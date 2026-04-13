"""Unit tests for the `QueryPreset` dataclass helpers (Story 4.7)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.query_presets import QueryPreset


def test_preset_to_query_string_round_trips() -> None:
    preset = QueryPreset(
        id=1,
        name="Satoshi Override Losses",
        filters={"asset_class": ["crypto"], "followed": ["override"]},
        created_at=datetime(2026, 4, 13, tzinfo=UTC),
    )
    qs = preset.to_query_string()
    assert "asset_class=crypto" in qs
    assert "followed=override" in qs


def test_preset_multi_value_filter_flattens() -> None:
    preset = QueryPreset(
        id=2,
        name="Stock + Crypto",
        filters={"asset_class": ["stock", "crypto"]},
        created_at=datetime(2026, 4, 13, tzinfo=UTC),
    )
    qs = preset.to_query_string()
    assert qs.count("asset_class=") == 2


def test_preset_empty_filters_is_empty_string() -> None:
    preset = QueryPreset(
        id=3,
        name="All",
        filters={},
        created_at=datetime(2026, 4, 13, tzinfo=UTC),
    )
    assert preset.to_query_string() == ""
