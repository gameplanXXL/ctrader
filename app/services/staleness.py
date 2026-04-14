"""Staleness formatting helpers (Story 5.1 / 5.3).

Produces German phrases for "vor X Minuten" / "vor X Stunden" style
freshness hints that the UI renders next to cached fundamental data.
"""

from __future__ import annotations

from datetime import UTC, datetime


def format_staleness(cached_at: datetime | None, *, now: datetime | None = None) -> str:
    """Return a short German phrase like "vor 23 Minuten".

    - `None` → "unbekannt"
    - future timestamp (clock skew) → "in der Zukunft (?)"
    - < 60s → "gerade eben"
    - < 60min → "vor N Minuten"
    - < 24h  → "vor N Stunden"
    - ≥ 24h  → "vor N Tagen"

    Code-review H8 / BH-7: future timestamps used to silently map to
    "gerade eben", masking clock skew / tz bugs. We now surface the
    anomaly explicitly.
    """

    if cached_at is None:
        return "unbekannt"

    reference = now or datetime.now(UTC)
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)

    delta = reference - cached_at
    seconds = int(delta.total_seconds())

    if seconds < -5:  # Allow a small clock-skew tolerance.
        return "in der Zukunft (?)"
    if seconds < 60:
        return "gerade eben"
    if seconds < 3600:
        minutes = seconds // 60
        return f"vor {minutes} Minuten" if minutes != 1 else "vor 1 Minute"
    if seconds < 86_400:
        hours = seconds // 3600
        return f"vor {hours} Stunden" if hours != 1 else "vor 1 Stunde"
    days = seconds // 86_400
    return f"vor {days} Tagen" if days != 1 else "vor 1 Tag"


def severity_for_staleness(cached_at: datetime | None, *, now: datetime | None = None) -> str:
    """Return `'ok'` / `'yellow'` / `'red'` per Story 5.3 AC #3.

    - < 1h → ok
    - 1h..24h → yellow
    - > 24h OR None OR future timestamp → red

    Code-review H8 / BH-8: a future timestamp (clock skew, tz bug)
    used to return "ok", silently masking a data-integrity issue.
    We now treat it as red so the banner screams until the root
    cause is fixed.
    """

    if cached_at is None:
        return "red"

    reference = now or datetime.now(UTC)
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)

    delta_seconds = (reference - cached_at).total_seconds()
    if delta_seconds < -5:
        return "red"
    hours = delta_seconds / 3600
    if hours < 1:
        return "ok"
    if hours < 24:
        return "yellow"
    return "red"
