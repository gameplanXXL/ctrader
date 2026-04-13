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

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Resolve templates directory once at import time.
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


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
async def journal_page(request: Request):
    return _render(request, "journal")


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
