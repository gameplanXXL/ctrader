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
from app.services.mistakes_report import MistakeRow, top_n_mistakes
from app.services.pnl import compute_pnl
from app.services.r_multiple import compute_r_multiple
from app.services.taxonomy import get_taxonomy
from app.services.trade_query import DEFAULT_PAGE_SIZE, get_trade_detail, list_trades
from app.services.trigger_prose import render_mistake_tags, render_trigger_prose

logger = get_logger(__name__)

router = APIRouter()

# Resolve templates directory once at import time.
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Register the formatting filters on the Jinja env so templates can use
# `{{ trade.pnl | format_pnl }}` etc. Story 2.3 added these.
for filter_name, filter_func in JINJA_FILTERS.items():
    templates.env.filters[filter_name] = filter_func
# Story 3.3 — expose the trigger-prose renderers so the journal
# expansion prefill also renders trigger_spec_readable correctly.
templates.env.globals["render_trigger_prose"] = render_trigger_prose
templates.env.globals["render_mistake_tags"] = render_mistake_tags


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


@router.get("/journal/mistakes", include_in_schema=False)
async def mistakes_report_page(
    request: Request,
    window: str = Query(default="30d", description="Time window — 7d, 30d, 90d, ytd, all"),
):
    """Story 3.4 — Top-N Mistakes report.

    Aggregates `trigger_spec->mistake_tags` over a window and ranks by
    total cost (most negative P&L first), then frequency. Renders an
    empty table with a helpful hint when no tags are present.
    """

    rows: list[MistakeRow] = []
    window_start = None
    window_end = None
    total_trades = 0

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                rows, window_start, window_end = await top_n_mistakes(conn, window=window)
                # Count ALL tagged trades in-window so the UI can show
                # "3 mistakes across 12 trades" rather than a bare count.
                total_trades = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM trades
                     WHERE trigger_spec IS NOT NULL
                       AND opened_at BETWEEN $1 AND $2
                    """,
                    window_start,
                    window_end,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mistakes_report.db_error", error=str(exc))

    # Look up the friendly label for each tag from taxonomy.yaml.
    taxonomy = get_taxonomy()
    tag_labels = {entry.id: (entry.label or entry.id) for entry in taxonomy.mistake_tags}

    return templates.TemplateResponse(
        request,
        "pages/mistakes_report.html",
        {
            "active_route": "journal",
            "rows": rows,
            "tag_labels": tag_labels,
            "window": window,
            "window_start": window_start,
            "window_end": window_end,
            "total_trades": total_trades or 0,
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
