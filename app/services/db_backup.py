"""PostgreSQL backup service (Epic 11 / Story 11.3).

Owns:
- `create_backup(db_url=None, backup_dir=None)` — runs `pg_dump`
  via `asyncio.create_subprocess_exec`, STREAMS the output into a
  gzip writer (no full-buffer RAM hit), chmods `0600` at `os.open`
  time (no race window), and atomic-renames `*.sql.gz.part` →
  `*.sql.gz` so a partial file never shows up in `get_backup_info`.
- `rotate_backups(backup_dir, keep=7)` — deletes everything older
  than the 7 most recent dated backups. Called from the scheduler's
  `db_backup_job` (code-review H8 / EC-4 / BH-11) so the backup
  directory cannot grow unbounded.
- `get_backup_info(backup_dir=None)` — returns the latest backup
  metadata `{path, size, mtime}` or None for the Health-Widget.

Code-review hardening (Tranche A — Epic 11):

- **H1 / BH-1**: the DSN is NOT passed as a pg_dump CLI argument any
  more. The password leaked to the process table via `/proc/<pid>/cmdline`
  and `ps aux`. Instead we parse the asyncpg-style URL and pass
  `PGHOST` / `PGPORT` / `PGUSER` / `PGPASSWORD` / `PGDATABASE` env
  vars to the subprocess — these live in the child process's
  environment and are not visible in the process list.

- **H2 / BH-2 / EC-9**: `proc.communicate()` used to buffer the entire
  dump in RAM (a 500 MB DB → 1 GB RSS plus a second gzip copy).
  Now we read the stdout in 64KB chunks and feed them into the gzip
  writer via `asyncio.to_thread`, so the event loop is never blocked
  and the memory footprint stays flat.

- **H3 / BH-3 / EC-10**: `gzip.open(path, "wb")` + `chmod(0o600)` had
  a race window where the file had default umask permissions (0o644).
  Now we `os.open(..., O_WRONLY|O_CREAT|O_EXCL, 0o600)` so the file
  is `0o600` from the first byte onward. Partial writes land in a
  `*.sql.gz.part` tempfile and are only atomic-renamed to the final
  name on success, so `get_backup_info` will never surface a
  corrupted file even on OOM-kill mid-write.

NFR-S5: the backup directory is created with `0700` and every
backup file has `0600` from the first byte. `pg_dump` is invoked
with `--no-owner --no-acl` so the dump restores into a fresh
database with a different owner.
"""

from __future__ import annotations

import asyncio
import gzip
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


_DEFAULT_BACKUP_DIR = Path("data/backups")
_STREAM_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    size_bytes: int
    modified_at: datetime


def _resolve_backup_dir(backup_dir: Path | None = None) -> Path:
    path = backup_dir or _DEFAULT_BACKUP_DIR
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Code-review EC-11 / BH-23: `mkdir(mode=...)` only applies to
    # newly created directories. If the dir already exists (bind-mount
    # from host with host umask), force-tighten it here.
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        logger.warning("db_backup.chmod_dir_failed", path=str(path), error=str(exc))
    return path


def _pg_env_from_dsn(dsn: str) -> dict[str, str]:
    """Convert a `postgresql://user:pass@host:port/db` URL into a
    PG-env-var dict suitable for passing to the pg_dump subprocess.

    Code-review H1 / BH-1: the DSN must NOT be on the argv or it
    leaks to `ps aux`. This helper is the single point that extracts
    credentials out of the URL so we can hand them off via env vars
    (not visible in the process list) and pass a stripped-down
    `--dbname=<name>` on the CLI.
    """

    parsed = urlparse(dsn)
    env: dict[str, str] = {}
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    if parsed.path and parsed.path != "/":
        env["PGDATABASE"] = parsed.path.lstrip("/")
    return env


