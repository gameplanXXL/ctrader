"""JSON API routes — command palette, query presets (Stories 4.6, 4.7),
MCP health status (Story 5.3), on-demand contract test (Story 5.4).

These endpoints return plain JSON (not HTML fragments), so they sit
in their own router instead of sharing `trades.py` or `pages.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.services.command_palette import build_palette_items
from app.services.mcp_contract_test import run_contract_test
from app.services.mcp_health import get_all_agents
from app.services.query_presets import list_presets, save_preset

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

# Share a Jinja env for the tiny HTML fragments /api/mcp-status
# returns to the staleness-banner HTMX polling.
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for _name, _fn in JINJA_FILTERS.items():
    _templates.env.filters[_name] = _fn


@router.get("/command-palette")
async def command_palette_items(request: Request) -> JSONResponse:
    """Return the full palette item list (static routes + presets).

    Story 4.6 / FR59. Graceful: if the DB is down the static routes
    still render so Ctrl+K keeps working.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    items: list[dict[str, Any]] = []
    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                items = await build_palette_items(conn)
        except Exception as exc:  # noqa: BLE001
            logger.warning("api.command_palette.db_error", error=str(exc))
            items = await build_palette_items(None)
    else:
        items = await build_palette_items(None)
    return JSONResponse(items)


# Code-review M10 / BH-25: whitelist the facet keys a preset is
# allowed to store. Without this, a crafted POST could persist
# arbitrary JSONB keys that surface in the command palette.
# Mirror the set from `pages._FACET_KEYS` — kept local to avoid a
# circular import between api.py and pages.py.
_ALLOWED_FACET_KEYS = {
    "asset_class",
    "broker",
    "horizon",
    "strategy",
    "trigger_type",
    "followed",
    "confidence_band",
    "regime_tag",
}


class PresetPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    filters: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def _validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty / whitespace")
        return stripped

    def cleaned_filters(self) -> dict[str, list[str]]:
        """Return a copy of `filters` with only whitelisted facet keys
        and non-empty value lists. Raises `ValueError` if nothing
        survives (empty presets are useless and confuse the palette).
        """

        cleaned: dict[str, list[str]] = {}
        for key, values in self.filters.items():
            if key not in _ALLOWED_FACET_KEYS:
                continue
            trimmed = [str(v).strip() for v in values if str(v).strip()]
            if trimmed:
                cleaned[key] = trimmed
        if not cleaned:
            raise ValueError("filters must contain at least one facet value")
        return cleaned


@router.post("/presets")
async def save_query_preset(request: Request, payload: PresetPayload) -> JSONResponse:
    """Story 4.7 / FR61 — upsert a saved query preset.

    Code-review M10/M11: validate the payload's facet keys against the
    whitelist and reject empty-filter presets (they'd surface in the
    command palette as no-op entries).
    """

    try:
        name = PresetPayload._validate_name(payload.name)
        cleaned_filters = payload.cleaned_filters()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    try:
        async with db_pool.acquire() as conn:
            preset = await save_preset(conn, name, cleaned_filters)
    except Exception as exc:  # noqa: BLE001
        logger.warning("api.presets.save_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="could not save preset") from None

    return JSONResponse(
        {
            "id": preset.id,
            "name": preset.name,
            "filters": preset.filters,
            "created_at": preset.created_at.isoformat(),
        }
    )


@router.get("/mcp-status", include_in_schema=False)
async def mcp_status_fragment(request: Request):
    """Story 5.3 — HTMX polling target for the staleness banner.

    Returns the rendered banner HTML (or an empty stub when nothing
    is degraded). Polling cadence is 60s, configured in the macro.
    """

    agents = get_all_agents()
    return _templates.TemplateResponse(
        request,
        "fragments/mcp_status_banner.html",
        {"mcp_agents": agents},
    )


@router.post("/mcp-contract-test", include_in_schema=False)
async def run_mcp_contract_test(request: Request) -> JSONResponse:
    """Story 5.4 — on-demand contract test runner.

    Intended for the settings page + CLI path. Story 12.1's scheduler
    will call the same `run_contract_test()` function nightly.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    mcp_client = getattr(request.app.state, "mcp_client", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    async with db_pool.acquire() as conn:
        report = await run_contract_test(conn, mcp_client)
    # Code-review H5: a report that couldn't be persisted is a
    # half-success — the drift banner on the next page load will
    # show stale state. Return 500 so the caller knows the audit
    # trail is broken.
    status_code = 200 if report.persisted else 500
    return JSONResponse(report.to_dict(), status_code=status_code)


@router.get("/presets")
async def list_query_presets(request: Request) -> JSONResponse:
    db_pool = getattr(request.app.state, "db_pool", None)
    presets: list[dict[str, Any]] = []
    if db_pool is not None and hasattr(db_pool, "acquire"):
        try:
            async with db_pool.acquire() as conn:
                rows = await list_presets(conn)
                presets = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "filters": p.filters,
                        "created_at": p.created_at.isoformat(),
                    }
                    for p in rows
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("api.presets.list_failed", error=str(exc))
    return JSONResponse(presets)
