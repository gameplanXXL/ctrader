"""Minimal PostgreSQL migrations runner.

Discovers `NNN_*.sql` files under `migrations/`, tracks applied versions
in a `schema_migrations` table, and runs each unapplied migration inside
its own transaction. PostgreSQL's transactional DDL makes this safe —
if a migration fails mid-script, the whole thing rolls back.

References:
- CLAUDE.md rule #2: "All PostgreSQL schema changes MUST go through
  versioned migration scripts."
- PRD FR51, NFR-R7 (migrations must be idempotent).
- Architecture `Schema & Migrations`: custom runner, no Alembic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import asyncpg

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


# Project-root relative migrations folder. Overridden in tests.
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

# A migration filename must match `NNN_<slug>.sql` where NNN is zero-padded.
_MIGRATION_FILENAME_RE = re.compile(r"^(\d{3,})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class Migration:
    """A single discovered migration script."""

    version: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations(migrations_dir: Path | None = None) -> list[Migration]:
    """Return migrations in numerically-sorted order by version.

    - Ignores README.md and other non-`.sql` files silently.
    - Logs a WARNING for `.sql` files that don't match the
      `NNN_<slug>.sql` convention so a misnamed file (typo, wrong
      separator) doesn't get silently dropped from the migration set.
    - Raises ValueError on duplicate version numbers — two files with
      the same `NNN_*` prefix would otherwise execute in undefined
      order and only one would get tracked, silently corrupting the
      `schema_migrations` table.
    """

    directory = migrations_dir or DEFAULT_MIGRATIONS_DIR
    if not directory.is_dir():
        raise FileNotFoundError(f"migrations directory not found: {directory}")

    discovered: dict[str, Migration] = {}
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix != ".sql":
            # Non-SQL file (README.md, .gitignore) — silently skip.
            continue
        match = _MIGRATION_FILENAME_RE.match(entry.name)
        if not match:
            # Typo or wrong separator — log loudly so the operator
            # notices the file isn't being applied.
            logger.warning(
                "migrate.malformed_filename",
                file=entry.name,
                expected_pattern=_MIGRATION_FILENAME_RE.pattern,
            )
            continue
        version = match.group(1)
        if version in discovered:
            raise ValueError(
                f"duplicate migration version {version!r}: "
                f"{discovered[version].path.name} vs {entry.name}"
            )
        discovered[version] = Migration(version=version, path=entry)

    # Numeric sort, not lexicographic — otherwise `"1000" < "999"` and
    # the 1000th migration would run before the 999th.
    return sorted(discovered.values(), key=lambda m: int(m.version))


async def _ensure_tracking_table(conn: asyncpg.Connection) -> None:
    """Create `schema_migrations` if it doesn't exist yet.

    Called before discovery so even the very first migration run has a
    place to record itself — otherwise we'd get a chicken-and-egg problem
    for 001 (which creates the tracking table in its own SQL). We
    deliberately duplicate the DDL here; both sides use `IF NOT EXISTS`
    so running them twice is a no-op.
    """

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT        PRIMARY KEY,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


async def _applied_versions(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {row["version"] for row in rows}


async def _apply_one(conn: asyncpg.Connection, migration: Migration) -> None:
    """Run a single migration inside its own transaction."""

    logger.info("migrate.applying", version=migration.version, file=migration.path.name)
    async with conn.transaction():
        await conn.execute(migration.sql)
        await conn.execute(
            "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT (version) DO NOTHING",
            migration.version,
        )
    logger.info("migrate.applied", version=migration.version)


async def run_migrations(
    dsn: str | None = None,
    migrations_dir: Path | None = None,
) -> list[str]:
    """Apply all pending migrations. Returns the list of versions that ran.

    - Opens its own one-shot connection (not a pooled one) so the call
      site can run this during FastAPI startup, before `create_pool` or
      from a CLI context.
    - Skips migrations already recorded in `schema_migrations`.
    - Each migration runs in its own transaction.
    """

    migrations = discover_migrations(migrations_dir)
    if not migrations:
        logger.info("migrate.no_migrations_found")
        return []

    target_dsn = dsn or settings.database_url
    conn = await asyncpg.connect(dsn=target_dsn)
    applied_now: list[str] = []
    try:
        await _ensure_tracking_table(conn)
        already_applied = await _applied_versions(conn)

        for migration in migrations:
            if migration.version in already_applied:
                logger.debug("migrate.skip", version=migration.version, reason="already_applied")
                continue
            await _apply_one(conn, migration)
            applied_now.append(migration.version)
    finally:
        await conn.close()

    logger.info("migrate.done", applied=applied_now, total=len(migrations))
    return applied_now