async def create_backup(
    db_url: str | None = None,
    backup_dir: Path | None = None,
) -> Path:
    """Run `pg_dump` and write a gzipped SQL file to `backup_dir`.

    Streams stdout → gzip → atomic rename. See the module docstring
    for the Tranche-A hardening rationale (H1 / H2 / H3).
    """

    dsn = db_url or settings.database_url
    target_dir = _resolve_backup_dir(backup_dir)

    # Code-review M2 / BH-10: include the UTC time so two backups on
    # the same calendar day (manual trigger + 04:00 cron, or a
    # rage-click during testing) cannot overwrite each other.
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    output_path = target_dir / f"ctrader-{timestamp}.sql.gz"
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")

    logger.info("db_backup.starting", path=str(output_path))

    env = {**os.environ, **_pg_env_from_dsn(dsn)}
    pg_database = env.get("PGDATABASE", "")

    proc = await asyncio.create_subprocess_exec(
        "pg_dump",
        "--format=plain",
        "--no-owner",
        "--no-acl",
        f"--dbname={pg_database}" if pg_database else "--dbname=",
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Code-review H3 / BH-3: open the tmp file with 0o600 BEFORE any
    # bytes are written so the file is owner-readable only from byte 0.
    # O_EXCL ensures we never clobber an in-flight `.part` left by an
    # earlier crashed run.
    try:
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        # Previous crashed attempt — unlink and retry once.
        tmp_path.unlink(missing_ok=True)
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

    bytes_written = 0
    try:
        # Code-review H2 / BH-2 / EC-9: stream stdout in 64KB chunks
        # into the gzip writer so we never buffer the full dump in RAM.
        with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb") as gz:
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                # gzip writes are blocking — off-load to the default
                # thread pool so the event loop stays responsive.
                await asyncio.to_thread(gz.write, chunk)
                bytes_written += len(chunk)

        return_code = await proc.wait()
        stderr_bytes = await proc.stderr.read() if proc.stderr is not None else b""

        if return_code != 0:
            err_text = stderr_bytes.decode("utf-8", errors="replace")[:1000]
            logger.error(
                "db_backup.pg_dump_failed",
                returncode=return_code,
                stderr_preview=err_text,
            )
            raise RuntimeError(f"pg_dump failed with exit code {return_code}: {err_text}")

        # Code-review M3 / BH-14: log stderr even on a successful run so
        # warnings (role mismatch, version hints) are visible.
        if stderr_bytes:
            logger.warning(
                "db_backup.pg_dump_stderr",
                stderr_preview=stderr_bytes.decode("utf-8", errors="replace")[:500],
            )

        # Atomic rename: `*.part` → `*.sql.gz`. `get_backup_info` only
        # globs `ctrader-*.sql.gz`, so a crashed run leaves a `.part`
        # file that is ignored.
        tmp_path.replace(output_path)
    except BaseException:
        # On any failure (exception, cancel, OOM), remove the partial
        # file so it never shows up in `get_backup_info`.
        tmp_path.unlink(missing_ok=True)
        raise

    logger.info(
        "db_backup.completed",
        path=str(output_path),
        size_bytes=output_path.stat().st_size,
        uncompressed_bytes=bytes_written,
    )
    return output_path


def rotate_backups(
    backup_dir: Path | None = None,
    *,
    keep: int = 7,
) -> int:
    """Delete all but the `keep` most recent `ctrader-*.sql.gz` files.

    Returns the number of files deleted. Called from the scheduled
    `db_backup_job` after each successful `create_backup` so the
    backup directory has a bounded footprint (Story 11.3 Task 3 /
    code-review EC-4 / BH-11).
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
    """Return metadata for the most recent backup, or None if empty.

    Only considers fully-renamed `ctrader-*.sql.gz` files — the
    `*.sql.gz.part` staging names used during streaming are
    deliberately excluded by the glob pattern.
    """

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


def get_backup_info_async() -> Any:
    """Async wrapper for `get_backup_info` (BH-17 / EC-11 follow-up).

    Filesystem glob + stat are bounded but block the event loop. In
    practice the backup directory has ~7 files so the cost is
    negligible, but for consistency with `collect_health`'s async
    shape we offer an `asyncio.to_thread` wrapper.
    """

    return asyncio.to_thread(get_backup_info)
