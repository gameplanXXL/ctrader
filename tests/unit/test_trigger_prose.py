"""Unit tests for Story 3.3 trigger-spec prose renderer.

Covers the 8+ patterns, partial-field fallback ("Unbekannt"), and
empty-spec fallback ("Nicht getaggt") per AC #1 / #2 / #3.
"""

from __future__ import annotations

from app.services.trigger_prose import (
    PATTERNS,
    render_mistake_tags,
    render_trigger_prose,
)

# ---------------------------------------------------------------------------
# AC #3 — empty / missing spec
# ---------------------------------------------------------------------------


def test_none_spec_renders_as_nicht_getaggt() -> None:
    assert render_trigger_prose(None) == "Nicht getaggt"


def test_empty_dict_spec_also_returns_nicht_getaggt() -> None:
    assert render_trigger_prose({}) == "Nicht getaggt"


def test_explicit_null_trigger_type_also_nicht_getaggt() -> None:
    """Code-review EC-5: a dict with `trigger_type: None` (e.g. from
    asyncpg decoding a JSONB row with partial fields) must not render
    a half-formed "Unbekannt (…)" line. Treat as untagged."""

    assert render_trigger_prose({"trigger_type": None, "horizon": "intraday"}) == "Nicht getaggt"


def test_empty_string_trigger_type_also_nicht_getaggt() -> None:
    assert render_trigger_prose({"trigger_type": "", "horizon": "intraday"}) == "Nicht getaggt"


# ---------------------------------------------------------------------------
# AC #1 — pattern coverage (happy paths)
# ---------------------------------------------------------------------------


