"""Facet registry + SQL-composition helpers (Story 4.1).

`get_registry()` returns the canonical ordered list of facets. The
Journal route calls `render_facets(conn, selections)` to materialize
every facet with per-value counts under the currently-active
filter set, and `build_where_clause(selections)` to translate the
URL query params into a parameterized WHERE fragment that
`trade_query.list_trades` can splice into its SQL.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from app.logging import get_logger
from app.services.facets.agent import AgentFacet
from app.services.facets.asset_class import AssetClassFacet
from app.services.facets.base import Facet, FacetSelection, FacetValue
from app.services.facets.broker import BrokerFacet
from app.services.facets.horizon import HorizonFacet
from app.services.facets.placeholders import (
    ConfidenceBandFacet,
    FollowedFacet,
    RegimeTagFacet,
    StrategyFacet,
    TriggerSourceFacet,
)

logger = get_logger(__name__)


class FacetRegistry:
    """Ordered list of facets. Keeps the render order stable across requests."""

    def __init__(self, facets: list[Facet]) -> None:
        self._facets = facets
        self._by_name = {f.name: f for f in facets}

    def __iter__(self):
        return iter(self._facets)

    def get(self, name: str) -> Facet | None:
        return self._by_name.get(name)

    @property
    def names(self) -> list[str]:
        return [f.name for f in self._facets]


_DEFAULT_ORDER: list[type] = [
    AssetClassFacet,
    BrokerFacet,
    AgentFacet,
    HorizonFacet,
    StrategyFacet,
    TriggerSourceFacet,
    FollowedFacet,
    ConfidenceBandFacet,
    RegimeTagFacet,
]


def get_registry() -> FacetRegistry:
    """Build a fresh registry per-request.

    Facets are plain dataclasses — constructing them is cheap, and
    per-request construction means tests can swap in mocked registries
    without reaching for a module-level singleton.
    """

    return FacetRegistry([cls() for cls in _DEFAULT_ORDER])


def build_where_clause(
    selections: dict[str, list[str]],
) -> tuple[str, list[Any]]:
    """Translate the URL query-param dict into a parameterized WHERE
    fragment.

    Returns `(sql_fragment, params)`. The fragment starts with a
    placeholder-index of `$1` and the caller is expected to splice it
    into a larger query that doesn't use `$1` itself.

    Example:
        `{"asset_class": ["stock"], "broker": ["ib"]}` →
        `("asset_class = ANY($1) AND broker = ANY($2::trade_source[])",
          [["stock"], ["ib"]])`
    """

    registry = get_registry()
    fragments: list[str] = []
    params: list[Any] = []
    placeholder = 1

    for name, values in selections.items():
        if not values:
            continue
        facet = registry.get(name)
        if facet is None:
            logger.warning("facets.unknown_name", name=name)
            continue
        fragment, fragment_params = facet.sql_condition(values, placeholder_start=placeholder)
        if not fragment:
            continue
        fragments.append(fragment)
        params.extend(fragment_params)
        placeholder += len(fragment_params)

    where_sql = " AND ".join(fragments) if fragments else "1=1"
    return where_sql, params


async def render_facets(
    conn: asyncpg.Connection | None,
    selections: dict[str, list[str]],
) -> list[FacetSelection]:
    """Render every facet in registry order with per-value counts.

    Counts are computed against the *current* filter set, so clicking
    a value narrows the other facets' counts — the typical drill-in
    UX pattern.

    If `conn` is None (test / degraded), every facet renders as
    unavailable and no counts are produced.
    """

    registry = get_registry()
    out: list[FacetSelection] = []

    for facet in registry:
        available = await facet.is_available(conn)
        if not available or conn is None:
            out.append(
                FacetSelection(
                    name=facet.name,
                    label=facet.label,
                    values=[],
                    available=False,
                )
            )
            continue

        # Build the WHERE for this facet's count query, but EXCLUDE the
        # facet itself from the WHERE — otherwise selecting "stock"
        # would hide every other asset_class value, trapping the user.
        other_selections = {k: v for k, v in selections.items() if k != facet.name and v}
        where_sql, where_args = build_where_clause(other_selections)

        try:
            raw = await facet.get_values(conn, where_sql=where_sql, where_args=where_args)
        except Exception as exc:  # noqa: BLE001
            logger.warning("facets.get_values_failed", facet=facet.name, error=str(exc))
            raw = []

        selected_ids = set(selections.get(facet.name, []) or [])
        values = [
            FacetValue(
                id=vid,
                label=facet.label_for(vid),
                count=count,
                selected=vid in selected_ids,
            )
            for vid, count in raw
        ]
        # Also include any selected value that doesn't appear in the
        # counts (e.g., URL param for a value that no longer has any
        # matching rows) so the chip stays clickable.
        for sid in selected_ids:
            if not any(v.id == sid for v in values):
                values.append(
                    FacetValue(
                        id=sid,
                        label=facet.label_for(sid),
                        count=0,
                        selected=True,
                    )
                )

        out.append(
            FacetSelection(
                name=facet.name,
                label=facet.label,
                values=values,
                available=True,
            )
        )

    return out
