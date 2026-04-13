"""Saved query presets (Story 4.7 / FR61).

Minimal CRUD around the `query_presets` table. Presets are stored as
`(name, filters)` where `filters` is the URL-query-param form the
facet framework already understands. Loading a preset reconstructs
the query-string and redirects Chef to `/journal?...`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import asyncpg


@dataclass(frozen=True)
class QueryPreset:
    id: int
    name: str
    filters: dict[str, list[str]]
    created_at: datetime

    def to_query_string(self) -> str:
        """Rebuild the URL query string so the journal route can replay
        the preset as if Chef had clicked every chip by hand."""

        flat: list[tuple[str, str]] = []
        for key, values in self.filters.items():
            for value in values:
                flat.append((key, value))
        return urlencode(flat)


_INSERT_SQL = """
INSERT INTO query_presets (name, filters)
VALUES ($1, $2)
ON CONFLICT (name) DO UPDATE SET filters = EXCLUDED.filters
RETURNING id, name, filters, created_at
"""

_LIST_SQL = """
SELECT id, name, filters, created_at
  FROM query_presets
 ORDER BY created_at DESC
 LIMIT $1
"""

_GET_SQL = """
SELECT id, name, filters, created_at
  FROM query_presets
 WHERE id = $1
"""


def _row_to_preset(row: asyncpg.Record) -> QueryPreset:
    filters = row["filters"] or {}
    # Normalize: values may come in as a bare string or a list.
    normalized: dict[str, list[str]] = {}
    for k, v in filters.items():
        if isinstance(v, list):
            normalized[k] = [str(x) for x in v]
        elif v is None:
            normalized[k] = []
        else:
            normalized[k] = [str(v)]
    return QueryPreset(
        id=int(row["id"]),
        name=str(row["name"]),
        filters=normalized,
        created_at=row["created_at"],
    )


async def save_preset(
    conn: asyncpg.Connection,
    name: str,
    filters: dict[str, list[str]],
) -> QueryPreset:
    """Upsert a preset — re-saving under the same name overwrites."""

    row = await conn.fetchrow(_INSERT_SQL, name, filters)
    return _row_to_preset(row)


async def list_presets(conn: asyncpg.Connection, *, limit: int = 100) -> list[QueryPreset]:
    rows = await conn.fetch(_LIST_SQL, limit)
    return [_row_to_preset(row) for row in rows]


async def get_preset(conn: asyncpg.Connection, preset_id: int) -> QueryPreset | None:
    row = await conn.fetchrow(_GET_SQL, preset_id)
    return _row_to_preset(row) if row is not None else None
