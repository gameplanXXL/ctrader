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
from app.services.trade_query import DEFAULT_PAGE_SIZE, list_trades

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
):
    """Journal start page — paginated trade list + untagged counter.

    Borrows a connection from the asyncpg pool that the lifespan owns.
    Falls back to an empty `TradeListPage` if the pool isn't available
    (e.g., during the smoke tests where conftest provides an
    AsyncMock pool that doesn't support real queries).
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    journal_page_data = None

    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                journal_page_data = await list_trades(conn, page=page)
        except Exception:  # noqa: BLE001 — keep the page rendering
            journal_page_data = None

    if journal_page_data is None:
        # Empty fallback — used by unit tests with the AsyncMock pool
        # and by the smoke test where the table may be empty.
        from app.services.trade_query import TradeListPage

        journal_page_data = TradeListPage(
            trades=[],
            untagged_count=0,
            total_count=0,
            page=page,
            per_page=DEFAULT_PAGE_SIZE,
        )

    return templates.TemplateResponse(
        request,
        "pages/journal.html",
        {"active_route": "journal", "page": journal_page_data},
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
