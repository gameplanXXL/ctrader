"""Unit tests for the Story 5.1 fundamental service + staleness helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.fundamental import FundamentalRating
from app.services.fundamental import (
    _agent_for,
    _parse_confidence,
    _parse_mcp_response,
    _parse_rating,
    clear_caches,
    get_fundamental,
)
from app.services.staleness import format_staleness, severity_for_staleness


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_caches()
    yield
    clear_caches()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def test_agent_routing_stock_goes_to_viktor() -> None:
    assert _agent_for("stock") == "viktor"
    assert _agent_for("option") == "viktor"


def test_agent_routing_crypto_goes_to_satoshi() -> None:
    assert _agent_for("crypto") == "satoshi"
    assert _agent_for("cfd") == "satoshi"


def test_agent_routing_unknown_defaults_to_viktor() -> None:
    assert _agent_for("weird_thing") == "viktor"


# ---------------------------------------------------------------------------
# Confidence coercion
# ---------------------------------------------------------------------------


def test_parse_confidence_accepts_0_to_1_float() -> None:
    assert _parse_confidence(0.72) == 0.72


def test_parse_confidence_accepts_percent_int() -> None:
    assert _parse_confidence(85) == 0.85


def test_parse_confidence_clamps_above_1() -> None:
    assert _parse_confidence(150) == 1.0


def test_parse_confidence_none_returns_zero() -> None:
    assert _parse_confidence(None) == 0.0


def test_parse_confidence_garbage_returns_zero() -> None:
    assert _parse_confidence("not a number") == 0.0


# ---------------------------------------------------------------------------
# Rating mapping
# ---------------------------------------------------------------------------


def test_viktor_rating_map_canonical() -> None:
    assert _parse_rating("BUY", "viktor") == FundamentalRating.BUY
    assert _parse_rating("HOLD", "viktor") == FundamentalRating.HOLD
    assert _parse_rating("SELL", "viktor") == FundamentalRating.SELL
    assert _parse_rating("STRONG_BUY", "viktor") == FundamentalRating.BUY


def test_satoshi_rating_map_canonical() -> None:
    assert _parse_rating("LONG", "satoshi") == FundamentalRating.LONG
    assert _parse_rating("NEUTRAL", "satoshi") == FundamentalRating.NEUTRAL
    assert _parse_rating("SHORT", "satoshi") == FundamentalRating.SHORT


def test_unknown_rating_token_maps_to_unknown() -> None:
    assert _parse_rating("BOGUS", "viktor") == FundamentalRating.UNKNOWN
    assert _parse_rating(None, "viktor") == FundamentalRating.UNKNOWN


# ---------------------------------------------------------------------------
# MCP response parsing (tool-call shapes)
# ---------------------------------------------------------------------------


def test_parse_mcp_response_from_content_list() -> None:
    raw = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": '{"rating":"BUY","confidence":0.72,"thesis":"Growth"}',
                }
            ]
        },
    }
    assessment = _parse_mcp_response(raw, "viktor")
    assert assessment.rating == FundamentalRating.BUY
    assert assessment.confidence == 0.72
    assert "Growth" in assessment.thesis


def test_parse_mcp_response_falls_back_to_result_dict() -> None:
    """Older/custom shape: result itself is the assessment dict."""

    raw = {
        "result": {
            "rating": "HOLD",
            "confidence": 0.55,
            "thesis": "Mixed",
        }
    }
    assessment = _parse_mcp_response(raw, "viktor")
    assert assessment.rating == FundamentalRating.HOLD
    assert assessment.confidence == 0.55


def test_parse_mcp_response_empty_returns_unknown() -> None:
    assessment = _parse_mcp_response({"result": {}}, "viktor")
    assert assessment.rating == FundamentalRating.UNKNOWN


# ---------------------------------------------------------------------------
# get_fundamental — end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_fundamental_none_mcp_returns_none_without_cache() -> None:
    result = await get_fundamental("AAPL", "stock", mcp_client=None)
    assert result is None


@pytest.mark.asyncio
async def test_get_fundamental_success_caches_and_returns() -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.return_value = {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": '{"rating":"BUY","confidence":0.8,"thesis":"Earnings beat"}',
                }
            ]
        }
    }
    result = await get_fundamental("AAPL", "stock", mcp_client=mock_client)
    assert result is not None
    assert result.assessment.rating == FundamentalRating.BUY
    assert not result.is_stale
    assert result.source_agent == "viktor"

    # Second call hits the fresh cache — mock called only once.
    await get_fundamental("AAPL", "stock", mcp_client=mock_client)
    assert mock_client.call_tool.call_count == 1


@pytest.mark.asyncio
async def test_get_fundamental_timeout_falls_back_to_stale() -> None:
    """Code-review: graceful degradation on MCP timeout."""

    mock_client = AsyncMock()
    # First call succeeds and seeds the stale cache.
    mock_client.call_tool.return_value = {
        "result": {"content": [{"type": "text", "text": '{"rating":"BUY","confidence":0.5}'}]}
    }
    await get_fundamental("AAPL", "stock", mcp_client=mock_client)

    # Keep stale — clear fresh cache only so the next call cannot
    # satisfy from the fresh TTLCache.
    from app.services.fundamental import _fresh_caches

    for cache in _fresh_caches.values():
        cache.clear()

    # Force a timeout on the next fetch.
    mock_client.call_tool.side_effect = TimeoutError("mcp down")
    result = await get_fundamental("AAPL", "stock", mcp_client=mock_client)
    assert result is not None
    # The stale cache still holds the first successful fetch,
    # now flagged as stale (code-review H2 / EC-1).
    assert result.assessment.rating == FundamentalRating.BUY
    assert result.is_stale is True


# ---------------------------------------------------------------------------
# Staleness helpers
# ---------------------------------------------------------------------------


NOW = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)


def test_format_staleness_none() -> None:
    assert format_staleness(None) == "unbekannt"


def test_format_staleness_gerade_eben() -> None:
    assert format_staleness(NOW - timedelta(seconds=10), now=NOW) == "gerade eben"


def test_format_staleness_minutes() -> None:
    assert format_staleness(NOW - timedelta(minutes=23), now=NOW) == "vor 23 Minuten"


def test_format_staleness_single_minute_grammar() -> None:
    assert format_staleness(NOW - timedelta(minutes=1, seconds=5), now=NOW) == "vor 1 Minute"


def test_format_staleness_hours() -> None:
    assert format_staleness(NOW - timedelta(hours=3), now=NOW) == "vor 3 Stunden"


def test_format_staleness_days() -> None:
    assert format_staleness(NOW - timedelta(days=2, hours=1), now=NOW) == "vor 2 Tagen"


def test_severity_ok_under_one_hour() -> None:
    assert severity_for_staleness(NOW - timedelta(minutes=30), now=NOW) == "ok"


def test_severity_yellow_between_1_and_24() -> None:
    assert severity_for_staleness(NOW - timedelta(hours=5), now=NOW) == "yellow"


def test_severity_red_over_24() -> None:
    assert severity_for_staleness(NOW - timedelta(hours=30), now=NOW) == "red"


def test_severity_red_on_none() -> None:
    assert severity_for_staleness(None, now=NOW) == "red"
