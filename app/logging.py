"""Structured JSON logging via structlog.

Configures both the stdlib logging root (used by uvicorn, fastapi, asyncpg)
and structlog itself so every log line is a single-line JSON object.

Reference:
- NFR-M4: Structured JSON logs, RotatingFileHandler, 100 MB per file, 5 backups.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

import structlog

from app.config import settings


def configure_logging() -> None:
    """Wire up stdlib logging + structlog.

    Called once from the FastAPI lifespan at startup. Idempotent: calling
    it multiple times re-applies the same configuration without error.
    """

    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Stdlib logging — two handlers (rotating file + stderr)
    # ------------------------------------------------------------------
    formatter = logging.Formatter("%(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_path),
        maxBytes=settings.log_file_max_bytes,
        backupCount=settings.log_file_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    # Clear any handlers set by uvicorn or pytest so our setup wins.
    root_logger.handlers = [file_handler, stream_handler]

    # Silence noisy libraries at default; they can be opted-in via LOG_LEVEL=DEBUG.
    for noisy in ("uvicorn.access", "asyncpg"):
        logging.getLogger(noisy).setLevel(logging.INFO)

    # ------------------------------------------------------------------
    # structlog — JSON output pipeline shared across the app
    # ------------------------------------------------------------------
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger. Use in modules that need logging."""

    return structlog.get_logger(name)
