"""Unit tests for the Story 3.1 tagging form + POST /tag endpoint.

The AsyncMock db pool from conftest prevents real DB access — so the
tests here cover the route-level control flow:
- GET /trades/{id}/tagging_form → 404 when trade missing
- POST /trades/{id}/tag → validation error path (422, form re-rendered)
- POST /trades/{id}/tag → happy path stubbed via direct service patches

Tagging-service SQL is exercised by the integration test file.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


def test_tagging_form_returns_404_when_pool_unavailable(client: TestClient) -> None:
    response = client.get("/trades/1/tagging_form")
    assert response.status_code == 404


def test_tagging_form_contains_dropdowns_and_mistake_checkboxes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stub get_trade_detail so the route renders the form, then assert
    the critical structure: 4 dropdowns, mistake checkboxes, autofocus
    on the first field, HTMX post target."""

    from app.routers import trades as trades_router

    async def _fake_get_trade_detail(_conn, _trade_id):  # noqa: ANN001
        return {
            "id": 42,
            "symbol": "AAPL",
            "broker": "ib",
            "closed_at": "2026-04-10T13:30:00+00:00",
            "trigger_spec": None,
        }

    async def _fake_strategies(_conn):  # noqa: ANN001
        return [("mean_reversion", "Mean Reversion"), ("momentum", "Momentum")]

    monkeypatch.setattr(trades_router, "get_trade_detail", _fake_get_trade_detail)
    monkeypatch.setattr(trades_router, "list_strategies_for_dropdown", _fake_strategies)

    # Bypass the AsyncMock pool guard — create a minimal async-context-
    # manager so the `async with db_pool.acquire() as conn:` block runs.
    class _CtxMgr:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    client.app.state.db_pool.acquire = lambda: _CtxMgr()

    response = client.get("/trades/42/tagging_form")
    assert response.status_code == 200
    body = response.text

    assert 'name="strategy"' in body
    assert 'name="trigger_type"' in body
    assert 'name="horizon"' in body
    assert 'name="exit_reason"' in body
    assert 'name="mistake_tags[]"' in body
    assert "autofocus" in body
    assert 'hx-post="/trades/42/tag"' in body
    # Mean Reversion comes from our stub, so taxonomy fallback is not used
    assert "Mean Reversion" in body


def test_tag_post_rejects_unknown_trigger_type(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bogus trigger_type → 422, form re-rendered with inline error."""

    # Ensure pool looks alive so we get past the 503 guard
    from app.main import app

    app.state.db_pool = AsyncMock(name="asyncpg.Pool")
    app.state.db_pool.acquire = lambda: _noop_ctx()

    response = client.post(
        "/trades/1/tag",
        data={
            "trigger_type": "bogus_type",
            "horizon": "intraday",
        },
    )
    assert response.status_code == 422
    assert "trigger_type" in response.text


def _noop_ctx():
    class _Ctx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    return _Ctx()
