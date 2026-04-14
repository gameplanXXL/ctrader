"""Settings + system-health routes (Epic 11).

- `GET /settings` — the Settings page: health widget + backup section
  + read-only taxonomy preview + MCP configuration summary.
- `GET /api/health` — HTMX-polled health payload (returns a small
  HTML fragment, not JSON, so the top-bar status dots can live-
  update via `hx-get` + `hx-swap="outerHTML"`).
- `GET /settings/backup/download` — stream the most recent
  `ctrader-*.sql.gz` to the operator's browser. NFR-S2 keeps this
  safe (server binds to 127.0.0.1 only).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.services.db_backup import get_backup_info
from app.services.health import collect_health

logger = get_logger(__name__)

router = APIRouter(tags=["settings"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for _name, _fn in JINJA_FILTERS.items():
    templates.env.filters[_name] = _fn


async def _load_health(request: Request):
    """Shared loader for /settings page + /api/health fragment."""

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        return None

    async with db_pool.acquire() as conn:
        return await collect_health(
            conn,
            ib_available=getattr(request.app.state, "ib_available", False),
            mcp_client=getattr(request.app.state, "mcp_client", None),
            mcp_available=getattr(request.app.state, "mcp_available", False),
            ctrader_client=getattr(request.app.state, "ctrader_client", None),
            ib_quick_order_client=getattr(request.app.state, "ib_quick_order_client", None),
        )


@router.get("/api/health", include_in_schema=False)
async def api_health(request: Request):
    """Full health-widget fragment. Reused by the Settings page and
    any future HTMX poller that wants the whole payload (job runs +
    contract test + backup metadata + dots).
    """

    health = await _load_health(request)
    return templates.TemplateResponse(
        request,
        "fragments/health_widget.html",
        {"health": health, "compact": False},
    )


@router.get("/api/health/dots", include_in_schema=False)
async def api_health_dots(request: Request):
    """Tiny dots-only fragment used by the top-bar HTMX poller
    (Story 11.2 AC #2 + AC #3 / Code-review H9 + H10 / EC-5 + EC-6).

    Under 1KB so the 5-second poll stays cheap. Returns only the
    three integration dots — the full widget lives on the Settings
    page via the `/api/health` endpoint.
    """

    health = await _load_health(request)
    return templates.TemplateResponse(
        request,
        "fragments/topbar_health_dots.html",
        {"health": health},
    )


@router.get("/settings/backup/download", include_in_schema=False)
async def download_backup(request: Request):
    """Story 11.3 AC #4 — download the latest PostgreSQL backup file.

    NFR-S2: the server binds to 127.0.0.1 only, so this endpoint is
    implicitly localhost-gated. Future auth work would add a stricter
    check here.
    """

    info = get_backup_info()
    if info is None:
        raise HTTPException(
            status_code=404,
            detail="No backup file available yet — run the db_backup job first",
        )
    return FileResponse(
        info.path,
        filename=info.path.name,
        media_type="application/gzip",
    )
