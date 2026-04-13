"""Unit tests for aggregation.py + query_prose.py + sparkline.py (Story 4.2).

Aggregation's DB path is covered by the integration test. Here we
exercise the pure-Python pieces (query prose matcher, sparkline SVG
generator).
"""

from __future__ import annotations

from app.services.query_prose import render_query_prose
from app.services.sparkline import render_sparkline_svg

# ---------------------------------------------------------------------------
# query_prose
# ---------------------------------------------------------------------------


def test_no_facets_renders_all_trades() -> None:
    assert render_query_prose({}) == "Alle Trades"


def test_empty_list_values_are_treated_as_no_filter() -> None:
    assert render_query_prose({"asset_class": []}) == "Alle Trades"


def test_single_asset_class() -> None:
    assert "Stock-Trades" in render_query_prose({"asset_class": ["stock"]})


def test_crypto_plus_broker_combines() -> None:
    prose = render_query_prose({"asset_class": ["crypto"], "broker": ["ctrader"]})
    assert "Crypto-Trades" in prose
    assert "cTrader" in prose


def test_agent_signal_with_override() -> None:
    prose = render_query_prose({"trigger_type": ["satoshi_signal"], "followed": ["override"]})
    assert "Satoshi" in prose
    assert "Override" in prose


def test_multi_asset_class_joins_with_slash() -> None:
    prose = render_query_prose({"asset_class": ["stock", "crypto"]})
    assert "Stock / Crypto" in prose


def test_horizon_added_as_qualifier() -> None:
    prose = render_query_prose({"asset_class": ["stock"], "horizon": ["intraday"]})
    assert "Stock-Trades" in prose
    assert "Intraday" in prose


# ---------------------------------------------------------------------------
# sparkline
# ---------------------------------------------------------------------------


def test_sparkline_flat_on_empty_series() -> None:
    svg = render_sparkline_svg([])
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "M 0" in svg


def test_sparkline_flat_on_constant_series() -> None:
    """All-equal values render as a horizontal midline, not a crash."""

    svg = render_sparkline_svg([5.0, 5.0, 5.0, 5.0])
    assert "<path" in svg


def test_sparkline_normalizes_range() -> None:
    """First point pinned to x=0, last pinned to x=width."""

    svg = render_sparkline_svg([0.0, 10.0, 20.0], width=100, height=20)
    assert "M 0.0" in svg
    assert "100.0" in svg


def test_sparkline_aria_label_respected() -> None:
    svg = render_sparkline_svg([1.0, 2.0], aria_label="Custom label")
    assert 'aria-label="Custom label"' in svg
