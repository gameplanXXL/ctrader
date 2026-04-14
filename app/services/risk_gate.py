"""Risk-gate service (Story 7.2 / FR27 / FR28).

Routes a proposal to the right MCP agent for a 3-stage risk verdict:

- `stock` / `option` → Rita
- `crypto` / `cfd`   → Cassandra

Returns a `RiskGateResult` whose `level` ∈ {green, yellow, red,
unreachable}. The application-only `unreachable` value is treated
the same as `red` everywhere it gates UI behaviour, so an MCP outage
fails closed on Action-Views (per FR23 / NFR-R6 — Action-Views block
explicitly, Info-Views degrade gracefully).

Never raises — graceful degradation always returns a result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.proposal import Proposal, RiskGateLevel
from app.models.risk_gate import RiskGateResult
from app.services.mcp_health import record_failure, record_success

logger = get_logger(__name__)


def _agent_for(asset_class: str) -> str:
    """`stock`/`option` → Rita; `crypto`/`cfd` → Cassandra."""

    normalized = (asset_class or "").lower().strip()
    if normalized in ("crypto", "cfd"):
        return "cassandra"
    return "rita"


def _parse_level(raw: Any) -> RiskGateLevel:
    """Defensive enum mapping. Unknown levels collapse to `red`
    (fail-closed) so an unexpected MCP response never inadvertently
    unlocks the approve button."""

    if raw is None:
        return RiskGateLevel.RED
    token = str(raw).lower().strip()
    if token in ("green", "ok", "pass"):
        return RiskGateLevel.GREEN
    if token in ("yellow", "warn", "warning", "caution"):
        return RiskGateLevel.YELLOW
    if token in ("red", "block", "blocked", "fail"):
        return RiskGateLevel.RED
    return RiskGateLevel.RED


def _extract_payload(raw: Any) -> dict[str, Any]:
    """Pull the actual assessment dict out of the MCP envelope.

    Same shape-tolerance as `fundamental._parse_mcp_response`:
    handles both `result.content[0].text` (JSON-encoded) and a flat
    `result` dict. Any malformed shape returns `{}`.
    """

    if not isinstance(raw, dict):
        return {}
    result = raw.get("result")
    if not isinstance(result, dict):
        return {}

    content = result.get("content")
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
                return parsed
    elif isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            import json as _json

            try:
                parsed = _json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except ValueError:
                pass

    # Shape 2 — `result` is the assessment itself. Strip MCP envelope keys.
    return {
        k: v
        for k, v in result.items()
        if k not in {"content", "isError", "is_error", "_meta", "metadata"}
    }


async def run_risk_gate(
    proposal: Proposal,
    mcp_client: MCPClient | None,
) -> RiskGateResult:
    """Evaluate a proposal via the appropriate MCP risk-gate agent.

    Never raises:
    - MCP None / unreachable → level=UNREACHABLE (treated as RED for
      gating purposes)
    - MCP timeout / HTTP error → level=UNREACHABLE
    - Unexpected payload shape → level=RED with `flags=["parse_error"]`
    """

    agent = _agent_for(proposal.asset_class)
    now = datetime.now(UTC)

    if mcp_client is None:
        logger.info("risk_gate.mcp_disabled", proposal_id=proposal.id, agent=agent)
        return RiskGateResult(
            level=RiskGateLevel.UNREACHABLE,
            flags=["mcp_unreachable"],
            details={},
            evaluated_at=now,
            agent_id=agent,
        )

    try:
        raw = await mcp_client.call_tool(
            "risk_gate",
            {
                "agent": agent,
                "symbol": proposal.symbol,
                "asset_class": proposal.asset_class,
                "side": proposal.side.value,
                "horizon": proposal.horizon.value,
                "entry_price": str(proposal.entry_price),
                "stop_price": str(proposal.stop_price) if proposal.stop_price else None,
                "position_size": str(proposal.position_size),
                "risk_budget": str(proposal.risk_budget),
                "trigger_spec": proposal.trigger_spec,
            },
        )
    except (httpx.TimeoutException, TimeoutError) as exc:
        logger.warning("risk_gate.timeout", proposal_id=proposal.id, error=str(exc))
        record_failure(agent)
        return RiskGateResult(
            level=RiskGateLevel.UNREACHABLE,
            flags=["timeout"],
            details={},
            evaluated_at=now,
            agent_id=agent,
        )
    except Exception as exc:  # noqa: BLE001 — never raise
        logger.warning(
            "risk_gate.error",
            proposal_id=proposal.id,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        record_failure(agent)
        return RiskGateResult(
            level=RiskGateLevel.UNREACHABLE,
            flags=["mcp_error", type(exc).__name__],
            details={},
            evaluated_at=now,
            agent_id=agent,
        )

    payload = _extract_payload(raw)
    if not payload:
        # MCP returned 2xx but the body shape was unrecognisable.
        # Fail closed — RED, not UNREACHABLE, because the server IS
        # reachable, just incomprehensible.
        logger.warning("risk_gate.parse_error", proposal_id=proposal.id, agent=agent)
        record_failure(agent)
        return RiskGateResult(
            level=RiskGateLevel.RED,
            flags=["parse_error"],
            details=raw if isinstance(raw, dict) else {},
            evaluated_at=now,
            agent_id=agent,
        )

    level = _parse_level(payload.get("level") or payload.get("verdict") or payload.get("status"))
    flags_raw = payload.get("flags") or []
    flags = [str(f) for f in flags_raw if f] if isinstance(flags_raw, list) else []

    record_success(agent)
    return RiskGateResult(
        level=level,
        flags=flags,
        details=payload,
        evaluated_at=now,
        agent_id=agent,
    )
