"""Query-prose renderer (Story 4.2 / UX-DR21).

Turns the facet-selection dict into a short German headline the
user can read at a glance: "Crypto-Shorts mit Satoshi-Override",
"Alle Trades", "Stock-Trades, Intraday", etc.

Pattern catalogue grows as new facets land — keep the matcher
simple and string-based so non-English facet values don't corrupt
the output.
"""

from __future__ import annotations


# Ordered list of (predicate, phrase) pairs. First predicate that
# matches wins for its slot; multiple slots can fire (the output is
# "phrase1 + ' ' + phrase2").
#
# Predicates read the facet dict directly so the renderer does not
# need to import the facet registry.
def render_query_prose(facets: dict[str, list[str]]) -> str:
    """Return a short German headline for the current facet selection."""

    # Normalize: drop empty values, lowercase known strings.
    active = {k: v for k, v in facets.items() if v}
    if not active:
        return "Alle Trades"

    asset_classes = active.get("asset_class", [])
    brokers = active.get("broker", [])
    horizons = active.get("horizon", [])
    trigger_types = active.get("trigger_type", [])
    followed = active.get("followed", [])
    strategy = active.get("strategy", [])

    parts: list[str] = []

    # Asset-class leads the headline (most common drill-in).
    if asset_classes:
        parts.append(_asset_class_phrase(asset_classes))
    else:
        parts.append("Trades")

    # Brokers as a qualifier.
    if brokers:
        broker_phrase = _broker_phrase(brokers)
        if broker_phrase:
            parts.append(broker_phrase)

    # Horizons — "Intraday", "Short Swing", …
    if horizons:
        parts.append(_horizon_phrase(horizons))

    # Trigger-type + followed together produce the agent phrasing.
    if trigger_types:
        parts.append(_trigger_phrase(trigger_types, followed))
    elif followed:
        parts.append("mit Agent-" + _followed_phrase(followed))

    # Strategy override (Epic 6 fallback text).
    if strategy:
        parts.append(f"Strategie {', '.join(strategy)}")

    return " ".join(parts).strip()


def _asset_class_phrase(values: list[str]) -> str:
    labels = {
        "stock": "Stock",
        "option": "Optionen",
        "crypto": "Crypto",
        "cfd": "CFDs",
    }
    if len(values) == 1:
        return f"{labels.get(values[0], values[0].title())}-Trades"
    joined = " / ".join(labels.get(v, v.title()) for v in values)
    return f"{joined}-Trades"


def _broker_phrase(values: list[str]) -> str:
    labels = {"ib": "bei IB", "ctrader": "bei cTrader"}
    if len(values) == 1:
        return labels.get(values[0], f"bei {values[0]}")
    return "bei " + " / ".join(labels.get(v, v) for v in values)


def _horizon_phrase(values: list[str]) -> str:
    labels = {
        "intraday": "Intraday",
        "swing_short": "Short Swing",
        "swing_long": "Long Swing",
        "position": "Position",
    }
    if len(values) == 1:
        return f"({labels.get(values[0], values[0])})"
    return "(" + " / ".join(labels.get(v, v) for v in values) + ")"


def _trigger_phrase(trigger_types: list[str], followed: list[str]) -> str:
    # Special-case agent signals into "mit {Agent}-{Override|Follow}".
    agent_aliases = {
        "satoshi_signal": "Satoshi",
        "viktor_signal": "Viktor",
        "gordon_hot_pick": "Gordon-Pick",
        "news_event": "News-Event",
        "technical_breakout": "Ausbruch",
        "technical_pullback": "Pullback",
        "regime_shift": "Regime-Shift",
        "manual": "Manuell",
    }
    labels = [agent_aliases.get(v, v.replace("_", " ").title()) for v in trigger_types]
    trigger_label = " / ".join(labels)

    followed_phrase = _followed_phrase(followed) if followed else None
    if followed_phrase:
        return f"mit {trigger_label}-{followed_phrase}"
    return f"mit {trigger_label}"


def _followed_phrase(values: list[str]) -> str:
    if "followed" in values and "override" in values:
        return "Folgend / Override"
    if "override" in values:
        return "Override"
    return "Follow"
