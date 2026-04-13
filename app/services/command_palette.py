"""Command palette data source (Story 4.6).

Produces the JSON blob the frontend palette consumes — static routes
plus dynamic items (strategies, saved query presets, recent trade ids).

Fuzzy matching is done client-side (simple substring for Phase 1) so
we don't need a server round-trip per keystroke.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import asyncpg

from app.services.query_presets import list_presets


@dataclass(frozen=True)
class PaletteItem:
    id: str
    label: str
    url: str
    category: str
    hint: str | None = None


_STATIC_ROUTES: list[PaletteItem] = [
    PaletteItem("route-journal", "Journal", "/journal", "Navigation", hint="G J"),
    PaletteItem("route-mistakes", "Top Mistakes", "/journal/mistakes", "Navigation"),
    PaletteItem("route-strategies", "Strategies", "/strategies", "Navigation", hint="G S"),
    PaletteItem("route-approvals", "Approvals", "/approvals", "Navigation", hint="G A"),
    PaletteItem("route-trends", "Trends", "/trends", "Navigation", hint="G T"),
    PaletteItem("route-regime", "Regime", "/regime", "Navigation", hint="G R"),
    PaletteItem("route-settings", "Settings", "/settings", "Navigation"),
]


def get_static_routes() -> list[PaletteItem]:
    return list(_STATIC_ROUTES)


async def build_palette_items(
    conn: asyncpg.Connection | None,
) -> list[dict[str, Any]]:
    """Return a flat JSON-ready list for the palette.

    Static routes always appear. Presets are loaded if the DB is
    reachable — otherwise we serve static routes only (graceful
    degradation so Ctrl+K is always useful).
    """

    items: list[PaletteItem] = get_static_routes()

    if conn is not None:
        try:
            presets = await list_presets(conn, limit=50)
            for preset in presets:
                items.append(
                    PaletteItem(
                        id=f"preset-{preset.id}",
                        label=preset.name,
                        url=f"/journal?{preset.to_query_string()}",
                        category="Saved Queries",
                    )
                )
        except Exception:  # noqa: BLE001 — never break the palette over DB hiccups
            pass

    return [asdict(item) for item in items]
