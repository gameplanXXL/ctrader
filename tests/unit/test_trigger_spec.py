"""Unit tests for the TriggerSpec model + builder service (Story 3.2)."""

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
        "agent_id": None,
        "proposal_id": None,
        "mistake_tags": ["fomo", "no_stop"],
        "note": None,
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


def test_extra_keys_rejected() -> None:
    with pytest.raises(ValueError):
        TriggerSpec.model_validate(
            {
                "trigger_type": "manual",
                "confidence": 0.5,
                "horizon": "intraday",
                "source": "manual",
                "unknown_field": "nope",
            }
        )


# ---------------------------------------------------------------------------
# Builder: build_from_tagging_form
# ---------------------------------------------------------------------------


def test_build_from_form_happy_path() -> None:
    spec = build_from_tagging_form(
        {
            "trigger_type": "technical_breakout",
            "horizon": "swing_short",
            "confidence": "72%",
            "entry_reason": "Earnings beat, breakout",
            "mistake_tags": ["fomo", "chased"],
            "followed": "on",
        }
    )
    assert spec.trigger_type == "technical_breakout"
    assert spec.confidence == 0.72
    assert spec.horizon == "swing_short"
    assert spec.mistake_tags == ["fomo", "chased"]
    assert spec.followed is True
    assert spec.source is TriggerSource.MANUAL


def test_build_from_form_accepts_float_confidence() -> None:
    spec = build_from_tagging_form(
        {"trigger_type": "manual", "horizon": "intraday", "confidence": 0.3}
    )
    assert spec.confidence == 0.3


def test_build_from_form_accepts_int_percent() -> None:
    spec = build_from_tagging_form(
        {"trigger_type": "manual", "horizon": "intraday", "confidence": 45}
    )
    assert spec.confidence == 0.45


def test_build_from_form_default_confidence() -> None:
    """Omitted confidence → 0.5 neutral default."""

    spec = build_from_tagging_form({"trigger_type": "manual", "horizon": "intraday"})
    assert spec.confidence == 0.5


def test_build_from_form_rejects_unknown_trigger_type() -> None:
    with pytest.raises(TriggerSpecValidationError, match="trigger_type"):
        build_from_tagging_form({"trigger_type": "bogus", "horizon": "intraday"})


def test_build_from_form_rejects_unknown_horizon() -> None:
    with pytest.raises(TriggerSpecValidationError, match="horizon"):
        build_from_tagging_form({"trigger_type": "manual", "horizon": "forever"})


def test_build_from_form_requires_trigger_type() -> None:
    with pytest.raises(TriggerSpecValidationError, match="trigger_type"):
        build_from_tagging_form({"horizon": "intraday"})


def test_build_from_form_requires_horizon() -> None:
    with pytest.raises(TriggerSpecValidationError, match="horizon"):
        build_from_tagging_form({"trigger_type": "manual"})


def test_build_from_form_drops_unknown_mistake_tags() -> None:
    """Unknown mistake tags are logged, not raised — taxonomy drift
    shouldn't block tagging (see service comment)."""

    spec = build_from_tagging_form(
        {
            "trigger_type": "manual",
            "horizon": "intraday",
            "mistake_tags": ["fomo", "bogus_tag", "no_stop"],
        }
    )
    assert spec.mistake_tags == ["fomo", "no_stop"]


def test_build_from_form_accepts_string_mistake_tag() -> None:
    """Single-checkbox form submits one value as a string, not a list."""

    spec = build_from_tagging_form(
        {
            "trigger_type": "manual",
            "horizon": "intraday",
            "mistake_tags": "fomo",
        }
    )
    assert spec.mistake_tags == ["fomo"]


def test_build_from_form_followed_false_on_string_off() -> None:
    spec = build_from_tagging_form(
        {"trigger_type": "manual", "horizon": "intraday", "followed": "off"}
    )
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
