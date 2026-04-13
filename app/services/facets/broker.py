"""Broker facet — `ib`, `ctrader`."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.facets.base import BaseFacet

_LABELS = {"ib": "Interactive Brokers", "ctrader": "cTrader"}

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
        """`broker` is a PG enum — cast the `ANY` expression."""

        if not selected:
            return "", []
        fragment = f"broker = ANY(${placeholder_start}::trade_source[])"
        return fragment, [selected]
