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


def test_root_endpoint_returns_200(client: TestClient) -> None:
    """AC #2: GET / returns a 200 response with a small JSON body."""

    response = client.get("/")
    assert response.status_code == 200

    body = response.json()
    assert body["app"] == "ctrader"
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_pool_is_attached_to_app_state(client: TestClient) -> None:
    """AC #1: lifespan creates the (faked) asyncpg pool and hangs it on app.state."""

    # Accessing app.state inside the TestClient context proves the lifespan
    # ran and create_pool was awaited.
    assert hasattr(app.state, "db_pool")
    assert app.state.db_pool is not None
