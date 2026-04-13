"""Trade-specific routes — currently just the inline-expansion fragment.

Story 2.4: `GET /trades/{id}/detail_fragment` returns the HTML for one
trade drilldown, ready to be swapped into the row's expansion slot by
HTMX. Story 2.3 owns the journal page route in `routers/pages.py`;
this module owns the trade-detail endpoints.

NOTE on `from __future__ import annotations`: omitted on purpose for
the same reason as `routers/pages.py` — FastAPI tries to resolve
`templates.TemplateResponse` as a class, which it isn't.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.filters.formatting import JINJA_FILTERS
from app.services.expectancy import compute_expectancy_at_entry
from app.services.pnl import compute_pnl
from app.services.r_multiple import compute_r_multiple
from app.services.trade_query import get_trade_detail

router = APIRouter(prefix="/trades", tags=["trades"])

# Reuse the same templates dir as the pages router so component imports
# resolve. We re-register the filters because `Jinja2Templates` builds
# its own env per instance.
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for filter_name, filter_func in JINJA_FILTERS.items():
    templates.env.filters[filter_name] = filter_func


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
