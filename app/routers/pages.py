"""Top-level page routes.

Story 1.5 scope: six empty page shells, one per top-level nav item.
Each page renders `base.html` with the matching `active_route` so the
top-bar highlights the current section. Real content lands in the
respective epic stories (2, 6, 7, 9, 10, 12).

`GET /` redirects to `/journal` — Chef's primary landing surface.

Note: Return-type annotations are intentionally omitted on the
endpoints so FastAPI doesn't try to re-evaluate `TemplateResponse`
(which isn't a real class) under `from __future__ import annotations`.
That's also why this module does **not** use future-annotations at all.
"""

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.services.expectancy import compute_expectancy_at_entry
from app.services.pnl import compute_pnl
from app.services.r_multiple import compute_r_multiple
from app.services.trade_query import DEFAULT_PAGE_SIZE, get_trade_detail, list_trades

logger = get_logger(__name__)

router = APIRouter()

# Resolve templates directory once at import time.
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Register the formatting filters on the Jinja env so templates can use
# `{{ trade.pnl | format_pnl }}` etc. Story 2.3 added these.
for filter_name, filter_func in JINJA_FILTERS.items():
    templates.env.filters[filter_name] = filter_func


def _render(request: Request, page: str):
    """Convenience wrapper: render a page template with active-route context."""

    return templates.TemplateResponse(
        request,
        f"pages/{page}.html",
        {"active_route": page},
    )


@router.get("/", include_in_schema=False)
async def root_redirect():
    """Land on the Journal — the primary trader surface."""

    return RedirectResponse(url="/journal", status_code=302)


@router.get("/journal", include_in_schema=False)
async def journal_page(
    request: Request,
    page: int = Query(default=1, ge=1, description="1-indexed page number"),
    expand: int | None = Query(
        default=None,
        description="Trade ID to render expanded inline (Story 2.4 AC #4 — bookmarkable)",
    ),
):
    """Journal start page — paginated trade list + untagged counter.

    If `?expand=<trade_id>` is present, the trade's drilldown context
    is fetched and exposed to the template so the journal can pre-fill
    the matching expansion-row at first render. Bookmarkable URL,
    Story 2.4 AC #4 — code-review M11 fix.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    journal_page_data = None
    expanded_trade = None

    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                journal_page_data = await list_trades(conn, page=page)
                if expand is not None:
                    expanded_trade = await get_trade_detail(conn, expand)
        except Exception as exc:  # noqa: BLE001 — keep the page rendering
            # Log loudly so DB issues don't disappear behind an empty
            # journal — code-review M4 fix.
            logger.warning(
                "journal_page.db_error",
                error=str(exc),
                exception_type=type(exc).__name__,
            )
            journal_page_data = None
            expanded_trade = None

    if journal_page_data is None:
        from app.services.trade_query import TradeListPage

        journal_page_data = TradeListPage(
            trades=[],
            untagged_count=0,
            total_count=0,
            page=page,
            per_page=DEFAULT_PAGE_SIZE,
        )

    expansion_context = None
    if expanded_trade is not None:
        expansion_context = {
            "trade": expanded_trade,
            "computed_pnl": compute_pnl(expanded_trade),
            "computed_r_multiple": compute_r_multiple(expanded_trade),
            "computed_expectancy": compute_expectancy_at_entry(expanded_trade),
        }

    return templates.TemplateResponse(
        request,
        "pages/journal.html",
        {
            "active_route": "journal",
            "page": journal_page_data,
            "expand_id": expand,
            "expansion": expansion_context,
        },
    )


@router.get("/strategies", include_in_schema=False)
async def strategies_page(request: Request):
    return _render(request, "strategies")


@router.get("/approvals", include_in_schema=False)
async def approvals_page(request: Request):
    return _render(request, "approvals")


@router.get("/trends", include_in_schema=False)
async def trends_page(request: Request):
    return _render(request, "trends")


@router.get("/regime", include_in_schema=False)
async def regime_page(request: Request):
    return _render(request, "regime")


@router.get("/settings", include_in_schema=False)
async def settings_page(request: Request):
    return _render(request, "settings")
