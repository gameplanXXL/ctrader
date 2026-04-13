"""Strategy dropdown source adapter (Story 3.1 / Concern m2).

Before Epic 6 the `strategies` table does not exist yet. The tagging
form still needs a non-empty strategy dropdown, so we fall back to the
`strategy_categories` section of `taxonomy.yaml`.

Once Epic 6 Story 6.1 lands and creates the strategies table, this
adapter starts returning user-defined strategy rows instead. The
caller (tagging form) shouldn't care which side of the migration
they're on.

Return shape is a list of `(id, label)` tuples so the template can
iterate without touching Pydantic or asyncpg.Record semantics.
"""

from __future__ import annotations

import asyncpg

from app.logging import get_logger
from app.services.taxonomy import get_taxonomy

logger = get_logger(__name__)


_STRATEGIES_EXIST_SQL = """
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
     WHERE table_schema = 'public' AND table_name = 'strategies'
)
"""

# Epic 6 hasn't landed yet, but we already know the column names we'll
# need — keeping the query close to the table shape so the flip is a
# one-liner later.
_STRATEGIES_LIST_SQL = """
SELECT id::text AS id, name AS label
  FROM strategies
 WHERE status = 'active'
 ORDER BY name
"""


async def list_strategies_for_dropdown(
    conn: asyncpg.Connection | None,
) -> list[tuple[str, str]]:
    """Return `[(id, label), ...]` for the tagging form's strategy dropdown.

    If `conn` is None, or the `strategies` table doesn't exist yet,
    fall back to `taxonomy.strategy_categories`. Either case is
    non-fatal — the form must stay usable.
    """

    if conn is not None:
        try:
            exists = await conn.fetchval(_STRATEGIES_EXIST_SQL)
            if exists:
                rows = await conn.fetch(_STRATEGIES_LIST_SQL)
                if rows:
                    return [(str(row["id"]), row["label"]) for row in rows]
        except Exception as exc:  # noqa: BLE001 — never break the form
            logger.warning(
                "strategy_source.db_probe_failed",
                error=str(exc),
                exception_type=type(exc).__name__,
            )

    taxonomy = get_taxonomy()
    return [(entry.id, entry.label or entry.id) for entry in taxonomy.strategy_categories]
