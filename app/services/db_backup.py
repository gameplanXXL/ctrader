"""PostgreSQL backup service (Epic 11 / Story 11.3).

Owns:
- `create_backup(db_url=None, backup_dir=None)` — runs `pg_dump`
  via `asyncio.create_subprocess_exec` (never blocks the event
  loop), gzips the output to
  `data/backups/ctrader-YYYY-MM-DD.sql.gz`, chmods `0600`, and
  returns the path.
- `rotate_backups(backup_dir, keep=7)` — deletes everything older
  than the 7 most recent dated backups.
- `get_backup_info(backup_dir=None)` — returns the latest backup
  metadata `{path, size, mtime}` or None for the Health-Widget.

The scheduler (`app/services/scheduler.py`) registers a daily
04:00 UTC job that calls `create_backup()` → `rotate_backups()`.
Manual download is exposed via `GET /settings/backup/download`
(Story 11.3 AC #4).

NFR-S5: the backup directory is created with `0700` and every
backup file is chmod'd to `0600` so other host users can't read
it. `pg_dump` is invoked with `--no-owner --no-acl` so the dump
can be restored into a fresh database with a different owner.
"""

from __future__ import annotations

import asyncio
import gzip
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


_DEFAULT_BACKUP_DIR = Path("data/backups")


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    size_bytes: int
    modified_at: datetime


def _resolve_backup_dir(backup_dir: Path | None = None) -> Path:
    path = backup_dir or _DEFAULT_BACKUP_DIR
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


async def create_backup(
    db_url: str | None = None,
    backup_dir: Path | None = None,
) -> Path:
    """Run `pg_dump` and write a gzipped SQL file to `backup_dir`.

    Uses `asyncio.create_subprocess_exec` so the event loop is never
    blocked. The `db_url` defaults to `settings.database_url` so the
    caller usually doesn't need to pass it.
    """

    dsn = db_url or settings.database_url
    target_dir = _resolve_backup_dir(backup_dir)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    output_path = target_dir / f"ctrader-{timestamp}.sql.gz"

    logger.info("db_backup.starting", path=str(output_path))

    proc = await asyncio.create_subprocess_exec(
        "pg_dump",
        dsn,
        "--format=plain",
        "--no-owner",
        "--no-acl",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err_text = stderr.decode("utf-8", errors="replace")[:1000]
        logger.error(
            "db_backup.pg_dump_failed",
            returncode=proc.returncode,
            stderr_preview=err_text,
        )
        raise RuntimeError(f"pg_dump failed with exit code {proc.returncode}: {err_text}")

    # Gzip the dump stream. This is blocking but bounded by the
    # dump size (expected well under 100 MB for a personal trading
    # DB) — asyncio.to_thread keeps the event loop responsive.
    def _write_gzip() -> None:
        with gzip.open(output_path, "wb") as f:
            f.write(stdout)
        output_path.chmod(0o600)

    await asyncio.to_thread(_write_gzip)

    logger.info(
        "db_backup.completed",
        path=str(output_path),
        size_bytes=output_path.stat().st_size,
    )
    return output_path


def rotate_backups(
    backup_dir: Path | None = None,
    *,
    keep: int = 7,
) -> int:
    """Delete all but the `keep` most recent `ctrader-*.sql.gz` files.

    Returns the number of files deleted.
    """

    target_dir = _resolve_backup_dir(backup_dir)
    files = sorted(target_dir.glob("ctrader-*.sql.gz"))
    if len(files) <= keep:
        return 0
    to_delete = files[:-keep]
    for old in to_delete:
        try:
            old.unlink()
            logger.info("db_backup.rotated", deleted=str(old))
        except OSError as exc:
            logger.warning("db_backup.rotation_failed", path=str(old), error=str(exc))
    return len(to_delete)


def get_backup_info(backup_dir: Path | None = None) -> BackupInfo | None:
    """Return metadata for the most recent backup, or None if empty."""

    target_dir = backup_dir or _DEFAULT_BACKUP_DIR
    if not target_dir.exists():
        return None
    files = sorted(target_dir.glob("ctrader-*.sql.gz"))
    if not files:
        return None
    latest = files[-1]
    stat = latest.stat()
    return BackupInfo(
        path=latest,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )
