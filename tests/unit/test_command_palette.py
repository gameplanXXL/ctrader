"""Unit tests for command_palette.py (Story 4.6)."""

from __future__ import annotations

import pytest

from app.services.command_palette import build_palette_items, get_static_routes


def test_static_routes_contains_canonical_pages() -> None:
    routes = get_static_routes()
    urls = {r.url for r in routes}
    assert "/journal" in urls
    assert "/strategies" in urls
    assert "/approvals" in urls
    assert "/trends" in urls
    assert "/regime" in urls
    assert "/settings" in urls
    assert "/journal/mistakes" in urls


@pytest.mark.asyncio
async def test_build_palette_items_without_db_returns_static_only() -> None:
    """DB unavailable → palette still serves navigation routes."""

    items = await build_palette_items(None)
    assert len(items) >= 7
    categories = {item["category"] for item in items}
    assert "Navigation" in categories
