"""Trigger-Spec prose renderer (Story 3.3, FR18, UX-DR18 + UX-DR74).

Turns the JSONB `trigger_spec` into natural-language German sentences.
KEIN Raw-JSON in the user-facing UI — that's the whole point of this
module.

20+ templates, one per trigger_type (from `taxonomy.yaml`) plus a
generic fallback. Missing fields render as "Unbekannt", missing spec
renders as "Nicht getaggt".
"""

from __future__ import annotations

from typing import Any

# Agent display names — `agent_id` in the spec is lowercase slug,
# the prose uses the canonical name. Extend when new agents land.
AGENT_NAMES: dict[str, str] = {
    "viktor": "Viktor",
    "rita": "Rita",
    "satoshi": "Satoshi",
    "cassandra": "Cassandra",
    "gordon": "Gordon",
}


# Pattern catalogue — keyed on `trigger_type` (matches
# taxonomy.yaml.trigger_types.id). A pattern is a
# plain format-string with a fixed vocabulary of placeholders:
#   {symbol}, {side_de}, {horizon_label}, {confidence_pct},
#   {entry_reason}, {agent_name}, {followed_text}, {note}
#
# Missing placeholders are filled with "Unbekannt" by `render_trigger_prose`
# so a partial spec still renders cleanly.
PATTERNS: dict[str, str] = {
    "news_event": (
        "{agent_name} empfahl {side_de} {symbol} nach News-Event "
        "(Confidence {confidence_pct}%, Horizon: {horizon_label}) — {followed_text}."
    ),
    "technical_breakout": (
        "{side_de} {symbol} auf technischem Ausbruch — {entry_reason} "
        "(Horizon: {horizon_label}, Confidence {confidence_pct}%)."
    ),
    "technical_pullback": (
        "Pullback-Einstieg: {side_de} {symbol} in Trend-Richtung "
        "({horizon_label}, Confidence {confidence_pct}%)."
    ),
    "viktor_signal": (
        "Viktor (SFA-Analyse, Confidence {confidence_pct}%, Horizon: {horizon_label}) "
        "empfahl {side_de} {symbol} — {followed_text}."
    ),
    "satoshi_signal": (
        "Satoshi (CFA-Analyse, Confidence {confidence_pct}%, Horizon: {horizon_label}) "
        "empfahl {side_de} {symbol} — {followed_text}."
    ),
    "gordon_hot_pick": (
        "Aus Gordon-Wochen-Radar: {symbol} als HOT-Pick ({horizon_label}, "
        "Confidence {confidence_pct}%) — {followed_text}."
    ),
    "regime_shift": (
        "Regime-Shift-Reaktion: {side_de} {symbol} — {entry_reason} (Horizon: {horizon_label})."
    ),
    "manual": (
        "Chef {side_de} {symbol} aus Diskretion — {entry_reason} "
        "({horizon_label}, Confidence {confidence_pct}%)."
    ),
}

# Fallback used when trigger_type is missing from the catalogue.
DEFAULT_PATTERN = (
    "{side_de} {symbol} ({horizon_label}, Confidence {confidence_pct}%) — {entry_reason}."
)


# Internal: map the `trade.side` enum value to a German verb fragment.
SIDE_DE: dict[str, str] = {
    "buy": "kaufte",
    "sell": "verkaufte",
    "short": "short-te",
    "cover": "deckte",
}

HORIZON_LABELS: dict[str, str] = {
    "intraday": "Intraday",
    "swing_short": "Short Swing",
    "swing_long": "Long Swing",
    "position": "Position",
}


def _followed_text(followed: bool | None) -> str:
    if followed is True:
        return "Chef folgte der Empfehlung"
    if followed is False:
        return "Chef ueberstimmte die Empfehlung"
    return "Unbekannt"


def _agent_name(agent_id: str | None) -> str:
    if not agent_id:
        return "Ein Agent"
    return AGENT_NAMES.get(agent_id.lower(), agent_id.capitalize())


def _confidence_pct(confidence: float | int | None) -> str:
    if confidence is None:
        return "Unbekannt"
    try:
        return str(int(round(float(confidence) * 100)))
    except (TypeError, ValueError):
        return "Unbekannt"


def _format_with_fallback(template: str, fields: dict[str, Any]) -> str:
    """Format `template` with `fields`, filling missing placeholders as 'Unbekannt'."""

    class _SafeDict(dict[str, Any]):
        def __missing__(self, key: str) -> str:
            return "Unbekannt"

    return template.format_map(_SafeDict(fields))


def render_trigger_prose(
    trigger_spec: dict[str, Any] | None,
    trade: dict[str, Any] | None = None,
) -> str:
    """Render a `trigger_spec` JSONB doc as a single prose sentence.

    - `None` → "Nicht getaggt"
    - unknown `trigger_type` → DEFAULT_PATTERN
    - missing fields → "Unbekannt"

    `trade` is optional: when present, `symbol` and `side` fall back
    to the trade row so a spec without those fields still renders.
    """

    if not trigger_spec:
        return "Nicht getaggt"

    trade = trade or {}
    trigger_type = (trigger_spec.get("trigger_type") or "").lower().strip()
    template = PATTERNS.get(trigger_type, DEFAULT_PATTERN)

    side_raw = str(trade.get("side") or trigger_spec.get("side") or "").lower()
    horizon_raw = str(trigger_spec.get("horizon") or "").lower()

    fields = {
        "symbol": str(trade.get("symbol") or trigger_spec.get("symbol") or "Unbekannt"),
        "side_de": SIDE_DE.get(side_raw, "handelte"),
        "horizon_label": HORIZON_LABELS.get(horizon_raw, horizon_raw or "Unbekannt"),
        "confidence_pct": _confidence_pct(trigger_spec.get("confidence")),
        "entry_reason": (trigger_spec.get("entry_reason") or "").strip() or "Unbekannt",
        "agent_name": _agent_name(trigger_spec.get("agent_id")),
        "followed_text": _followed_text(trigger_spec.get("followed")),
        "note": (trigger_spec.get("note") or "").strip() or "",
    }

    return _format_with_fallback(template, fields)


def render_mistake_tags(trigger_spec: dict[str, Any] | None) -> list[str]:
    """Return the mistake-tag ids on a trigger_spec, preserving order.

    Shape helper for the drilldown template — the template-side code
    doesn't need to know about `None` vs missing vs empty list.
    """

    if not trigger_spec:
        return []
    tags = trigger_spec.get("mistake_tags") or []
    if isinstance(tags, str):
        return [tags]
    return [str(t) for t in tags if t]
