"""Smoke tests for app.main — Story 1.1 ACs #1, #2, #5."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import __version__
from app.config import settings
from app.main import app


def test_app_metadata() -> None:
    """App advertises its title and version (sanity check)."""

    assert app.title == "ctrader"
    assert app.version == __version__


def test_default_host_binds_loopback() -> None:
    """AC #5 / NFR-S2: host defaults to 127.0.0.1, never 0.0.0.0."""

    assert settings.host == "127.0.0.1"


def test_root_redirects_to_journal(client: TestClient) -> None:
    """Story 1.5: GET / redirects to /journal (Chef's primary surface)."""

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/journal"


def test_healthz_endpoint_returns_200(client: TestClient) -> None:
    """Story 1.1 AC #2 (moved to /healthz in Story 1.5): liveness probe."""

    response = client.get("/healthz")
    assert response.status_code == 200

    body = response.json()
    assert body["app"] == "ctrader"
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_pool_is_attached_to_app_state(
    client: TestClient,
    _fake_db_pool: object,
) -> None:
    """AC #1: lifespan creates the (faked) asyncpg pool and hangs it on app.state.

    The conftest fixture returns the exact AsyncMock the lifespan's
    `create_pool()` will yield, so we can assert *identity* — not just
    existence. A regression where the lifespan forgets to set
    `app.state.db_pool` (or sets it to something else) will now fail
    here, which the previous `is not None` check would have missed
    since AsyncMock is always truthy (P15 fix).
    """

    assert app.state.db_pool is _fake_db_pool
