"""Broker facet — `ib`, `ctrader`."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.facets.base import BaseFacet

_LABELS = {"ib": "Interactive Brokers", "ctrader": "cTrader"}

# Code-review H4 / BH-3: allowlist for the `trade_source` enum.
# Without this, a crafted URL like `?broker=alpaca` drops straight
# into a Postgres `invalid input value for enum trade_source: "alpaca"`
# 500 (bubbled up to the outer journal-page try/except, which then
# blanks the whole page). Intersect with the known-good set before
# any SQL binding.
_VALID_BROKERS = frozenset(_LABELS.keys())

_VALUES_SQL = """
SELECT broker::text AS value, COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
 GROUP BY broker
 ORDER BY count DESC, broker ASC
"""


@dataclass
class BrokerFacet(BaseFacet):
    name: str = "broker"
    label: str = "Broker"
    _values_sql: str = _VALUES_SQL
    _label_map: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._label_map is None:
            self._label_map = dict(_LABELS)

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[object]]:
        """`broker` is a PG enum — cast the `ANY` expression.

        Code-review H4: filter the selection through the enum allowlist
        first so unknown values (typo / crafted URL) don't reach the
        Postgres enum coercion.
        """

        valid = [v for v in selected if v in _VALID_BROKERS]
        if not valid:
            return "", []
        fragment = f"broker = ANY(${placeholder_start}::trade_source[])"
        return fragment, [valid]
