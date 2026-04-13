"""Shared fixtures for DB integration tests.

Each integration module that needs a real PostgreSQL spins up its own
`PostgresContainer` via the `pg_container` fixture. The fixture is
session-scoped so a single container is reused across all tests in one
pytest run — that keeps the feedback loop fast.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
    """Yield a running PostgreSQL 16 container for the session.

    Requires a reachable Docker daemon. Tests that use this fixture are
    automatically skipped if Docker isn't available (see `_skip_if_no_docker`
    in individual modules) so CI without Docker degrades gracefully.
    """

    container = PostgresContainer(
        image="postgres:16-alpine",
        username="ctrader_test",
        password="ctrader_test",
        dbname="ctrader_test",
    )
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def pg_dsn(pg_container: PostgresContainer) -> str:
    """Return an asyncpg-compatible DSN for the running container."""

    # testcontainers builds a SQLAlchemy-style URL; asyncpg needs the
    # plain postgres:// scheme without the `+driver` suffix.
    url = pg_container.get_connection_url()
    return url.replace("postgresql+psycopg2://", "postgresql://")
