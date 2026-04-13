"""Trade-specific routes.

Story 2.4: `GET /trades/{id}/detail_fragment` returns the HTML for one
trade drilldown, ready to be swapped into the row's expansion slot by
HTMX. Story 2.3 owns the journal page route in `routers/pages.py`;
this module owns the trade-detail endpoints.

Story 3.1 adds the tagging surface:
- `GET  /trades/{id}/tagging_form`   → renders the tagging form fragment
- `POST /trades/{id}/tag`            → persists a trigger_spec and
                                       jumps the user to the next
                                       untagged trade.

NOTE on `from __future__ import annotations`: omitted on purpose for
the same reason as `routers/pages.py` — FastAPI tries to resolve
`templates.TemplateResponse` as a class, which it isn't.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.services.expectancy import compute_expectancy_at_entry
from app.services.pnl import compute_pnl
from app.services.r_multiple import compute_r_multiple
from app.services.strategy_source import list_strategies_for_dropdown
from app.services.tagging import TradeNotFoundError, tag_trade
from app.services.taxonomy import get_taxonomy
from app.services.trade_query import get_trade_detail, next_untagged_trade
from app.services.trigger_prose import render_mistake_tags, render_trigger_prose
from app.services.trigger_spec import TriggerSpecValidationError, build_from_tagging_form

logger = get_logger(__name__)

router = APIRouter(prefix="/trades", tags=["trades"])

# Reuse the same templates dir as the pages router so component imports
# resolve. We re-register the filters because `Jinja2Templates` builds
# its own env per instance.
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for filter_name, filter_func in JINJA_FILTERS.items():
    templates.env.filters[filter_name] = filter_func
# Story 3.3 — expose the trigger-prose renderers to templates so the
# trigger_spec_readable macro can call them without importing.
templates.env.globals["render_trigger_prose"] = render_trigger_prose
templates.env.globals["render_mistake_tags"] = render_mistake_tags


@router.get("/{trade_id}/detail_fragment", include_in_schema=False)
async def trade_detail_fragment(request: Request, trade_id: int):
    """Return the inline-expansion HTML fragment for one trade.

    Story 2.4 AC #1 + #6: HTMX-targeted partial that the trade row
    swaps into its expansion slot. Falls back to a 404 fragment if the
    trade ID doesn't exist (so the journal still shows its row layout
    instead of a blank gap).
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    trade = None

    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                trade = await get_trade_detail(conn, trade_id)
        except Exception:  # noqa: BLE001 — render a 404 instead of 500
            trade = None

    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")

    return templates.TemplateResponse(
        request,
        "fragments/trade_detail.html",
        {
            "trade": trade,
            "computed_pnl": compute_pnl(trade),
            "computed_r_multiple": compute_r_multiple(trade),
            "computed_expectancy": compute_expectancy_at_entry(trade),
        },
    )


# ---------------------------------------------------------------------------
# Story 3.1 — tagging form + tag POST
# ---------------------------------------------------------------------------


@router.get("/{trade_id}/tagging_form", include_in_schema=False)
async def tagging_form(request: Request, trade_id: int):
    """Render the tagging form for one trade.

    Story 3.1 AC #1 + #2 + #3: 4 dropdowns (strategy, trigger_type,
    horizon, exit_reason) + optional mistake_tags + optional note. The
    strategy list uses the source adapter so the form also works
    before Epic 6 creates the strategies table.
    """

    taxonomy = get_taxonomy()
    trade = None
    strategies: list[tuple[str, str]] = []

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                trade = await get_trade_detail(conn, trade_id)
                strategies = await list_strategies_for_dropdown(conn)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tagging_form.db_error", error=str(exc))

    if trade is None:
        # Fallback: still render the form if DB access failed so the
        # user at least sees something — but flag it with a 404.
        raise HTTPException(status_code=404, detail="trade not found")

    return templates.TemplateResponse(
        request,
        "fragments/tagging_form.html",
        {
            "trade": trade,
            "strategies": strategies,
            "trigger_types": taxonomy.trigger_types,
            "horizons": taxonomy.horizons,
            "exit_reasons": taxonomy.exit_reasons,
            "mistake_tags": taxonomy.mistake_tags,
            "error": None,
        },
    )


@router.post("/{trade_id}/tag", include_in_schema=False)
async def post_tag(request: Request, trade_id: int):
    """Persist the tagging form as a `trigger_spec` and jump to the next
    untagged trade.

    Returns a small HTMX-friendly fragment + `HX-Trigger: showToast`
    header so the base layout's toast component can display the success
    message (Story 3.1 AC #6).
    """

    form = await request.form()
    form_data: dict[str, object] = {}
    # Multi-value form fields (mistake_tags[]) arrive as repeated keys.
    for key in form:
        values = form.getlist(key)
        form_data[key.rstrip("[]")] = values if len(values) > 1 else values[0]

    try:
        spec = build_from_tagging_form(form_data)
    except TriggerSpecValidationError as exc:
        logger.warning("tagging.invalid_form", trade_id=trade_id, error=str(exc))
        return _render_form_error(request, trade_id, str(exc))

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    try:
        async with db_pool.acquire() as conn:
            await tag_trade(conn, trade_id, spec)
            next_trade = await next_untagged_trade(conn)
    except TradeNotFoundError:
        raise HTTPException(status_code=404, detail="trade not found") from None

    headers = {
        "HX-Trigger": json.dumps({"showToast": {"message": "Trade getaggt", "variant": "success"}})
    }

    return templates.TemplateResponse(
        request,
        "fragments/tagging_success.html",
        {
            "trade_id": trade_id,
            "next_trade": next_trade,
        },
        headers=headers,
    )


def _render_form_error(request: Request, trade_id: int, message: str) -> Response:
    """Re-render the tagging form with a visible validation error.

    Story 3.1 AC #8 — form-level error shown when the client-side
    validation misses or is bypassed.
    """

    taxonomy = get_taxonomy()
    return templates.TemplateResponse(
        request,
        "fragments/tagging_form.html",
        {
            "trade": {"id": trade_id},
            "strategies": [],
            "trigger_types": taxonomy.trigger_types,
            "horizons": taxonomy.horizons,
            "exit_reasons": taxonomy.exit_reasons,
            "mistake_tags": taxonomy.mistake_tags,
            "error": message,
        },
        status_code=422,
    )
