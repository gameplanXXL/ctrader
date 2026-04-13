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

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.services.aggregation import compute_aggregation
from app.services.csv_export import export_trades_csv
from app.services.daily_pnl import get_daily_pnl, iter_month_days
from app.services.expectancy import compute_expectancy_at_entry
from app.services.facets import render_facets
from app.services.mcp_contract_test import get_latest_contract_test
from app.services.mcp_health import get_all_agents
from app.services.mistakes_report import MistakeRow, top_n_mistakes
from app.services.pnl import compute_pnl
from app.services.query_prose import render_query_prose
from app.services.r_multiple import compute_r_multiple
from app.services.sparkline import render_sparkline_svg
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


# ---------------------------------------------------------------------------
# Story 4.1 — facet URL helpers
# ---------------------------------------------------------------------------

# Facets we recognize in the URL query string. Anything else is ignored
# so bots / typos don't crash the page.
_FACET_KEYS = {
    "asset_class",
    "broker",
    "horizon",
    "strategy",
    "trigger_type",
    "followed",
    "confidence_band",
    "regime_tag",
}


def _parse_facet_query(request: Request) -> dict[str, list[str]]:
    """Parse the request's query string into the facet-framework dict shape.

    Supports both repeated keys (`?asset_class=stock&asset_class=crypto`)
    and comma-separated lists (`?asset_class=stock,crypto`) so pasted
    URLs from the command palette round-trip cleanly.
    """

    facets: dict[str, list[str]] = {}
    for key in _FACET_KEYS:
        raw_values = request.query_params.getlist(key)
        flat: list[str] = []
        for raw in raw_values:
            for value in raw.split(","):
                value = value.strip()
                if value:
                    flat.append(value)
        if flat:
            facets[key] = flat
    return facets


def _build_facet_href(base_url: str, facet_name: str, value: str, currently_selected: bool):
    """Return the URL that toggles `value` inside `facet_name`."""

    def _href(request: Request | None = None) -> str:
        # The template wires this into jinja2, so we return a callable
        # that the closure can access via `build_facet_href(...)`. The
        # real implementation is in `_facet_href_builder` below.
        return ""

    return _href


def _facet_href_builder(current_facets: dict[str, list[str]], base_url: str = "/journal"):
    """Return a Jinja-friendly callable for building toggle URLs."""

    def _build(base: str, facet_name: str, value_id: str, selected: bool) -> str:
        next_facets = {k: list(v) for k, v in current_facets.items()}
        current = next_facets.get(facet_name, [])
        if selected:
            current = [v for v in current if v != value_id]
        else:
            if value_id not in current:
                current = list(current) + [value_id]
        if current:
            next_facets[facet_name] = current
        else:
            next_facets.pop(facet_name, None)
        query_items: list[tuple[str, str]] = []
        for name, values in next_facets.items():
            for v in values:
                query_items.append((name, v))
        qs = urlencode(query_items)
        return f"{base}?{qs}" if qs else base

    return _build


async def _base_context(request: Request) -> dict[str, Any]:
    """Shared base-template context — MCP health + latest contract drift.

    Story 5.3 + 5.4: every page route merges this into its own
    context dict so `base.html` can render the staleness and drift
    banners without each route having to plumb them manually.
    Returns a context with safe defaults if the DB pool is down.
    """

    context: dict[str, Any] = {
        "mcp_agents": get_all_agents(),
        "contract_drift": None,
    }
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        return context
    try:
        async with db_pool.acquire() as conn:
            latest = await get_latest_contract_test(conn)
        if latest is not None and latest.has_drift:
            context["contract_drift"] = latest
    except Exception as exc:  # noqa: BLE001
        logger.warning("pages.contract_drift_probe_failed", error=str(exc))
    return context


