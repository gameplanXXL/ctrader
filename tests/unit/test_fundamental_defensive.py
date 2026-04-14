"""Tests for the Tranche A defensive fixes (code-review H2/H3/H7/H8).

Covers:
- `_parse_mcp_response` never raises on malformed upstream shapes.
- `_parse_confidence` rejects bool and NaN.
- `is_stale=True` on stale fallback (H2 / EC-1).
- `format_staleness` / `severity_for_staleness` future-timestamp handling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.fundamental import FundamentalRating
from app.services.fundamental import (
    _parse_confidence,
    _parse_mcp_response,
    clear_caches,
    get_fundamental,
)
from app.services.staleness import format_staleness, severity_for_staleness


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_caches()
    yield
    clear_caches()


# ---------------------------------------------------------------------------
# H3 — parse defensiveness
# ---------------------------------------------------------------------------


def test_parse_response_on_non_dict_raw_returns_unknown() -> None:
    assert _parse_mcp_response("string response", "viktor").rating == FundamentalRating.UNKNOWN
    assert _parse_mcp_response([], "viktor").rating == FundamentalRating.UNKNOWN
    assert _parse_mcp_response(None, "viktor").rating == FundamentalRating.UNKNOWN


def test_parse_response_on_non_dict_result_returns_unknown() -> None:
    assert _parse_mcp_response({"result": "oops"}, "viktor").rating == FundamentalRating.UNKNOWN
    assert _parse_mcp_response({"result": None}, "viktor").rating == FundamentalRating.UNKNOWN
    assert _parse_mcp_response({"result": []}, "viktor").rating == FundamentalRating.UNKNOWN


def test_parse_response_mcp_metadata_not_in_extra() -> None:
    """MCP envelope keys (content, isError, _meta) should NOT leak into
    the assessment's `extra` dict."""

    raw = {
        "result": {
            "content": [],  # empty list falls through to shape 2
            "isError": False,
            "_meta": {"foo": "bar"},
            "rating": "BUY",
            "confidence": 0.7,
            "custom_field": "keep-me",
        }
    }
    assessment = _parse_mcp_response(raw, "viktor")
    assert assessment.rating == FundamentalRating.BUY
    assert "content" not in assessment.extra
    assert "isError" not in assessment.extra
    assert "_meta" not in assessment.extra
    assert assessment.extra.get("custom_field") == "keep-me"


def test_parse_response_content_as_dict_shape() -> None:
    """Some MCPs emit a single-dict content instead of a list."""

    raw = {
        "result": {
            "content": {
                "type": "text",
                "text": '{"rating":"HOLD","confidence":0.5}',
            }
        }
    }
    assessment = _parse_mcp_response(raw, "viktor")
    assert assessment.rating == FundamentalRating.HOLD


def test_parse_response_forward_compat_verdict_field() -> None:
    """Future MCP payload with `verdict` instead of `rating`."""

    raw = {"result": {"verdict": "SELL", "confidence": 0.6}}
    assessment = _parse_mcp_response(raw, "viktor")
    assert assessment.rating == FundamentalRating.SELL


# ---------------------------------------------------------------------------
# H7 — _parse_confidence bool/NaN rejection
# ---------------------------------------------------------------------------


def test_parse_confidence_rejects_true_as_100_percent() -> None:
    """bool(True) == 1 would previously pass through as confidence=1.0."""

    assert _parse_confidence(True) == 0.0
    assert _parse_confidence(False) == 0.0


def test_parse_confidence_rejects_nan() -> None:
    assert _parse_confidence(float("nan")) == 0.0


# ---------------------------------------------------------------------------
# H2 — is_stale=True on stale fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_disabled_stale_fallback_flags_is_stale() -> None:
    """Seed the stale cache via a successful fetch, then call again
    with mcp_client=None and assert `is_stale=True`."""

    mock = AsyncMock()
    mock.call_tool.return_value = {
        "result": {"content": [{"type": "text", "text": '{"rating":"BUY","confidence":0.8}'}]}
    }
    first = await get_fundamental("AAPL", "stock", mcp_client=mock)
    assert first is not None
    assert first.is_stale is False

    # Clear fresh cache → next call without MCP falls back to stale.
    from app.services.fundamental import _fresh_caches

    for cache in _fresh_caches.values():
        cache.clear()

    stale = await get_fundamental("AAPL", "stock", mcp_client=None)
    assert stale is not None
    assert stale.is_stale is True
    assert stale.assessment.rating == FundamentalRating.BUY


@pytest.mark.asyncio
async def test_mcp_exception_stale_fallback_flags_is_stale() -> None:
    mock = AsyncMock()
    mock.call_tool.return_value = {
        "result": {"content": [{"type": "text", "text": '{"rating":"LONG","confidence":0.6}'}]}
    }
    await get_fundamental("BTCUSD", "crypto", mcp_client=mock)

    from app.services.fundamental import _fresh_caches

    for cache in _fresh_caches.values():
        cache.clear()

    mock.call_tool.side_effect = RuntimeError("mcp blew up")
    stale = await get_fundamental("BTCUSD", "crypto", mcp_client=mock)
    assert stale is not None
    assert stale.is_stale is True


# ---------------------------------------------------------------------------
# H8 — future-timestamp staleness
# ---------------------------------------------------------------------------


NOW = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)


def test_format_staleness_future_timestamp_flags_anomaly() -> None:
    future = NOW + timedelta(hours=1)
    assert format_staleness(future, now=NOW) == "in der Zukunft (?)"


def test_severity_future_timestamp_is_red() -> None:
    future = NOW + timedelta(minutes=10)
    assert severity_for_staleness(future, now=NOW) == "red"


def test_format_staleness_within_clock_skew_tolerance_is_gerade_eben() -> None:
    """3 seconds in the future is clock-skew noise, not anomaly."""

    future = NOW + timedelta(seconds=3)
    assert format_staleness(future, now=NOW) == "gerade eben"
