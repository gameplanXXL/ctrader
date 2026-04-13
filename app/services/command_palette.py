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

from app.logging import get_logger
from app.services.query_presets import list_presets
from app.services.strategy_source import list_strategies_for_dropdown

logger = get_logger(__name__)


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


_RECENT_TRADES_SQL = """
SELECT id, symbol, side, opened_at
  FROM trades
 ORDER BY opened_at DESC, id DESC
 LIMIT $1
"""


async def build_palette_items(
    conn: asyncpg.Connection | None,
) -> list[dict[str, Any]]:
    """Return a flat JSON-ready list for the palette.

    Static routes always appear. Strategies, saved presets, and recent
    trade ids are loaded if the DB is reachable — otherwise we serve
    static routes only (graceful degradation so Ctrl+K is always
    useful).

    Code-review M5 / Auditor 4.6 AC #2: previously only routes + presets
    were indexed; spec explicitly lists strategies and trade ids.
    """

    items: list[PaletteItem] = get_static_routes()

    if conn is None:
        return [asdict(item) for item in items]

    # Saved query presets → "Saved Queries" category.
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
    except Exception as exc:  # noqa: BLE001
        logger.warning("command_palette.presets_failed", error=str(exc))

    # Strategy entries — `list_strategies_for_dropdown` handles the
    # pre-Epic-6 fallback to taxonomy.yaml via the same adapter the
    # tagging form uses. Deep-link into a filtered journal view.
    try:
        strategies = await list_strategies_for_dropdown(conn)
        for sid, label in strategies:
            items.append(
                PaletteItem(
                    id=f"strategy-{sid}",
                    label=label,
                    url=f"/journal?strategy={sid}",
                    category="Strategies",
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("command_palette.strategies_failed", error=str(exc))

    # Recent trades — top 25 by opened_at. Chef can type the symbol
    # or a fragment of the trade id.
    try:
        rows = await conn.fetch(_RECENT_TRADES_SQL, 25)
        for row in rows:
            items.append(
                PaletteItem(
                    id=f"trade-{row['id']}",
                    label=f"#{row['id']} · {row['symbol']} · {row['side']}",
                    url=f"/journal?expand={row['id']}",
                    category="Recent Trades",
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("command_palette.trades_failed", error=str(exc))

    return [asdict(item) for item in items]
