"""Unit tests for the facet framework (Story 4.1).

Covers the registry, WHERE-clause composition, and placeholder numbering
without touching a real DB. Integration coverage (hitting a real Postgres
with the facet query) lives in the journal integration test.
"""

from __future__ import annotations

from app.services.facets import build_where_clause, get_registry


def test_registry_exposes_expected_facets() -> None:
    registry = get_registry()
    names = registry.names
    # The eight canonical facets, in order.
    assert names == [
        "asset_class",
        "broker",
        "horizon",
        "strategy",
        "trigger_type",
        "followed",
        "confidence_band",
        "regime_tag",
    ]


def test_build_where_clause_empty_returns_trivial() -> None:
    where, params = build_where_clause({})
    assert where == "1=1"
    assert params == []


def test_build_where_clause_single_asset_class() -> None:
    where, params = build_where_clause({"asset_class": ["stock"]})
    assert where == "asset_class = ANY($1)"
    assert params == [["stock"]]


def test_build_where_clause_multi_select_uses_ANY() -> None:
    """Story 4.1 AC #7: shift+click produces multi-value selection."""

    where, params = build_where_clause({"asset_class": ["stock", "crypto"]})
    assert where == "asset_class = ANY($1)"
    assert params == [["stock", "crypto"]]


def test_build_where_clause_combined_facets_increment_placeholders() -> None:
    where, params = build_where_clause(
        {"asset_class": ["stock"], "broker": ["ib"]}
    )
    assert "asset_class = ANY($1)" in where
    assert "broker = ANY($2::trade_source[])" in where
    assert params == [["stock"], ["ib"]]


def test_build_where_clause_unknown_facet_is_silently_dropped() -> None:
    """Unknown facet names shouldn't crash the page."""

    where, params = build_where_clause({"asset_class": ["stock"], "bogus": ["x"]})
    assert where == "asset_class = ANY($1)"
    assert params == [["stock"]]


def test_horizon_facet_uses_jsonb_extraction() -> None:
    where, params = build_where_clause({"horizon": ["intraday", "swing_short"]})
    assert where == "trigger_spec->>'horizon' = ANY($1)"
    assert params == [["intraday", "swing_short"]]


def test_followed_facet_maps_to_boolean_any() -> None:
    where, params = build_where_clause({"followed": ["followed", "override"]})
    assert "trigger_spec->>'followed'" in where
    # Values mapped to booleans
    assert params == [[True, False]]
