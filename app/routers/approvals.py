"""Approval pipeline routes (Epic 7).

Story 7.1 — GET /approvals (dashboard), POST /api/proposals (creation)
Story 7.3 — GET /proposals/{id}/drilldown (3-column viewport fragment)
Story 7.4 — POST /proposals/{id}/approve | /reject | /revision

NOTE: omits `from __future__ import annotations` so FastAPI doesn't
crash on `TemplateResponse` resolution under the future-annotations
stringization rule.
"""

import asyncio
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError as PydanticValidationError

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.models.proposal import (
    ProposalCreate,
    ProposalDecision,
)
from app.services.bot_execution import trigger_bot_execution
from app.services.fundamental import get_fundamental
from app.services.mcp_health import get_all_agents
from app.services.proposal import (
    ProposalBlockedError,
    ProposalNotFoundError,
    ProposalStrategyInactiveError,
    approve_proposal,
    create_proposal,
    get_proposal,
    list_pending_proposals,
    reject_proposal,
    run_risk_gate_for_proposal,
    send_to_revision,
)

logger = get_logger(__name__)

router = APIRouter(tags=["approvals"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for _name, _fn in JINJA_FILTERS.items():
    templates.env.filters[_name] = _fn


async def _require_pool(request: Request):
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")
    return db_pool


# ---------------------------------------------------------------------------
# Story 7.1 — dashboard page
# ---------------------------------------------------------------------------


@router.get("/approvals", include_in_schema=False)
async def approvals_page(request: Request):
    """Render the approval dashboard with all pending proposals."""

    db_pool = getattr(request.app.state, "db_pool", None)
    proposals: list = []
    db_error = False

    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                proposals = await list_pending_proposals(conn)
        except Exception as exc:  # noqa: BLE001
            logger.exception("approvals_page.db_error", error=str(exc))
            db_error = True

    return templates.TemplateResponse(
        request,
        "pages/approvals.html",
        {
            "active_route": "approvals",
            "mcp_agents": get_all_agents(),
            "contract_drift": None,
            "proposals": proposals,
            "db_error": db_error,
        },
    )


# ---------------------------------------------------------------------------
# Story 7.1 — proposal creation API (Bot side)
# ---------------------------------------------------------------------------


@router.post("/api/proposals", include_in_schema=False)
async def create_proposal_route(request: Request) -> JSONResponse:
    """Bot-side entry point. Accepts a JSON body (Pydantic-validated),
    runs the risk gate immediately, and returns the persisted proposal
    with the verdict attached.
    """

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid JSON body") from None

    try:
        payload = ProposalCreate.model_validate(body)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from None

    db_pool = await _require_pool(request)
    mcp_client = getattr(request.app.state, "mcp_client", None)

    async with db_pool.acquire() as conn:
        try:
            proposal = await create_proposal(conn, payload)
        except ProposalStrategyInactiveError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        # Story 7.2: risk-gate verdict written before the proposal is
        # visible to Chef. Failure stays on the row as UNREACHABLE
        # (mapped to red in the DB) so the dashboard can render it.
        proposal = await run_risk_gate_for_proposal(conn, proposal, mcp_client)

    return JSONResponse(
        {
            "id": proposal.id,
            "status": proposal.status.value,
            "risk_gate_result": (
                proposal.risk_gate_result.value if proposal.risk_gate_result else None
            ),
        },
        status_code=201,
    )


# ---------------------------------------------------------------------------
# Story 7.3 — proposal drilldown fragment
# ---------------------------------------------------------------------------


@router.get("/proposals/{proposal_id}/drilldown", include_in_schema=False)
async def proposal_drilldown(request: Request, proposal_id: int):
    """3-column viewport fragment (agent / fundamental / risk gate)."""

    db_pool = await _require_pool(request)
    mcp_client = getattr(request.app.state, "mcp_client", None)

    async with db_pool.acquire() as conn:
        proposal = await get_proposal(conn, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="proposal not found")

    fundamental = None
    try:
        fundamental = await get_fundamental(proposal.symbol, proposal.asset_class, mcp_client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("proposal_drilldown.fundamental_failed", error=str(exc))

    return templates.TemplateResponse(
        request,
        "fragments/proposal_drilldown.html",
        {
            "proposal": proposal,
            "fundamental": fundamental,
        },
    )


# ---------------------------------------------------------------------------
# Story 7.4 — decision endpoints
# ---------------------------------------------------------------------------


def _parse_decision(form: dict[str, Any]) -> ProposalDecision:
    risk_budget_raw = form.get("risk_budget")
    risk_budget: Decimal | None = None
    if risk_budget_raw not in (None, ""):
        try:
            risk_budget = Decimal(str(risk_budget_raw))
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=422, detail=f"invalid risk_budget: {risk_budget_raw}"
            ) from exc

    overrode = form.get("overrode_fundamental")
    overrode_flag = False
    if isinstance(overrode, str):
        overrode_flag = overrode.lower() in ("true", "on", "1", "yes")
    elif overrode is not None:
        overrode_flag = bool(overrode)

    notes_raw = form.get("notes") or form.get("note")
    notes = str(notes_raw).strip() if notes_raw else None

    try:
        return ProposalDecision(
            risk_budget=risk_budget,
            overrode_fundamental=overrode_flag,
            notes=notes,
        )
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from None


@router.post("/proposals/{proposal_id}/approve", include_in_schema=False)
async def post_approve(request: Request, proposal_id: int):
    form = await request.form()
    decision = _parse_decision({k: form.get(k) for k in form})

    db_pool = await _require_pool(request)
    mcp_client = getattr(request.app.state, "mcp_client", None)
    ctrader_client = getattr(request.app.state, "ctrader_client", None)

    try:
        async with db_pool.acquire() as conn:
            await approve_proposal(conn, proposal_id, decision, mcp_client)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ProposalBlockedError as exc:
        # FR28: hard invariant — RED / UNREACHABLE blocks approval
        # at the backend, not just the frontend.
        raise HTTPException(status_code=403, detail=str(exc)) from None

    # Story 8.1: fire-and-forget bot execution after successful approve.
    # Never blocks the HTTP response; errors inside `trigger_bot_execution`
    # are swallowed and logged by bot_execution itself.
    asyncio.create_task(trigger_bot_execution(db_pool, ctrader_client, proposal_id))

    return _decision_response("approved", proposal_id)


@router.post("/proposals/{proposal_id}/reject", include_in_schema=False)
async def post_reject(request: Request, proposal_id: int):
    form = await request.form()
    decision = _parse_decision({k: form.get(k) for k in form})

    db_pool = await _require_pool(request)
    try:
        async with db_pool.acquire() as conn:
            await reject_proposal(conn, proposal_id, decision)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    return _decision_response("rejected", proposal_id)


@router.post("/proposals/{proposal_id}/revision", include_in_schema=False)
async def post_revision(request: Request, proposal_id: int):
    form = await request.form()
    decision = _parse_decision({k: form.get(k) for k in form})

    db_pool = await _require_pool(request)
    try:
        async with db_pool.acquire() as conn:
            await send_to_revision(conn, proposal_id, decision)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    return _decision_response("revision", proposal_id)


def _decision_response(action: str, proposal_id: int) -> Response:
    """Common response shape for approve / reject / revision.

    Returns an empty body so HTMX `hx-swap="outerHTML"` removes the
    proposal card from the dashboard, plus an `HX-Trigger` toast.
    Code-review M10 / BH-15: dropped the unused `request` and
    `proposal` parameters.
    """

    label = {
        "approved": "Approved",
        "rejected": "Rejected",
        "revision": "Sent for revision",
    }.get(action, action)

    return Response(
        status_code=200,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {
                    "showToast": {
                        "message": f"Proposal #{proposal_id}: {label}",
                        "variant": "success",
                    }
                }
            )
        },
    )
