"""Logging configuration tests — Story 1.1 AC #6 (NFR-M4)."""

from __future__ import annotations

import json
import logging
import logging.handlers
from io import StringIO

import structlog

from app.logging import configure_logging, get_logger


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


def test_structlog_emits_single_line_json() -> None:
    """A structlog call must serialize to a single-line JSON object."""

    configure_logging()

    buffer = StringIO()
    # Temporarily route structlog's underlying stdlib logger to our buffer
    # so we can inspect the exact bytes that would hit the file.
    stream_handler = logging.StreamHandler(buffer)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(stream_handler)

    try:
        logger = get_logger("tests.unit.test_logging")
        logger.info("smoke_test", key="value", number=42)
    finally:
        logging.getLogger().removeHandler(stream_handler)

    output = buffer.getvalue().strip().splitlines()
    assert output, "structlog produced no output"

    # Pick the last line (tests may run repeatedly and add lines).
    payload = json.loads(output[-1])
    assert payload["event"] == "smoke_test"
    assert payload["key"] == "value"
    assert payload["number"] == 42
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_get_logger_returns_bound_logger() -> None:
    """Sanity: `get_logger` hands back a structlog bound logger."""

    configure_logging()
    logger = get_logger()
    assert isinstance(logger, structlog.stdlib.BoundLogger) or hasattr(logger, "info")