def test_satoshi_signal_renders_full_prose() -> None:
    spec = {
        "trigger_type": "satoshi_signal",
        "confidence": 0.85,
        "horizon": "intraday",
        "entry_reason": "Oversold RSI + F&G extreme fear",
        "source": "bot",
        "agent_id": "satoshi",
        "followed": True,
    }
    trade = {"symbol": "BTCUSD", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "Satoshi" in prose
    assert "BTCUSD" in prose
    assert "85%" in prose
    assert "kaufte" in prose
    assert "folgte der Empfehlung" in prose


def test_viktor_signal_not_followed() -> None:
    spec = {
        "trigger_type": "viktor_signal",
        "confidence": 0.6,
        "horizon": "swing_long",
        "source": "bot",
        "agent_id": "viktor",
        "followed": False,
    }
    trade = {"symbol": "MSFT", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "Viktor" in prose
    assert "ueberstimmte" in prose


def test_gordon_hot_pick_renders() -> None:
    spec = {
        "trigger_type": "gordon_hot_pick",
        "confidence": 0.7,
        "horizon": "swing_short",
        "followed": True,
    }
    trade = {"symbol": "NVDA", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "Gordon-Wochen-Radar" in prose
    assert "NVDA" in prose
    assert "HOT-Pick" in prose


def test_technical_breakout_renders_entry_reason() -> None:
    spec = {
        "trigger_type": "technical_breakout",
        "confidence": 0.65,
        "horizon": "swing_short",
        "entry_reason": "20-day high mit Volumen",
        "source": "manual",
    }
    trade = {"symbol": "AAPL", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "AAPL" in prose
    assert "20-day high mit Volumen" in prose
    assert "65%" in prose


def test_manual_short_uses_german_verb() -> None:
    spec = {
        "trigger_type": "manual",
        "confidence": 0.4,
        "horizon": "intraday",
        "entry_reason": "Diskretionaerer Short",
        "source": "manual",
    }
    trade = {"symbol": "TSLA", "side": "short"}
    prose = render_trigger_prose(spec, trade)
    assert "short-te" in prose
    assert "TSLA" in prose


# ---------------------------------------------------------------------------
# AC #2 — partial spec fallback
# ---------------------------------------------------------------------------


def test_missing_confidence_renders_unbekannt() -> None:
    spec = {
        "trigger_type": "manual",
        "horizon": "intraday",
        "source": "manual",
    }
    trade = {"symbol": "AAPL", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "Unbekannt" in prose


def test_missing_horizon_renders_unbekannt() -> None:
    spec = {
        "trigger_type": "manual",
        "confidence": 0.5,
        "source": "manual",
    }
    trade = {"symbol": "AAPL", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "Unbekannt" in prose


def test_unknown_trigger_type_falls_back_to_default_pattern() -> None:
    spec = {
        "trigger_type": "brand_new_signal",
        "confidence": 0.5,
        "horizon": "intraday",
        "entry_reason": "neue Strategie",
        "source": "manual",
    }
    trade = {"symbol": "AAPL", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "AAPL" in prose
    assert "neue Strategie" in prose


def test_missing_trade_context_still_renders() -> None:
    """Trade dict can be None — symbol falls back to 'Unbekannt'."""

    spec = {
        "trigger_type": "manual",
        "confidence": 0.5,
        "horizon": "intraday",
        "source": "manual",
    }
    prose = render_trigger_prose(spec, None)
    assert "Unbekannt" in prose


# ---------------------------------------------------------------------------
# AC #4 — pattern catalogue size
# ---------------------------------------------------------------------------


def test_pattern_catalogue_covers_all_taxonomy_trigger_types() -> None:
    """Every trigger_type from taxonomy.yaml must have a pattern, so
    the default fallback never fires for a known type."""

    from app.services.taxonomy import get_taxonomy

    taxonomy_ids = set(get_taxonomy().ids("trigger_types"))
    pattern_ids = set(PATTERNS.keys())
    missing = taxonomy_ids - pattern_ids
    assert not missing, f"missing patterns for trigger_types: {sorted(missing)}"


def test_pattern_catalogue_has_no_dead_patterns() -> None:
    """Code-review EC-38: reverse direction — a pattern with no
    taxonomy entry is dead code that will silently rot if the
    taxonomy is renamed."""

    from app.services.taxonomy import get_taxonomy

    taxonomy_ids = set(get_taxonomy().ids("trigger_types"))
    pattern_ids = set(PATTERNS.keys())
    stale = pattern_ids - taxonomy_ids
    assert not stale, f"dead patterns not referenced by taxonomy: {sorted(stale)}"


# ---------------------------------------------------------------------------
# Code-review H5 / EC-41 — `followed` defaulting
# ---------------------------------------------------------------------------


def test_manual_trade_without_followed_does_not_invent_provenance() -> None:
    """A manual tag has no `followed` flag — prose must NOT claim
    "Chef folgte der Empfehlung" because there was no recommendation
    to follow in the first place."""

    spec = {
        "trigger_type": "manual",
        "confidence": 0.5,
        "horizon": "intraday",
        "entry_reason": "Diskretionaerer Einstieg",
        "source": "manual",
    }
    trade = {"symbol": "AAPL", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "folgte der Empfehlung" not in prose
    assert "ueberstimmte" not in prose


# ---------------------------------------------------------------------------
# Code-review BH-17 — confidence clamp
# ---------------------------------------------------------------------------


def test_confidence_above_one_is_clamped_to_100pct() -> None:
    """A buggy caller sending raw integer percent (`confidence=45`) as
    a stored value must not render 'Confidence 4500%'."""

    spec = {
        "trigger_type": "manual",
        "confidence": 45,  # misencoded — 45 instead of 0.45
        "horizon": "intraday",
        "source": "manual",
    }
    trade = {"symbol": "AAPL", "side": "buy"}
    prose = render_trigger_prose(spec, trade)
    assert "4500%" not in prose
    assert "100%" in prose


# ---------------------------------------------------------------------------
# render_mistake_tags helper
# ---------------------------------------------------------------------------


def test_mistake_tags_helper_returns_list() -> None:
    assert render_mistake_tags(None) == []
    assert render_mistake_tags({}) == []
    assert render_mistake_tags({"mistake_tags": ["fomo", "no_stop"]}) == ["fomo", "no_stop"]
    # Tolerates single-string accidentally bypassing list
    assert render_mistake_tags({"mistake_tags": "fomo"}) == ["fomo"]
