"""Agent facet — filter journal by the cTrader bot agent that placed
the trade (Story 8.2 AC #3 / Code-review H10).

Bot trades have a non-NULL `agent_id` (populated at FILLED-event time
by `bot_execution.handle_execution_event`). Manual trades — whether
imported from IB Flex or placed via Quick-Order — have `agent_id
IS NULL`. Selecting `bot:any` returns all rows with a non-NULL agent,
selecting a specific agent name narrows further.

The "Bot-Trades only" filter that Story 8.2 AC #3 requires is just a
special case of this facet with the synthetic value `bot:any`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.facets.base import BaseFacet

# Synthetic "any bot" selector. Anything NOT starting with `bot:` is
# treated as a literal agent_id match.
_ANY_BOT = "bot:any"

_VALUES_SQL = """
SELECT COALESCE(agent_id, '') AS value, COUNT(*) AS count
  FROM trades
 WHERE {where_sql}
 GROUP BY agent_id
 ORDER BY count DESC, agent_id ASC
"""


@dataclass
class AgentFacet(BaseFacet):
    name: str = "agent"
    label: str = "Agent"
    _values_sql: str = _VALUES_SQL
    _label_map: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._label_map is None:
            # Known agents from `fundamental` MCP — extend as needed.
            self._label_map = {
                _ANY_BOT: "Alle Bot-Trades",
                "satoshi": "Satoshi",
                "viktor": "Viktor",
                "rita": "Rita",
                "cassandra": "Cassandra",
                "gordon": "Gordon",
            }

    def sql_condition(
        self,
        selected: list[str],
        *,
        placeholder_start: int,
    ) -> tuple[str, list[object]]:
        """Filter by agent_id.

        Values starting with `bot:` are synthetic:
        - `bot:any` → `agent_id IS NOT NULL` (all bot trades)

        Plain values are treated as literal agent_id matches via
        `ANY($N::text[])`.
        """

        if not selected:
            return "", []
        if _ANY_BOT in selected:
            return "agent_id IS NOT NULL", []
        fragment = f"agent_id = ANY(${placeholder_start}::text[])"
        return fragment, [selected]
