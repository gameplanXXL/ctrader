"""Module-level MCP health tracker (Story 5.3).

Keeps track of the last successful call timestamp per agent so the
`staleness_banner` component can render the right severity. This is
intentionally a module-level singleton (not per-request) because the
freshness state is process-wide and we want every concurrent request
to see the same view.

All functions are sync — MCP callers drop in a `record_success()` or
`record_failure()` from their async code path and the latency is
nanoseconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.services.staleness import format_staleness, severity_for_staleness

# Known agent ids — matches AGENT_NAMES in app/services/trigger_prose.py
# and the taxonomy. New agents can add themselves at runtime via
# `record_success()` without pre-registration.
_KNOWN_AGENTS: tuple[str, ...] = ("viktor", "rita", "satoshi", "cassandra", "gordon")


@dataclass
class _HealthState:
    last_success: dict[str, datetime] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)


_state = _HealthState()


def record_success(agent: str) -> None:
    _state.last_success[agent] = datetime.now(UTC)
    _state.failure_counts[agent] = 0


def record_failure(agent: str) -> None:
    _state.failure_counts[agent] = _state.failure_counts.get(agent, 0) + 1


def reset() -> None:
    """Test helper."""

    _state.last_success.clear()
    _state.failure_counts.clear()


@dataclass(frozen=True)
class AgentHealth:
    agent: str
    last_success: datetime | None
    severity: str
    staleness_phrase: str
    failure_count: int


def get_agent_health(agent: str, *, now: datetime | None = None) -> AgentHealth:
    last = _state.last_success.get(agent)
    return AgentHealth(
        agent=agent,
        last_success=last,
        severity=severity_for_staleness(last, now=now),
        staleness_phrase=format_staleness(last, now=now),
        failure_count=_state.failure_counts.get(agent, 0),
    )


def get_all_agents(*, now: datetime | None = None) -> list[AgentHealth]:
    """Return one AgentHealth per known-agent, including agents that
    have never successfully called MCP (severity='red')."""

    seen = set(_state.last_success.keys())
    agents = list(_KNOWN_AGENTS) + [a for a in seen if a not in _KNOWN_AGENTS]
    return [get_agent_health(a, now=now) for a in agents]


def is_any_degraded(*, now: datetime | None = None) -> bool:
    """True if any known agent has yellow/red severity — drives the
    global staleness banner shown in base.html."""

    return any(agent.severity in ("yellow", "red") for agent in get_all_agents(now=now))


def worst_severity(*, now: datetime | None = None) -> str:
    """Return the highest severity across all agents for the banner.

    Code-review M8 / BH-25: use `.get()` with a safe default so a
    future severity token (e.g. "degraded") doesn't KeyError-crash
    the banner.
    """

    worst = "ok"
    order = {"ok": 0, "yellow": 1, "red": 2}
    for agent in get_all_agents(now=now):
        if order.get(agent.severity, 0) > order.get(worst, 0):
            worst = agent.severity
    return worst
