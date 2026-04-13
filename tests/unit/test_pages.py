"""Story 1.5 — page-shell smoke tests.

Verifies that all six top-level nav routes render 200, inherit the base
template (topbar visible), and mark the correct nav link as active via
`aria-current="page"`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

PAGES = [
    ("/journal", "journal", "Journal"),
    ("/strategies", "strategies", "Strategies"),
    ("/approvals", "approvals", "Approvals"),
    ("/trends", "trends", "Trends"),
    ("/regime", "regime", "Regime"),
    ("/settings", "settings", "Settings"),
]


@pytest.mark.parametrize(("path", "slug", "label"), PAGES)
def test_page_shell_renders_200(client: TestClient, path: str, slug: str, label: str) -> None:
    """Every nav route returns 200 and shows the page-specific H1."""

    response = client.get(path)
    assert response.status_code == 200

    body = response.text
    assert "ctrader" in body
    # Story 2.3 replaced the journal page-shell H1 with a dedicated
    # journal__title class. Other shells still use page-title.
    assert (
        f'<h1 class="page-title">{label}</h1>' in body
        or f'<h1 class="journal__title">{label}</h1>' in body
    )


@pytest.mark.parametrize(("path", "slug", "label"), PAGES)
def test_active_nav_link_marked(client: TestClient, path: str, slug: str, label: str) -> None:
    """The link for the current route carries `aria-current="page"`."""

    response = client.get(path)
    body = response.text
    # The active link template renders: `aria-current="page"` on the <a>
    # whose href matches the current route.
    assert f'href="{path}"\n         class="nav-link"\n         aria-current="page"' in body


def test_topbar_contains_all_nav_items(client: TestClient) -> None:
    """Top-bar shows all six nav items on every page."""

    response = client.get("/journal")
    body = response.text
    for _, _, label in PAGES:
        assert label in body


def test_topbar_has_no_hamburger(client: TestClient) -> None:
    """UX-DR82: no hamburger icon, no drawer markup."""

    response = client.get("/journal")
    body = response.text.lower()
    for forbidden in ("hamburger", "drawer", "tab-bar"):
        assert forbidden not in body


def test_base_layout_includes_compiled_css(client: TestClient) -> None:
    """base.html links to the Tailwind-compiled stylesheet (absolute URL)."""

    response = client.get("/journal")
    assert "/static/css/compiled.css" in response.text


def test_base_layout_loads_viewport_guard(client: TestClient) -> None:
    """base.html includes the viewport-guard script (absolute URL)."""

    response = client.get("/journal")
    assert "/static/js/viewport-guard.js" in response.text
