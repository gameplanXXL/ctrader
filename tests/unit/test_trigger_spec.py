"""Unit tests for the TriggerSpec model + builder service (Story 3.2).

Updated after the Epic 3 code review:
- `strategy` and `exit_reason` are now captured inside the JSONB doc
  (code-review H1).
- `followed` is optional (default None) — manual trades don't invent
  "Chef folgte der Empfehlung" (H5 / EC-41).
- Pydantic `extra="ignore"` so a future schema addition doesn't
  break `parse()` on older rows (M5 / BH-28 / EC-11).
- `to_jsonb` uses `exclude_none=True` to keep the doc compact
  (BH-29).
"""

from __future__ import annotations

import pytest

from app.models.trigger_spec import TriggerSource, TriggerSpec
from app.services.trigger_spec import (
    TriggerSpecValidationError,
    build_from_proposal,
    build_from_tagging_form,
    parse,
)

# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


def test_trigger_spec_round_trips_through_jsonb() -> None:
    spec = TriggerSpec(
        trigger_type="technical_breakout",
        confidence=0.72,
        horizon="swing_short",
        entry_reason="20-day high breakout",
        source=TriggerSource.MANUAL,
        followed=True,
        strategy="momentum",
        exit_reason="target_hit",
        mistake_tags=["fomo", "no_stop"],
    )
    as_json = spec.to_jsonb()
    assert as_json == {
        "trigger_type": "technical_breakout",
        "confidence": 0.72,
        "horizon": "swing_short",
        "entry_reason": "20-day high breakout",
        "source": "manual",
        "followed": True,
        "strategy": "momentum",
        "exit_reason": "target_hit",
        "mistake_tags": ["fomo", "no_stop"],
    }
    restored = TriggerSpec.model_validate(as_json)
    assert restored == spec


def test_empty_mistake_tags_are_dropped_from_jsonb() -> None:
    """Story 3.4's report SQL keys on `trigger_spec ? 'mistake_tags'`
    so we must NOT store an empty list — drop the key entirely."""

    spec = TriggerSpec(
        trigger_type="manual",
        confidence=0.5,
        horizon="intraday",
        source=TriggerSource.MANUAL,
    )
    dumped = spec.to_jsonb()
    assert "mistake_tags" not in dumped


def test_none_fields_are_dropped_from_jsonb() -> None:
    """`exclude_none=True` keeps the stored doc compact (BH-29)."""

    spec = TriggerSpec(
        trigger_type="manual",
        confidence=0.5,
        horizon="intraday",
        source=TriggerSource.MANUAL,
    )
    dumped = spec.to_jsonb()
    assert "agent_id" not in dumped
    assert "proposal_id" not in dumped
    assert "followed" not in dumped
    assert "note" not in dumped
    assert "strategy" not in dumped
    assert "exit_reason" not in dumped


def test_mistake_tags_deduped() -> None:
    spec = TriggerSpec(
        trigger_type="manual",
        confidence=0.5,
        horizon="intraday",
        source=TriggerSource.MANUAL,
        mistake_tags=["fomo", "fomo", "", "no_stop"],
    )
    assert spec.mistake_tags == ["fomo", "no_stop"]


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValueError):
        TriggerSpec(
            trigger_type="manual",
            confidence=1.5,
            horizon="intraday",
            source=TriggerSource.MANUAL,
        )


def test_extra_keys_are_ignored_not_rejected() -> None:
    """Code-review M5 / BH-28 / EC-11: `extra="ignore"` so a future
    field addition doesn't break `parse()` on older stored rows."""

    spec = TriggerSpec.model_validate(
        {
            "trigger_type": "manual",
            "confidence": 0.5,
            "horizon": "intraday",
            "source": "manual",
            "future_field": "whatever",
        }
    )
    assert spec.trigger_type == "manual"


# ---------------------------------------------------------------------------
# Builder: build_from_tagging_form
# ---------------------------------------------------------------------------


def _form(**overrides: object) -> dict[str, object]:
    """Minimal happy-path form payload — 4 required fields + overrides."""

    base: dict[str, object] = {
        "strategy": "momentum",
        "trigger_type": "technical_breakout",
        "horizon": "swing_short",
        "exit_reason": "target_hit",
    }
    base.update(overrides)
    return base


def test_build_from_form_happy_path() -> None:
    spec = build_from_tagging_form(
        _form(
            confidence="72%",
            entry_reason="Earnings beat, breakout",
            mistake_tags=["fomo", "chased"],
        )
    )
    assert spec.trigger_type == "technical_breakout"
    assert spec.confidence == 0.72
    assert spec.horizon == "swing_short"
    assert spec.strategy == "momentum"
    assert spec.exit_reason == "target_hit"
    assert spec.mistake_tags == ["fomo", "chased"]
    assert spec.followed is None  # no checkbox → neutral
    assert spec.source is TriggerSource.MANUAL


