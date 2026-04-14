"""Unit tests for Epic 11 — scheduler + health + db_backup."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from app.services.db_backup import (
    _resolve_backup_dir,
    get_backup_info,
    rotate_backups,
)
from app.services.scheduler import (
    JOB_NAMES,
    get_last_job_runs,
    logged_job,
)

# ---------------------------------------------------------------------------
# DB stubs (same shape as the Gordon + regime tests)
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, canned: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self._canned = canned or {}

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchval", sql, args))
        if "INSERT INTO job_executions" in sql:
            return 101
        return self._canned.get("fetchval")

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.calls.append(("fetch", sql, args))
        return self._canned.get("fetch", [])

    async def execute(self, sql: str, *args: Any) -> str:
        self.calls.append(("execute", sql, args))
        return "UPDATE 1"


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _CM:
            async def __aenter__(self):  # noqa: N805
                return conn

            async def __aexit__(self, *_exc):  # noqa: N805
                return None

        return _CM()


# ---------------------------------------------------------------------------
# logged_job — AC 3 + AC 4 of Story 11.1
# ---------------------------------------------------------------------------


async def test_logged_job_writes_success_row_on_happy_path() -> None:
    conn = _FakeConn()
    pool = _FakePool(conn)

    job_fn = AsyncMock()
    wrapped = logged_job("regime_snapshot", job_fn, pool)

    await wrapped()

    assert job_fn.await_count == 1
    # Insert-start + success-update
    sql_sequence = [c[1] for c in conn.calls]
    assert any("INSERT INTO job_executions" in s for s in sql_sequence)
    assert any("status = 'success'" in s for s in sql_sequence)


async def test_logged_job_writes_failure_row_on_exception_and_does_not_reraise() -> None:
    """Story 11.1 AC #4: a failing job must NOT block the next
    scheduled run. The wrapper catches the exception, logs it, and
    updates the row to 'failure' — but never re-raises."""

    conn = _FakeConn()
    pool = _FakePool(conn)

    async def crashing_job() -> None:
        raise RuntimeError("boom")

    wrapped = logged_job("gordon_weekly", crashing_job, pool)

    # Must complete without raising.
    await wrapped()

    failure_updates = [c for c in conn.calls if "status = 'failure'" in c[1]]
    assert len(failure_updates) == 1
    _, _, args = failure_updates[0]
    assert args[0] == 101  # row id
    assert "boom" in args[1]


async def test_logged_job_survives_insert_failure() -> None:
    """If the initial INSERT fails (DB down for a blip), the wrapper
    still tries to run the job body — we only lose the audit row, not
    the heartbeat.
    """

    class _BrokenPool:
        def acquire(self):
            class _CM:
                async def __aenter__(self):  # noqa: N805
                    raise RuntimeError("pool gone")

                async def __aexit__(self, *_exc):  # noqa: N805
                    return None

            return _CM()

    job_fn = AsyncMock()
    wrapped = logged_job("db_backup", job_fn, _BrokenPool())

    await wrapped()
    assert job_fn.await_count == 1


# ---------------------------------------------------------------------------
# get_last_job_runs — never_run default entries
# ---------------------------------------------------------------------------


async def test_get_last_job_runs_fills_never_run_for_missing_jobs() -> None:
    """Jobs that have never run should still appear in the Health-Widget
    with a `never_run` status so Chef sees every registered cron.
    """

    # Only one job has actually run — the others should fall through
    # to the default.
    conn = _FakeConn(
        canned={
            "fetch": [
                {
                    "job_name": "regime_snapshot",
                    "status": "success",
                    "started_at": datetime(2026, 4, 14, 1, 0, tzinfo=UTC),
                    "completed_at": datetime(2026, 4, 14, 1, 0, 3, tzinfo=UTC),
                    "error_message": None,
                },
            ]
        }
    )
    result = await get_last_job_runs(conn)
    job_names = {r["job_name"] for r in result}
    assert job_names == set(JOB_NAMES.keys())

    by_name = {r["job_name"]: r for r in result}
    assert by_name["regime_snapshot"]["status"] == "success"
    assert by_name["gordon_weekly"]["status"] == "never_run"
    assert by_name["db_backup"]["status"] == "never_run"
    assert by_name["mcp_contract_test"]["status"] == "never_run"


# ---------------------------------------------------------------------------
# db_backup — rotation + info
# ---------------------------------------------------------------------------


def test_rotate_backups_keeps_most_recent_n(tmp_path: Path) -> None:
    """Keep the N most recent files, delete the rest."""

    for i in range(1, 11):  # 10 fake backups
        (tmp_path / f"ctrader-2026-04-{i:02d}.sql.gz").write_bytes(b"fake")

    deleted = rotate_backups(tmp_path, keep=7)
    assert deleted == 3
    remaining = sorted(tmp_path.glob("ctrader-*.sql.gz"))
    assert len(remaining) == 7
    # The newest 7 survive
    assert remaining[0].name == "ctrader-2026-04-04.sql.gz"
    assert remaining[-1].name == "ctrader-2026-04-10.sql.gz"


def test_rotate_backups_noop_when_below_keep(tmp_path: Path) -> None:
    for i in range(1, 4):
        (tmp_path / f"ctrader-2026-04-{i:02d}.sql.gz").write_bytes(b"fake")
    deleted = rotate_backups(tmp_path, keep=7)
    assert deleted == 0
    assert len(list(tmp_path.glob("ctrader-*.sql.gz"))) == 3


def test_get_backup_info_returns_none_when_empty(tmp_path: Path) -> None:
    assert get_backup_info(tmp_path) is None


def test_get_backup_info_returns_latest(tmp_path: Path) -> None:
    # Create two files with different mtimes — the glob-sort returns
    # alphabetical order which matches the date-prefixed filename.
    old = tmp_path / "ctrader-2026-04-01.sql.gz"
    new = tmp_path / "ctrader-2026-04-14.sql.gz"
    old.write_bytes(b"old")
    new.write_bytes(b"new")

    info = get_backup_info(tmp_path)
    assert info is not None
    assert info.path == new
    assert info.size_bytes == 3  # len(b"new")


def test_resolve_backup_dir_creates_with_secure_permissions(tmp_path: Path) -> None:
    target = tmp_path / "backups"
    assert not target.exists()
    _resolve_backup_dir(target)
    assert target.exists()
    # Permissions: 0o700 (owner rwx only)
    assert target.stat().st_mode & 0o777 == 0o700
