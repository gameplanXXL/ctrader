"""Integration test: audit_log is append-only (Story 7.5 AC #2 / NFR-S3).

Code-review H7 / Auditor: the Story-7.5 Task 4 explicitly requires an
automated test that verifies the BEFORE UPDATE OR DELETE trigger on
`audit_log` actually raises. Until now the trigger was only manually
probed during smoke tests, which leaves a regression window if someone
alters migration 008 or drops the trigger.

This module runs the full migration stack against a real PostgreSQL
container, inserts one audit_log row, and asserts:

1. UPDATE on the row raises `audit log is append-only`
2. DELETE on the row raises `audit log is append-only`
3. INSERT + SELECT still work (the trigger does NOT block the append path)

Marked `integration` so the module is skipped cleanly on machines
without a Docker daemon.
"""

from __future__ import annotations

import shutil

import asyncpg
import pytest

from app.db.migrate import run_migrations

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_docker() -> None:
    """Skip the whole module if the `docker` CLI isn't available."""

    if shutil.which("docker") is None:
        pytest.skip("docker not available — integration tests require a Docker daemon")


async def _insert_audit_row(conn: asyncpg.Connection) -> int:
    """Insert one append-only audit_log row and return its id."""

    return await conn.fetchval(
        """
        INSERT INTO audit_log (event_type, notes)
        VALUES ('proposal_approved', 'append-only test probe')
        RETURNING id
        """
    )


async def test_audit_log_insert_and_select_work(pg_dsn: str) -> None:
    """The trigger must NOT interfere with the happy path."""

    await run_migrations(dsn=pg_dsn)

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        row_id = await _insert_audit_row(conn)
        assert row_id is not None

        row = await conn.fetchrow("SELECT event_type, notes FROM audit_log WHERE id = $1", row_id)
        assert row is not None
        assert row["event_type"] == "proposal_approved"
        assert row["notes"] == "append-only test probe"
    finally:
        await conn.close()


async def test_audit_log_update_is_blocked(pg_dsn: str) -> None:
    """UPDATE on audit_log must raise via the BEFORE trigger."""

    await run_migrations(dsn=pg_dsn)

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        row_id = await _insert_audit_row(conn)

        with pytest.raises(asyncpg.exceptions.RaiseError, match="audit log is append-only"):
            await conn.execute(
                "UPDATE audit_log SET notes = 'tampered' WHERE id = $1",
                row_id,
            )

        # Verify the row is unchanged — defense in depth, the trigger
        # should have rolled the statement back cleanly.
        unchanged = await conn.fetchval("SELECT notes FROM audit_log WHERE id = $1", row_id)
        assert unchanged == "append-only test probe"
    finally:
        await conn.close()


async def test_audit_log_delete_is_blocked(pg_dsn: str) -> None:
    """DELETE on audit_log must raise via the BEFORE trigger."""

    await run_migrations(dsn=pg_dsn)

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        row_id = await _insert_audit_row(conn)

        with pytest.raises(asyncpg.exceptions.RaiseError, match="audit log is append-only"):
            await conn.execute("DELETE FROM audit_log WHERE id = $1", row_id)

        still_there = await conn.fetchval("SELECT 1 FROM audit_log WHERE id = $1", row_id)
        assert still_there == 1
    finally:
        await conn.close()


async def test_audit_log_bulk_update_is_blocked(pg_dsn: str) -> None:
    """Even a WHERE-clause-less UPDATE must be rejected by the row-level
    BEFORE trigger — verifies the trigger fires FOR EACH ROW, not just
    for scoped single-row paths.
    """

    await run_migrations(dsn=pg_dsn)

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        await _insert_audit_row(conn)

        with pytest.raises(asyncpg.exceptions.RaiseError, match="audit log is append-only"):
            await conn.execute("UPDATE audit_log SET notes = 'bulk tamper'")
    finally:
        await conn.close()
