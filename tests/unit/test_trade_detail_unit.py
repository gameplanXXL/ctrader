"""Unit tests for the trade-detail fragment route (Story 2.4) without DB.

Verifies the 404 path through the existing AsyncMock pool fixture:
when the pool is mocked, `get_trade_detail` either fails or returns
None, and the route should respond 404 — never crash.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_drilldown_returns_404_when_pool_unavailable(client: TestClient) -> None:
    """With the AsyncMock pool from conftest, the route can't fetch a
    real trade, so it falls through to the 404 path instead of 500.
    """

    response = client.get("/trades/1/detail_fragment")
    assert response.status_code == 404
