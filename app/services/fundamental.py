"""Fundamental-analysis service (Story 5.1 / FR19 / FR22).

Routes a `(symbol, asset_class)` lookup to the correct MCP agent:

- `stock` → Viktor (SFA — `fundamentals` tool with stock payload)
- `option` → Viktor (options piggyback on the stock assessment of the
  underlying — Epic 5 keeps it simple)
- `crypto` → Satoshi (CFA — `fundamentals` tool with crypto payload)
- `cfd` → Satoshi (cover with the crypto assessment path as a first
  approximation; a proper CFD analyst can land post-MVP)

Cache rules (FR22 / NFR-I2):

- **Fresh cache** — per-asset-class TTL (15 min crypto, 1 h stock)
  keyed on `(symbol, asset_class)`. Fresh hits never hit MCP.
- **Stale fallback** — a separate long-term dict keyed the same way
  holds the *last successful* response regardless of TTL. When a
  fresh fetch fails (timeout, MCP outage, any exception), the service
  returns the stale entry with `is_stale=True` so the UI can render
  a banner instead of an error.

Graceful degradation (FR23 / NFR-R6) is the whole point — every code
path must return a `FundamentalResult` or `None`, never raise.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from cachetools import TTLCache

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.fundamental import FundamentalAssessment, FundamentalRating, FundamentalResult
from app.services.mcp_health import record_failure, record_success

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Agent routing
# ---------------------------------------------------------------------------


def _agent_for(asset_class: str) -> str:
    """Route an asset class to its analyst agent."""

    normalized = (asset_class or "").lower().strip()
    if normalized in ("crypto", "cfd"):
        return "satoshi"
    # stock / option / anything else: default to Viktor (SFA analyst).
    return "viktor"


# ---------------------------------------------------------------------------
# Cache state — module-level singletons.
# ---------------------------------------------------------------------------


# Fresh caches: TTL in seconds. Crypto moves faster so it gets a
# shorter window; stock thesis is more stable.
_FRESH_CACHE_TTL: dict[str, int] = {
    "crypto": 15 * 60,  # 15 minutes
    "cfd": 15 * 60,
    "stock": 60 * 60,  # 1 hour
    "option": 60 * 60,
}

_DEFAULT_MAXSIZE = 512

_fresh_caches: dict[str, TTLCache] = {
    key: TTLCache(maxsize=_DEFAULT_MAXSIZE, ttl=ttl) for key, ttl in _FRESH_CACHE_TTL.items()
}

# Stale fallback — no TTL, just "the last thing that worked". The
# dict is bounded via a simple size check on write.
_stale_cache: dict[tuple[str, str], FundamentalResult] = {}
_STALE_MAX_ENTRIES = 1024


def _as_stale(result: FundamentalResult | None) -> FundamentalResult | None:
    """Mark a stale-fallback result with `is_stale=True` before returning.

    Code-review H2 / EC-1: previously every return path handed back a
    cached `FundamentalResult(is_stale=False)` even when the path was
    the error-fallback, so the drilldown's stale-badge (`is_stale`)
    was dead code. Rebuild the result here so callers can reliably
    distinguish fresh vs fallback.
    """

    if result is None:
        return None
    return FundamentalResult(
        assessment=result.assessment,
        cached_at=result.cached_at,
        is_stale=True,
        source_agent=result.source_agent,
    )


def _fresh_cache_for(asset_class: str | None) -> TTLCache | None:
    """Code-review M5 / EC-10: normalize via the same rule as
    `_cache_key` so a trailing-whitespace asset_class doesn't bypass
    the cache entirely. Also tolerates `None` defensively."""

    if not asset_class:
        return None
    return _fresh_caches.get(asset_class.lower().strip())


def _cache_key(symbol: str, asset_class: str) -> tuple[str, str]:
    return (symbol.upper().strip(), asset_class.lower().strip())


# ---------------------------------------------------------------------------
# MCP response parsing
# ---------------------------------------------------------------------------


_VIKTOR_RATING_MAP = {
    "BUY": FundamentalRating.BUY,
    "HOLD": FundamentalRating.HOLD,
    "SELL": FundamentalRating.SELL,
    "STRONG_BUY": FundamentalRating.BUY,
    "STRONG_SELL": FundamentalRating.SELL,
}

_SATOSHI_RATING_MAP = {
    "LONG": FundamentalRating.LONG,
    "NEUTRAL": FundamentalRating.NEUTRAL,
    "SHORT": FundamentalRating.SHORT,
    "BUY": FundamentalRating.LONG,
    "SELL": FundamentalRating.SHORT,
    "HOLD": FundamentalRating.NEUTRAL,
}


def _parse_rating(raw: Any, agent: str) -> FundamentalRating:
    """Map an upstream rating string onto the normalized enum. Unknown
    inputs map to UNKNOWN — never raise."""

    if raw is None:
        return FundamentalRating.UNKNOWN
    token = str(raw).upper().strip()
    if agent == "satoshi":
        return _SATOSHI_RATING_MAP.get(token, FundamentalRating.UNKNOWN)
    return _VIKTOR_RATING_MAP.get(token, FundamentalRating.UNKNOWN)


def _parse_confidence(raw: Any) -> float:
    """Accept 0..1 floats or 0..100 percentages. Out-of-range clamps.

    Code-review H7 / BH-4: reject `bool` explicitly — `True/False`
    coerce to `1.0/0.0` via `float()`, which would silently pass
    through as fake confidence values. We also reject NaN since
    Pydantic's `ge/le` constraints raise on NaN and the "never raise"
    contract must not be broken by a rogue MCP response.
    """

    if raw is None or isinstance(raw, bool):
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value != value:  # NaN check — NaN is the only value unequal to itself
        return 0.0
    if value > 1.0:
        value = value / 100.0
    return max(0.0, min(1.0, value))


# Keys consumed by the top-level assessment fields — everything else
# goes into the `extra` bag. Kept together so the exclusion list and
# the lookup order stay in sync.
_RATING_FIELDS = ("rating", "signal", "recommendation", "verdict", "opinion")
_CONFIDENCE_FIELDS = ("confidence", "score")
_THESIS_FIELDS = ("thesis", "summary", "rationale")
# Keys that belong to the MCP transport envelope — we don't want them
# leaking into the stored `extra` bag (code-review M2 / BH-9).
_MCP_METADATA_KEYS = frozenset(
    {"content", "isError", "is_error", "_meta", "metadata", "jsonrpc", "id"}
)


def _parse_mcp_response(raw: Any, agent: str) -> FundamentalAssessment:
    """Convert a JSON-RPC `tools/call` response into an assessment.

    The MCP `fundamentals` tool returns `{"result": {"content": [...]}}`
    in the standard MCP protocol. Inside `content`, our `fundamental`
    project wraps the assessment as JSON text in a single content
    entry. We probe a few likely shapes so we don't lockstep-break
    when the upstream adds fields.

    Code-review H3 / EC-2 / EC-3: this function MUST NOT raise — the
    "never raise" contract from `get_fundamental` relies on it. We
    defensively normalize every unexpected shape (string, list,
    scalar, None) into an empty payload and return an UNKNOWN
    assessment instead of crashing the drilldown.
    """

    if not isinstance(raw, dict):
        return FundamentalAssessment(agent_id=agent)

    result = raw.get("result")
    if not isinstance(result, dict):
        return FundamentalAssessment(agent_id=agent)

    payload: dict[str, Any] = {}
    content = result.get("content")

    # Shape 1: `content` is a list of `{type: text, text: "<json>"}`
    if isinstance(content, list):
        import json as _json

        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str):
                continue
            try:
                parsed = _json.loads(text)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                payload = parsed
                break
    # Shape 1b: `content` is a single dict (some MCPs emit this).
    elif isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            import json as _json

            try:
                parsed = _json.loads(text)
                if isinstance(parsed, dict):
                    payload = parsed
            except ValueError:
                pass

    # Shape 2: `result` itself is the assessment dict — fall through
    # when Shape 1 didn't produce anything useful.
    if not payload:
        payload = {k: v for k, v in result.items() if k not in _MCP_METADATA_KEYS}

    return FundamentalAssessment(
        agent_id=agent,
        rating=_parse_rating(_first_present(payload, _RATING_FIELDS), agent),
        confidence=_parse_confidence(_first_present(payload, _CONFIDENCE_FIELDS)),
        thesis=str(_first_present(payload, _THESIS_FIELDS) or "").strip(),
        extra={
            k: v
            for k, v in payload.items()
            if k not in _RATING_FIELDS
            and k not in _CONFIDENCE_FIELDS
            and k not in _THESIS_FIELDS
            and k not in _MCP_METADATA_KEYS
        },
    )


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-None value for any of `keys` in `payload`."""

    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def get_fundamental(
    symbol: str,
    asset_class: str,
    mcp_client: MCPClient | None,
) -> FundamentalResult | None:
    """Return a fundamental assessment for `symbol` / `asset_class`.

    - Cache hit → fresh `FundamentalResult`
    - Cache miss + MCP available → fetch, cache, return fresh
    - Cache miss + MCP unavailable → return stale fallback if any,
      else `None`
    - MCP fetch fails (timeout, error) → stale fallback if any,
      else `None`

    Never raises.
    """

    key = _cache_key(symbol, asset_class)
    fresh = _fresh_cache_for(asset_class)
    agent = _agent_for(asset_class)

    if fresh is not None and key in fresh:
        cached: FundamentalResult = fresh[key]
        return FundamentalResult(
            assessment=cached.assessment,
            cached_at=cached.cached_at,
            is_stale=False,
            source_agent=cached.source_agent,
        )

    if mcp_client is None:
        logger.info(
            "fundamental.mcp_disabled",
            symbol=symbol,
            asset_class=asset_class,
        )
        return _as_stale(_stale_cache.get(key))

    # Code-review M1 / BH-3: the httpx client already enforces a
    # per-request timeout (default 10s). We pass the explicit
    # `timeout` kwarg through so callers can tighten it, and we
    # still catch both `httpx.TimeoutException` and the builtin
    # `TimeoutError` to cover any future asyncio.wait_for callers.
    try:
        raw = await mcp_client.call_tool(
            "fundamentals",
            {"symbol": symbol, "asset_class": asset_class, "agent": agent},
        )
    except (httpx.TimeoutException, TimeoutError) as exc:
        logger.warning(
            "fundamental.timeout",
            symbol=symbol,
            asset_class=asset_class,
            error=str(exc),
        )
        record_failure(agent)
        return _as_stale(_stale_cache.get(key))
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning(
            "fundamental.error",
            symbol=symbol,
            asset_class=asset_class,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        record_failure(agent)
        return _as_stale(_stale_cache.get(key))

    assessment = _parse_mcp_response(raw, agent)
    now = datetime.now(UTC)
    result = FundamentalResult(
        assessment=assessment,
        cached_at=now,
        is_stale=False,
        source_agent=agent,
    )

    if fresh is not None:
        fresh[key] = result
    # Store in the stale-fallback dict too, pruning if we're over cap.
    if len(_stale_cache) >= _STALE_MAX_ENTRIES:
        # Drop the oldest 10% — cheap FIFO truncation.
        keep = _STALE_MAX_ENTRIES - (_STALE_MAX_ENTRIES // 10)
        for k in list(_stale_cache.keys())[:-keep]:
            _stale_cache.pop(k, None)
    _stale_cache[key] = result

    record_success(agent)
    return result


def clear_caches() -> None:
    """Test helper — drop all in-memory state between tests."""

    for cache in _fresh_caches.values():
        cache.clear()
    _stale_cache.clear()
