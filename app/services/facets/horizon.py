"""Horizon facet — sourced from `trigger_spec->>'horizon'`.

Only tagged trades carry a horizon, so the facet availability tracks
whether the trades table has any trigger_spec rows with a horizon key.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.facets.base import BaseFacet

_LABELS = {
    "intraday": "Intraday",
    "swing_short": "Short Swing",
    "swing_long": "Long Swing",
    "position": "Position",
}

_VALUES_SQL = """
SELECT trigger_spec->>'horizon' AS value, COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
   AND trigger_spec ? 'horizon'
 GROUP BY trigger_spec->>'horizon'
 ORDER BY count DESC, value ASC
"""

_PROBE_SQL = """
SELECT EXISTS (
    SELECT 1 FROM trades
     WHERE trigger_spec ? 'horizon'
     LIMIT 1
)
"""


@dataclass
class HorizonFacet(BaseFacet):
    name: str = "horizon"
    label: str = "Horizon"
    _values_sql: str = _VALUES_SQL
    _availability_probe_sql: str | None = _PROBE_SQL
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
        if not selected:
            return "", []
        # JSONB key lookup — text extraction for ANY-match.
        fragment = f"trigger_spec->>'horizon' = ANY(${placeholder_start})"
        return fragment, [selected]
