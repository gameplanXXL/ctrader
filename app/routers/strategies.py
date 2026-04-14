"""Strategy page + CRUD routes (Epic 6).

Story 6.1 — POST /strategies, POST /strategies/{id}/status
Story 6.2 — GET /strategies renders the two-pane layout with list + metrics
Story 6.3 — the right pane is a fragment endpoint that lazy-loads the detail
Story 6.4 — POST /strategies/{id}/notes appends a note

NOTE on `from __future__ import annotations`: omitted on purpose —
the same pattern as `routers/pages.py` and `routers/trades.py`.
FastAPI tries to resolve `TemplateResponse` under future-annotations
and crashes.
"""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError as PydanticValidationError

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.models.strategy import (
    StrategyCreate,
    StrategyHorizon,
    StrategyStatus,
)
from app.services.mcp_health import get_all_agents
from app.services.sparkline import render_sparkline_svg
from app.services.strategy import (
    StrategyNotFoundError,
    StrategyTransitionError,
    add_note,
    create_strategy,
    get_strategy,
    list_notes,
    toggle_status,
    update_status,
)
from app.services.strategy_metrics import (
    get_strategy_detail,
    horizon_aggregates,
    list_strategies_with_metrics,
)
from app.services.taxonomy import get_taxonomy

logger = get_logger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for _name, _fn in JINJA_FILTERS.items():
    templates.env.filters[_name] = _fn


async def _require_pool(request: Request):
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")
    return db_pool


@router.get("", include_in_schema=False)
async def strategies_page(
    request: Request,
    selected: int | None = None,
    group_by_horizon: bool = False,
):
    """Story 6.2 — two-pane strategy page.

    Renders every strategy with its metrics in the left pane. If
    `?selected=<id>` is present, the right pane eagerly fetches the
    detail; otherwise Chef clicks a row to lazy-load it via HTMX.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    rows: list = []
    horizon_rows: list = []
    detail = None
    sparkline_svg = ""

    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                rows = await list_strategies_with_metrics(conn)
                horizon_rows = await horizon_aggregates(conn)
                if selected is not None:
                    detail = await get_strategy_detail(conn, selected)
                    if detail is not None:
                        sparkline_svg = render_sparkline_svg(
                            detail.sparkline_points,
                            aria_label="Cumulative P&L",
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("strategies_page.db_error", error=str(exc))

    context: dict[str, Any] = {
        "active_route": "strategies",
        "mcp_agents": get_all_agents(),
        "contract_drift": None,
        "strategies": rows,
        "horizon_rows": horizon_rows,
        "selected": selected,
        "detail": detail,
        "sparkline_svg": sparkline_svg,
        "group_by_horizon": group_by_horizon,
        "taxonomy": get_taxonomy(),
    }
    return templates.TemplateResponse(request, "pages/strategies.html", context)


@router.get("/{strategy_id}/detail_fragment", include_in_schema=False)
async def strategy_detail_fragment(request: Request, strategy_id: int):
    """Story 6.3 — HTMX target for clicking a strategy in the list."""

    db_pool = await _require_pool(request)
    async with db_pool.acquire() as conn:
        detail = await get_strategy_detail(conn, strategy_id)
        notes = await list_notes(conn, strategy_id) if detail else []

    if detail is None:
        raise HTTPException(status_code=404, detail="strategy not found")

    sparkline_svg = render_sparkline_svg(detail.sparkline_points, aria_label="Cumulative P&L")
    return templates.TemplateResponse(
        request,
        "fragments/strategy_detail.html",
        {
            "detail": detail,
            "sparkline_svg": sparkline_svg,
            "notes": notes,
        },
    )


@router.post("", include_in_schema=False)
async def create_strategy_route(request: Request):
    """Story 6.1 — POST /strategies.

    Accepts either form-encoded or JSON payload. Returns a redirect
    to the strategy list on success, or re-renders the form fragment
    with the validation error on 422.
    """

    form = await request.form()
    data: dict[str, Any] = {}
    for key in form:
        values = form.getlist(key)
        clean_key = key.removesuffix("[]")
        data[clean_key] = values if len(values) > 1 else values[0]

    try:
        payload = StrategyCreate(
            name=str(data.get("name", "")).strip(),
            asset_class=str(data.get("asset_class", "")).strip(),
            horizon=StrategyHorizon(str(data.get("horizon", "intraday"))),
            typical_holding_period=str(data.get("typical_holding_period") or "") or None,
            trigger_sources=_coerce_list(data.get("trigger_sources")),
            risk_budget_per_trade=_coerce_decimal(data.get("risk_budget_per_trade", "0")),
            status=StrategyStatus(str(data.get("status", "active"))),
        )
    except (PydanticValidationError, ValueError, InvalidOperation) as exc:
        logger.warning("strategy.create_invalid", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from None

    db_pool = await _require_pool(request)
    async with db_pool.acquire() as conn:
        try:
            strategy = await create_strategy(conn, payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("strategy.create_failed", error=str(exc))
            raise HTTPException(status_code=500, detail="could not create strategy") from None

    return RedirectResponse(
        url=f"/strategies?selected={strategy.id}",
        status_code=302,
        headers={
            "HX-Trigger": json.dumps(
                {
                    "showToast": {
                        "message": f"Strategie '{strategy.name}' erstellt",
                        "variant": "success",
                    }
                }
            )
        },
    )


@router.post("/{strategy_id}/status", include_in_schema=False)
async def post_status(request: Request, strategy_id: int):
    """Story 6.1 AC #4 — status toggle with one click.

    Form field `status` optionally forces a specific target state
    (for the "retire" / "activate" / "pause" buttons). Without it,
    the endpoint flips active ↔ paused and leaves retired alone.
    """

    form = await request.form()
    target_raw = form.get("status")
    db_pool = await _require_pool(request)

    try:
        async with db_pool.acquire() as conn:
            if target_raw:
                try:
                    target = StrategyStatus(str(target_raw))
                except ValueError:
                    raise HTTPException(status_code=422, detail="invalid target status") from None
                transition = await update_status(conn, strategy_id, target)
            else:
                transition = await toggle_status(conn, strategy_id)
            strategy = await get_strategy(conn, strategy_id)
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="strategy not found") from None
    except StrategyTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    return templates.TemplateResponse(
        request,
        "fragments/status_badge.html",
        {"strategy": strategy, "interactive": True},
        headers={
            "HX-Trigger": json.dumps(
                {
                    "showToast": {
                        "message": f"Status → {transition.new_status.value}",
                        "variant": "success",
                    }
                }
            )
        },
    )


@router.post("/{strategy_id}/notes", include_in_schema=False)
async def post_note(request: Request, strategy_id: int):
    """Story 6.4 — append a note to the strategy's history."""

    form = await request.form()
    content = str(form.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="note content must not be empty")

    db_pool = await _require_pool(request)
    async with db_pool.acquire() as conn:
        try:
            await add_note(conn, strategy_id, content)
            notes = await list_notes(conn, strategy_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    return templates.TemplateResponse(
        request,
        "fragments/strategy_notes.html",
        {"notes": notes, "strategy_id": strategy_id},
        headers={
            "HX-Trigger": json.dumps(
                {"showToast": {"message": "Notiz gespeichert", "variant": "success"}}
            )
        },
    )


# ---------------------------------------------------------------------------
# Form-data coercion helpers
# ---------------------------------------------------------------------------


def _coerce_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw if x]
    return []


def _coerce_decimal(raw: Any) -> Decimal:
    if raw is None or raw == "":
        return Decimal("0")
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"risk_budget_per_trade is not a number: {raw!r}") from exc
