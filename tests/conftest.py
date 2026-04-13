"""Shared pytest fixtures.

Story 1.1 scope: we fake the asyncpg pool so the app can be started in a
unit test without a running PostgreSQL. Real DB integration tests land
in Story 1.2 (migrations framework) and use testcontainers.

Code-review patches:
- P13: clear the taxonomy lru_cache on teardown so cross-test state
  doesn't leak.
- P17: `mcp_handshake` is no longer mocked because the lifespan only
  calls it when `settings.mcp_fundamental_url` is set, which is never
  the case in unit tests. The dead fake was removed.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import main as app_module
from app.main import app
from app.services.taxonomy import get_taxonomy


@pytest.fixture(autouse=True)
def _fake_db_pool(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace asyncpg + migrations with AsyncMocks for unit tests.

    The lifespan still exercises `run_migrations`, `create_pool` and
    `close_pool`, but none actually touch a database. Real DB
    integration tests live in `tests/integration/` and use
    testcontainers.

    Returns the fake pool so individual tests can assert against the
    same instance the lifespan was handed.
    """

    fake_pool = AsyncMock(name="asyncpg.Pool")

    async def _fake_create_pool() -> AsyncMock:
        return fake_pool

    async def _fake_close_pool(_pool: AsyncMock) -> None:
        return None

    async def _fake_run_migrations() -> list[str]:
        return []

    async def _fake_connect_ib(*_args: object, **_kwargs: object) -> None:
        # IB is OPTIONAL (Story 2.2). Unit tests never touch a real
        # gateway — return None so `ib_available` stays False.
        return None

    async def _fake_disconnect_ib(_ib: object) -> None:
        return None

    monkeypatch.setattr(app_module, "create_pool", _fake_create_pool)
    monkeypatch.setattr(app_module, "close_pool", _fake_close_pool)
    monkeypatch.setattr(app_module, "run_migrations", _fake_run_migrations)
    monkeypatch.setattr(app_module, "connect_ib", _fake_connect_ib)
    monkeypatch.setattr(app_module, "disconnect_ib", _fake_disconnect_ib)
    return fake_pool


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache() -> Iterator[None]:
    """Clear the taxonomy lru_cache before AND after every test so
    cross-test state cannot leak (the cache is process-global and
    survives test boundaries by default).
    """

    get_taxonomy.cache_clear()
    yield
    get_taxonomy.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI TestClient that drives the full lifespan (startup + shutdown)."""

    with TestClient(app) as test_client:
        yield test_client
