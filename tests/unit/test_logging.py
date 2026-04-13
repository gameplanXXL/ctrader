"""Logging configuration tests — Story 1.1 AC #6 (NFR-M4).

Code-review patches:
- P3: redirect `settings.log_file` to a per-test tmp_path so we never
  pollute `<repo>/data/logs/` and so tests stay isolated from each
  other (and from running uvicorn instances on the dev box).
- P16: drop the `or hasattr(logger, "info")` tautology fallback.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from pathlib import Path

import pytest
import structlog

from app.config import settings
from app.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _isolated_log_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `settings.log_file` at a per-test tmp directory so
    `configure_logging` never touches the real `data/logs/` tree.
    """

    monkeypatch.setattr(settings, "log_file", str(tmp_path / "test.log"))


def test_configure_logging_attaches_rotating_handler() -> None:
    """The stdlib root must end up with a RotatingFileHandler at 100 MB / 5 backups."""

    configure_logging()

    rotating = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(rotating) == 1

    handler = rotating[0]
    assert handler.maxBytes == 100 * 1024 * 1024
    assert handler.backupCount == 5


def test_configure_logging_closes_old_handlers_on_reconfigure() -> None:
    """Repeated `configure_logging()` calls must not leak file handles."""

    configure_logging()
    first_rotating = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ][0]

    # Track the underlying stream so we can confirm it's been closed.
    first_stream = first_rotating.stream

    configure_logging()

    # The first rotating handler should no longer be in root_logger.handlers
    # AND its stream should be closed (file descriptor returned to OS).
    second_rotating = [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(second_rotating) == 1
    assert second_rotating[0] is not first_rotating
    # `closed` is True after close(); for some Python builds the stream
    # may be set to None instead. Either is acceptable as "released".
    assert first_stream is None or first_stream.closed


def test_structlog_emits_single_line_json() -> None:
    """A structlog call must serialize to a single-line JSON object.

    Reads the actual rotating log file (anchored at tmp_path by the
    autouse `_isolated_log_path` fixture) so we verify the bytes that
    hit disk, not a side-channel buffer that bypasses the
    ProcessorFormatter.
    """

    configure_logging()

    logger = get_logger("tests.unit.test_logging")
    logger.info("smoke_test", key="value", number=42)

    # Flush all root handlers so the rotating-file write is visible.
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_path = Path(settings.log_file)
    assert log_path.is_file(), f"log file not created at {log_path}"

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines, "structlog produced no output to the rotating file"

    payload = json.loads(lines[-1])
    assert payload["event"] == "smoke_test"
    assert payload["key"] == "value"
    assert payload["number"] == 42
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_get_logger_returns_bound_logger() -> None:
    """Sanity: `get_logger` hands back a structlog bound logger.

    Strict assertion — no `or hasattr(...)` fallback that would let any
    object with an `.info` attribute pass (P16 fix).
    """

    configure_logging()
    logger = get_logger()
    # structlog returns a FilteringBoundLogger by default with our wiring;
    # accept any structlog BoundLoggerBase descendant.
    assert isinstance(logger, structlog.types.BindableLogger | structlog.stdlib.BoundLogger)
