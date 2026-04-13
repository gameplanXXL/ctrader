"""Asset-class facet — `stock`, `option`, `crypto`, `cfd`."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.facets.base import BaseFacet

_LABELS = {
    "stock": "Stock",
    "option": "Option",
    "crypto": "Crypto",
    "cfd": "CFD",
}

_VALUES_SQL = """
SELECT asset_class AS value, COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
 GROUP BY asset_class
 ORDER BY count DESC, asset_class ASC
"""


@dataclass
class AssetClassFacet(BaseFacet):
    name: str = "asset_class"
    label: str = "Asset"
    _values_sql: str = _VALUES_SQL
    _label_map: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._label_map is None:
            self._label_map = dict(_LABELS)
