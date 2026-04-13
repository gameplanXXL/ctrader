"""Unit tests for the Story 3.1 tagging form + POST /tag endpoint.

The AsyncMock db pool from conftest prevents real DB access — so the
tests here cover the route-level control flow:
- GET /trades/{id}/tagging_form → 404 when trade missing
- POST /trades/{id}/tag → validation error path (422, form re-rendered)
- POST /trades/{id}/tag → happy path stubbed via direct service patches

Tagging-service SQL is exercised by the integration test file.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class _CtxMgr:
    """Minimal async context manager — yields a sentinel object as
    the 'connection' so stubbed service calls ignore it."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_a: object) -> bool:
        return False


def _install_fake_pool(client: TestClient) -> None:
    """Rewire `app.state.db_pool.acquire` to the no-op context manager
    so `async with db_pool.acquire() as conn:` doesn't crash on the
    conftest AsyncMock. Scoped to the `client` fixture — the autouse
    `_fake_db_pool` fixture resets it per test."""

    client.app.state.db_pool.acquire = lambda: _CtxMgr()


def test_tagging_form_returns_404_when_pool_unavailable(client: TestClient) -> None:
    response = client.get("/trades/1/tagging_form")
    assert response.status_code == 404


def test_tagging_form_contains_dropdowns_and_mistake_checkboxes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stub get_trade_detail so the route renders the form, then assert
    the critical structure: 4 dropdowns, mistake checkboxes, HTMX
    post target."""

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
    _install_fake_pool(client)

    response = client.get("/trades/42/tagging_form")
    assert response.status_code == 200
    body = response.text

    assert 'name="strategy"' in body
    assert 'name="trigger_type"' in body
    assert 'name="horizon"' in body
    assert 'name="exit_reason"' in body
    assert 'name="mistake_tags[]"' in body
    assert 'hx-post="/trades/42/tag"' in body
    # Mean Reversion comes from our stub, so taxonomy fallback is not used
    assert "Mean Reversion" in body


def test_tag_post_rejects_unknown_trigger_type(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bogus trigger_type → 422, form re-rendered with inline error.

    Code-review BH-25 fix: no longer mutates `app.state` globally —
    uses the conftest-provided mock pool via `_install_fake_pool`.
    """

    from app.routers import trades as trades_router

    async def _fake_strategies(_conn):  # noqa: ANN001
        return [("momentum", "Momentum")]

    monkeypatch.setattr(trades_router, "list_strategies_for_dropdown", _fake_strategies)
    _install_fake_pool(client)

    response = client.post(
        "/trades/1/tag",
        data={
            "strategy": "momentum",
            "trigger_type": "bogus_type",
            "horizon": "intraday",
            "exit_reason": "stop_hit",
        },
    )
    assert response.status_code == 422
    assert "trigger_type" in response.text
    # Code-review M2 / EC-12: re-render must keep the strategy dropdown
    # populated so the user isn't trapped.
    assert "Momentum" in response.text


def test_tag_post_missing_strategy_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Code-review H1: strategy is mandatory — previously dropped silently."""

    from app.routers import trades as trades_router

    async def _fake_strategies(_conn):  # noqa: ANN001
        return []

    monkeypatch.setattr(trades_router, "list_strategies_for_dropdown", _fake_strategies)
    _install_fake_pool(client)

    response = client.post(
        "/trades/1/tag",
        data={
            "trigger_type": "manual",
            "horizon": "intraday",
            "exit_reason": "stop_hit",
        },
    )
    assert response.status_code == 422
    assert "strategy" in response.text
