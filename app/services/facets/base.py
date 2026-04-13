"""Base types for the facet framework (Story 4.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import asyncpg


@dataclass(frozen=True)
class FacetValue:
    """One clickable value inside a facet (e.g., 'stock' under asset_class)."""

    id: str
    label: str
    count: int
    selected: bool = False


@dataclass(frozen=True)
class FacetSelection:
    """A rendered facet + its currently-selected values, ready for the template."""

    name: str
    label: str
    values: list[FacetValue]
    available: bool = True

    @property
    def has_active_selection(self) -> bool:
        return any(v.selected for v in self.values)


class Facet(Protocol):
    """Runtime interface each facet must satisfy.

    Facets are stateless — all per-request state (selection, counts)
    lives in the `FacetSelection` returned by `materialize`.
    """

    name: str
    label: str

    async def is_available(self, conn: asyncpg.Connection | None) -> bool: ...

    async def get_values(
        self,
        conn: asyncpg.Connection,
        *,
        where_sql: str,
        where_args: list[Any],
    ) -> list[tuple[str, int]]: ...

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[Any]]: ...

    def label_for(self, value_id: str) -> str: ...


@dataclass
class BaseFacet:
    """Concrete base class that handles the common plumbing — availability
    check via `_availability_probe_sql`, `sql_condition` via the `ANY($N)`
    idiom, `label_for` with an optional label map.

    Subclasses only need to set `name`, `label`, and provide a
    `_values_sql` template.
    """

    name: str = ""
    label: str = ""
    _values_sql: str = ""
    _availability_probe_sql: str | None = None
    _label_map: dict[str, str] = field(default_factory=dict)

    async def is_available(self, conn: asyncpg.Connection | None) -> bool:
        """Default: available if the backing column returns at least one
        non-null value under the current filter. Subclasses can override
        for cheaper probes (e.g., strategy facet probes the `strategies`
        table existence)."""

        if conn is None:
            return False
        if self._availability_probe_sql is None:
            # No custom probe → always report available and rely on
            # `get_values` returning an empty list.
            return True
        try:
            value = await conn.fetchval(self._availability_probe_sql)
            return bool(value)
        except Exception:  # noqa: BLE001 — availability must never crash
            return False

    async def get_values(
        self,
        conn: asyncpg.Connection,
        *,
        where_sql: str,
        where_args: list[Any],
    ) -> list[tuple[str, int]]:
        """Run `_values_sql` with the composed WHERE and return `(id, count)`
        tuples. Subclasses can override entirely if the values come from
        somewhere other than the trades table."""

        sql = self._values_sql.format(where_sql=where_sql or "1=1")
        rows = await conn.fetch(sql, *where_args)
        return [(row["value"], int(row["count"])) for row in rows if row["value"] is not None]

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[Any]]:
        """Default: `<column> = ANY($N)` with the facet's `name` as the
        column. Override for JSONB-sourced facets.
        """

        if not selected:
            return "", []
        fragment = f"{self.name} = ANY(${placeholder_start})"
        return fragment, [selected]

    def label_for(self, value_id: str) -> str:
        return self._label_map.get(value_id, value_id.replace("_", " ").title())