def _render(request: Request, page: str, **extra: Any):
    """Convenience wrapper: render a page template with active-route context.

    Extra context is merged on top of the defaults.
    """

    context: dict[str, Any] = {
        "active_route": page,
        "mcp_agents": get_all_agents(),
        "contract_drift": None,
    }
    context.update(extra)
    return templates.TemplateResponse(
        request,
        f"pages/{page}.html",
        context,
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
    date_filter: str | None = Query(
        default=None,
        alias="date",
        description="Story 4.4 — filter to a single day (YYYY-MM-DD)",
    ),
):
    """Journal start page — paginated trade list, facets, and hero block.

    Story 4.1 adds facet parsing: every known facet key in the query
    string is translated into a `dict[str, list[str]]` and passed to
    both `list_trades` and `render_facets` so chip counts reflect the
    current drill-in.

    Story 4.2 adds the hero aggregation block + query prose.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    facets = _parse_facet_query(request)

    # Calendar-day filter (Story 4.4). Invalid dates silently fall back
    # to "no filter" so a typo doesn't 500 the page.
    trade_date: date | None = None
    if date_filter:
        try:
            trade_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
        except ValueError:
            trade_date = None

    journal_page_data = None
    expanded_trade = None
    facet_selections: list = []
    aggregation = None
    sparkline_svg = ""

    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                journal_page_data = await list_trades(
                    conn, page=page, facets=facets, trade_date=trade_date
                )
                if expand is not None:
                    expanded_trade = await get_trade_detail(conn, expand)
                facet_selections = await render_facets(conn, facets)
                aggregation = await compute_aggregation(conn, facets)
                sparkline_svg = render_sparkline_svg(
                    aggregation.sparkline_points,
                    aria_label="Cumulative P&L trend",
                )
        except Exception as exc:  # noqa: BLE001 — keep the page rendering
            logger.warning(
                "journal_page.db_error",
                error=str(exc),
                exception_type=type(exc).__name__,
            )
            journal_page_data = None
            expanded_trade = None
            facet_selections = []
            aggregation = None

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

    # Facet-href builder is passed as a per-request context variable
    # (NOT attached to `templates.env.globals`). Code-review H1 /
    # BH-37 / EC-43 — env.globals is a module-level dict and mutating
    # it per request races under concurrent HTMX requests: request A
    # can render with request B's builder and produce URLs that reflect
    # the wrong facet selection.
    build_facet_href = _facet_href_builder(facets, "/journal")

    # Current URL query string (minus `page` / `expand`) — the hero
    # block's CSV link re-uses it, and the "Save preset" JS reads it
    # from `window.location`.
    query_items: list[tuple[str, str]] = []
    for name, values in facets.items():
        for v in values:
            query_items.append((name, v))
    current_query = urlencode(query_items)

    context = await _base_context(request)
    context.update(
        {
            "active_route": "journal",
            "page": journal_page_data,
            "expand_id": expand,
            "expansion": expansion_context,
            "facet_selections": facet_selections,
            "has_any_filter": any(facets.values()),
            "aggregation": aggregation,
            "sparkline_svg": sparkline_svg,
            "prose_text": render_query_prose(facets),
            "current_query": current_query,
            "build_facet_href": build_facet_href,
        }
    )
    return templates.TemplateResponse(request, "pages/journal.html", context)


@router.get("/journal/calendar", include_in_schema=False)
async def calendar_page(
    request: Request,
    year: int = Query(default=None, ge=1970, le=2100),
    month: int = Query(default=None, ge=1, le=12),
):
    """Story 4.4 — monthly P&L calendar.

    Defaults to the current UTC month. Clicking a cell links back to
    `/journal?date=YYYY-MM-DD`.

    Code-review M8 / BH-16 / EC-16: year/month are Query-bounded so
    `?month=13` or `?year=-5000` return 422 instead of 500ing
    `datetime(year, month, 1)`.
    """

    now = datetime.now(UTC)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    db_pool = getattr(request.app.state, "db_pool", None)
    cells: dict = {}
    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                cells = await get_daily_pnl(conn, year=year, month=month)
        except Exception as exc:  # noqa: BLE001
            logger.warning("calendar_page.db_error", error=str(exc))
            cells = {}

    days = iter_month_days(year, month)
    today = now.date()

    prev_year = year if month > 1 else year - 1
    prev_month = month - 1 if month > 1 else 12
    next_year = year if month < 12 else year + 1
    next_month = month + 1 if month < 12 else 1

    context = await _base_context(request)
    context.update(
        {
            "active_route": "journal",
            "year": year,
            "month": month,
            "days": days,
            "cells": cells,
            "today": today,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
        }
    )
    return templates.TemplateResponse(request, "pages/calendar.html", context)


@router.get("/journal/export", include_in_schema=False)
async def journal_csv_export(request: Request):
    """Story 4.7 — download the current facet-filtered trade list as CSV.

    Returns `text/csv` with a UTF-8 BOM so Excel auto-detects encoding.
    """

    from fastapi.responses import Response

    db_pool = getattr(request.app.state, "db_pool", None)
    facets = _parse_facet_query(request)

    body = ""
    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                body = await export_trades_csv(conn, facets)
        except Exception as exc:  # noqa: BLE001
            logger.warning("journal_export.db_error", error=str(exc))
            body = "\ufeff"  # BOM only

    filename = f"ctrader-trades-{datetime.now(UTC).strftime('%Y-%m-%d')}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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

    context = await _base_context(request)
    context.update(
        {
            "active_route": "journal",
            "rows": rows,
            "tag_labels": tag_labels,
            "window": window,
            "window_start": window_start,
            "window_end": window_end,
            "total_trades": total_trades or 0,
        }
    )
    return templates.TemplateResponse(request, "pages/mistakes_report.html", context)


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
