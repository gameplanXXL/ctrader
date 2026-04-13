"""Shared pytest fixtures.

Story 1.1 scope: we fake the asyncpg pool so the app can be started in a
unit test without a running PostgreSQL. Real DB integration tests land
in Story 1.2 (migrations framework) and use testcontainers.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import main as app_module
from app.main import app


@pytest.fixture(autouse=True)
def _fake_db_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace asyncpg + migrations with AsyncMocks for unit tests.

    The lifespan still exercises `run_migrations`, `create_pool` and
    `close_pool` but none of them actually touch a database. This keeps
    the smoke tests hermetic — real DB integration tests live in
    `tests/integration/` and use testcontainers.
    """

    fake_pool = AsyncMock(name="asyncpg.Pool")

    async def _fake_create_pool() -> AsyncMock:
        return fake_pool

    async def _fake_close_pool(_pool: AsyncMock) -> None:
        return None

    async def _fake_run_migrations() -> list[str]:
        return []

    monkeypatch.setattr(app_module, "create_pool", _fake_create_pool)
    monkeypatch.setattr(app_module, "close_pool", _fake_close_pool)
    monkeypatch.setattr(app_module, "run_migrations", _fake_run_migrations)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI TestClient that drives the full lifespan (startup + shutdown)."""

    with TestClient(app) as test_client:
        yield test_client
