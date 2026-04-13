"""Placeholder facets — registered now so they light up automatically
once their data source lands in later epics.

All five return `is_available=False` until the backing column/table
exists; the facet bar then hides them (Story 4.1 AC #2, graceful
degradation).
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from app.services.facets.base import BaseFacet

_STRATEGY_VALUES_SQL = """
SELECT trigger_spec->>'strategy' AS value, COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
   AND trigger_spec ? 'strategy'
 GROUP BY trigger_spec->>'strategy'
 ORDER BY count DESC
"""

_STRATEGY_PROBE_SQL = """
SELECT EXISTS (
    SELECT 1 FROM trades WHERE trigger_spec ? 'strategy' LIMIT 1
)
"""


@dataclass
class StrategyFacet(BaseFacet):
    """Strategy facet — reads `trigger_spec->>'strategy'` today, will
    switch to the `strategies` table FK in Epic 6."""

    name: str = "strategy"
    label: str = "Strategy"
    _values_sql: str = _STRATEGY_VALUES_SQL
    _availability_probe_sql: str | None = _STRATEGY_PROBE_SQL

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[object]]:
        if not selected:
            return "", []
        fragment = f"trigger_spec->>'strategy' = ANY(${placeholder_start})"
        return fragment, [selected]


_TRIGGER_VALUES_SQL = """
SELECT trigger_spec->>'trigger_type' AS value, COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
   AND trigger_spec ? 'trigger_type'
 GROUP BY trigger_spec->>'trigger_type'
 ORDER BY count DESC
"""

_TRIGGER_PROBE_SQL = """
SELECT EXISTS (
    SELECT 1 FROM trades WHERE trigger_spec ? 'trigger_type' LIMIT 1
)
"""


@dataclass
class TriggerSourceFacet(BaseFacet):
    """Trigger-type facet — sourced from the tagging form."""

    name: str = "trigger_type"
    label: str = "Trigger"
    _values_sql: str = _TRIGGER_VALUES_SQL
    _availability_probe_sql: str | None = _TRIGGER_PROBE_SQL

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[object]]:
        if not selected:
            return "", []
        fragment = f"trigger_spec->>'trigger_type' = ANY(${placeholder_start})"
        return fragment, [selected]


_FOLLOWED_PROBE_SQL = """
SELECT EXISTS (
    SELECT 1 FROM trades WHERE trigger_spec ? 'followed' LIMIT 1
)
"""

_FOLLOWED_VALUES_SQL = """
SELECT
    CASE
        WHEN (trigger_spec->>'followed')::boolean THEN 'followed'
        ELSE 'override'
    END AS value,
    COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
   AND trigger_spec ? 'followed'
 GROUP BY value
 ORDER BY count DESC
"""


@dataclass
class FollowedFacet(BaseFacet):
    """`followed` vs `override` — only surfaces when at least one tagged
    trade carries an explicit followed flag (bot-sourced trades)."""

    name: str = "followed"
    label: str = "Followed"
    _values_sql: str = _FOLLOWED_VALUES_SQL
    _availability_probe_sql: str | None = _FOLLOWED_PROBE_SQL
    _label_map: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._label_map is None:
            self._label_map = {"followed": "Followed", "override": "Override"}

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[object]]:
        if not selected:
            return "", []
        # Map ids back to booleans.
        bools = [v == "followed" for v in selected]
        fragment = f"(trigger_spec->>'followed')::boolean = ANY(${placeholder_start})"
        return fragment, [bools]


@dataclass
class ConfidenceBandFacet(BaseFacet):
    """Placeholder — confidence binning will land once we have enough
    data to see meaningful buckets. Today reports unavailable so the
    chip is hidden."""

    name: str = "confidence_band"
    label: str = "Confidence"
    _values_sql: str = "SELECT NULL AS value, 0 AS count WHERE FALSE"

    async def is_available(self, conn: asyncpg.Connection | None) -> bool:
        return False


@dataclass
class RegimeTagFacet(BaseFacet):
    """Placeholder until Epic 9 ships the `regime_snapshots` table."""

    name: str = "regime_tag"
    label: str = "Regime"
    _values_sql: str = "SELECT NULL AS value, 0 AS count WHERE FALSE"

    async def is_available(self, conn: asyncpg.Connection | None) -> bool:
        if conn is None:
            return False
        try:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                     WHERE table_schema = 'public'
                       AND table_name = 'regime_snapshots'
                )
                """
            )
        except Exception:  # noqa: BLE001
            return False
        return bool(exists)
