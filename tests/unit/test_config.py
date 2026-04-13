"""Settings unit tests — config defaults hold the NFRs in place."""

from __future__ import annotations

from app.config import settings


def test_log_rotation_matches_nfr_m4() -> None:
    """NFR-M4: 100 MB per file, 5 rotations."""

    assert settings.log_file_max_bytes == 100 * 1024 * 1024
    assert settings.log_file_backup_count == 5


def test_db_pool_sizes_match_architecture() -> None:
    """Architecture Decision: asyncpg pool min=2, max=10 for single-user."""

    assert settings.db_pool_min_size == 2
    assert settings.db_pool_max_size == 10


def test_host_default_is_loopback() -> None:
    """NFR-S2: default host must be 127.0.0.1, never 0.0.0.0."""

    assert settings.host == "127.0.0.1"
