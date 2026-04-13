"""Unit tests for migration discovery — no DB access needed."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db.migrate import Migration, discover_migrations


def test_discovery_returns_versions_sorted(tmp_path: Path) -> None:
    """Files are returned in strictly ascending version order."""

    (tmp_path / "002_add_trades.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "001_init.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "010_add_strategies.sql").write_text("SELECT 1;", encoding="utf-8")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == ["001", "002", "010"]
    assert all(isinstance(m, Migration) for m in migrations)


def test_discovery_ignores_non_matching_files(tmp_path: Path) -> None:
    """Files that don't match the NNN_slug.sql convention are silently skipped."""

    (tmp_path / "001_init.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "README.md").write_text("# notes", encoding="utf-8")
    (tmp_path / "001_init.down.sql").write_text("-- rollback", encoding="utf-8")
    (tmp_path / "broken.sql").write_text("SELECT 1;", encoding="utf-8")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == ["001"]


def test_discovery_raises_if_directory_missing(tmp_path: Path) -> None:
    """A missing migrations directory is a hard failure, not a silent empty list."""

    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        discover_migrations(missing)


def test_migration_sql_property_reads_file_lazily(tmp_path: Path) -> None:
    """`Migration.sql` reads the file contents on access."""

    path = tmp_path / "001_init.sql"
    path.write_text("CREATE TABLE t (id INT);", encoding="utf-8")

    [migration] = discover_migrations(tmp_path)
    assert migration.sql == "CREATE TABLE t (id INT);"


def test_project_migrations_folder_discovers_001() -> None:
    """The real project `migrations/` contains at least 001_initial_schema.sql."""

    migrations = discover_migrations()
    versions = [m.version for m in migrations]
    assert "001" in versions
    first = next(m for m in migrations if m.version == "001")
    assert first.path.name == "001_initial_schema.sql"