def test_build_from_form_requires_strategy() -> None:
    """Code-review H1: strategy is one of the four mandatory fields
    from FR15 / Story 3.1 AC #1 — previously dropped silently."""

    with pytest.raises(TriggerSpecValidationError, match="strategy"):
        form = _form()
        form.pop("strategy")
        build_from_tagging_form(form)


def test_build_from_form_requires_exit_reason() -> None:
    """Code-review H1: exit_reason is mandatory — previously dropped."""

    with pytest.raises(TriggerSpecValidationError, match="exit_reason"):
        form = _form()
        form.pop("exit_reason")
        build_from_tagging_form(form)


def test_build_from_form_rejects_unknown_exit_reason() -> None:
    with pytest.raises(TriggerSpecValidationError, match="exit_reason"):
        build_from_tagging_form(_form(exit_reason="bogus"))


def test_build_from_form_accepts_float_confidence() -> None:
    spec = build_from_tagging_form(_form(confidence=0.3))
    assert spec.confidence == 0.3


def test_build_from_form_accepts_int_percent() -> None:
    spec = build_from_tagging_form(_form(confidence=45))
    assert spec.confidence == 0.45


def test_build_from_form_default_confidence() -> None:
    """Omitted confidence → 0.5 neutral default."""

    spec = build_from_tagging_form(_form())
    assert spec.confidence == 0.5


def test_build_from_form_rejects_unknown_trigger_type() -> None:
    with pytest.raises(TriggerSpecValidationError, match="trigger_type"):
        build_from_tagging_form(_form(trigger_type="bogus"))


def test_build_from_form_rejects_unknown_horizon() -> None:
    with pytest.raises(TriggerSpecValidationError, match="horizon"):
        build_from_tagging_form(_form(horizon="forever"))


def test_build_from_form_drops_unknown_mistake_tags() -> None:
    """Unknown mistake tags are logged, not raised — taxonomy drift
    shouldn't block tagging (see service comment)."""

    spec = build_from_tagging_form(_form(mistake_tags=["fomo", "bogus_tag", "no_stop"]))
    assert spec.mistake_tags == ["fomo", "no_stop"]


def test_build_from_form_accepts_string_mistake_tag() -> None:
    """Single-checkbox form submits one value as a string, not a list."""

    spec = build_from_tagging_form(_form(mistake_tags="fomo"))
    assert spec.mistake_tags == ["fomo"]


def test_build_from_form_followed_absent_stays_none() -> None:
    """Code-review H5: manual trades have no `followed` checkbox, so
    the flag MUST default to None (not True) — otherwise the prose
    renderer invents "Chef folgte der Empfehlung" on every manual tag.
    """

    spec = build_from_tagging_form(_form())
    assert spec.followed is None


def test_build_from_form_followed_explicit_on() -> None:
    """Bot path can still set followed explicitly."""

    spec = build_from_tagging_form(_form(followed="on"))
    assert spec.followed is True


def test_build_from_form_followed_explicit_off() -> None:
    spec = build_from_tagging_form(_form(followed="off"))
    assert spec.followed is False


# ---------------------------------------------------------------------------
# Builder: build_from_proposal (Epic 7 placeholder)
# ---------------------------------------------------------------------------


def test_build_from_proposal_minimal() -> None:
    spec = build_from_proposal(
        {
            "id": 42,
            "trigger_type": "satoshi_signal",
            "confidence": 0.85,
            "horizon": "intraday",
            "entry_reason": "Oversold RSI + F&G extreme fear",
            "agent_id": "satoshi",
        }
    )
    assert spec.source is TriggerSource.BOT
    assert spec.agent_id == "satoshi"
    assert spec.proposal_id == 42
    assert spec.confidence == 0.85


# ---------------------------------------------------------------------------
# parse()
# ---------------------------------------------------------------------------


def test_parse_none_returns_none() -> None:
    assert parse(None) is None


def test_parse_valid_dict_returns_model() -> None:
    spec = parse(
        {
            "trigger_type": "viktor_signal",
            "confidence": 0.6,
            "horizon": "swing_long",
            "entry_reason": "deep-value setup",
            "source": "bot",
            "followed": True,
            "agent_id": "viktor",
        }
    )
    assert spec is not None
    assert spec.agent_id == "viktor"


def test_parse_tolerates_future_keys() -> None:
    """Code-review M5: `extra="ignore"` so `parse()` never fails on
    stored rows that pre-date a new field addition."""

    spec = parse(
        {
            "trigger_type": "manual",
            "confidence": 0.5,
            "horizon": "intraday",
            "source": "manual",
            "new_field_from_the_future": 42,
        }
    )
    assert spec is not None
    assert spec.trigger_type == "manual"
