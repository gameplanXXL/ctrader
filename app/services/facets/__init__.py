"""Facet filter framework (Story 4.1 / FR10).

A **facet** is a dimension Chef can slice the trade list on — asset
class, broker, horizon, strategy, agent, regime, … Every facet has a
consistent shape:

- `name`  — the URL query-parameter key (snake_case)
- `label` — the human label for the chip
- `is_available(conn)` — runtime check; hides facets whose backing
  data doesn't exist yet (e.g., strategies table before Epic 6)
- `get_values(conn, where_sql, where_args)` — returns the list of
  `FacetValue`s alongside their counts, given the currently-active
  filters (so counts shrink as Chef drills in)
- `sql_condition(selected)` — returns a `(fragment, params)` tuple
  that gets appended to the trade-list WHERE clause

The registry in `registry.py` holds the canonical order and provides
a single entry point for rendering the facet bar and applying a set
of selections to a query.

Story 4.1 AC #1 ships three concrete facets (asset class, broker,
horizon) plus placeholder registrations for the five future ones so
they light up automatically once the underlying data lands.
"""

from app.services.facets.base import Facet, FacetSelection, FacetValue
from app.services.facets.registry import (
    FacetRegistry,
    build_where_clause,
    get_registry,
    render_facets,
)

__all__ = [
    "Facet",
    "FacetSelection",
    "FacetValue",
    "FacetRegistry",
    "build_where_clause",
    "get_registry",
    "render_facets",
]
