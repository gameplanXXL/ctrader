"""Structured JSON logging via structlog.

Configures both the stdlib logging root (used by uvicorn, fastapi, asyncpg)
and structlog itself so every log line is a single-line JSON object.

Reference:
- NFR-M4: Structured JSON logs, RotatingFileHandler, 100 MB per file, 5 backups.
"""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
from pathlib import Path

import structlog

from app.config import settings

# Project-root anchor — used to resolve relative log paths so the
# location does not depend on `os.getcwd()`. `parents[1]` walks from
# this file (`app/logging.py`) up to the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Loggers whose handlers we adopt into the structlog JSON pipeline. By
# default uvicorn ships its own colorized formatter, so without this we
# get a mix of structlog JSON and plain `INFO: ...` lines (NFR-M4
# violation). Marking them as `propagate=True` and stripping their
# private handlers routes everything through our root.
_PROPAGATING_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "asyncpg",
    "fastapi",
    "httpx",
)


def _resolve_log_path(raw: str) -> Path:
    """Turn the configured `log_file` into an absolute Path.

    Absolute paths are returned as-is. Relative paths are anchored to
    the project root, NOT the current working directory — that way
    `uv run pytest` from any subdirectory still lands in
    `<repo>/data/logs/`.
    """

    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return _PROJECT_ROOT / candidate


def _close_existing_handlers(root_logger: logging.Logger) -> None:
    """Close any handlers we previously attached so file descriptors
    don't accumulate when `configure_logging` is called repeatedly
    (e.g., from a test suite that exercises the lifespan more than once).
    """

    for handler in list(root_logger.handlers):
        with contextlib.suppress(Exception):
            handler.close()


def configure_logging() -> None:
    """Wire up stdlib logging + structlog.

    Called once from the FastAPI lifespan at startup. Idempotent: calling
    it multiple times re-applies the same configuration without leaking
    handlers.
    """

    log_path = _resolve_log_path(settings.log_file)
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
    _close_existing_handlers(root_logger)
    root_logger.setLevel(settings.log_level.upper())
    root_logger.handlers = [file_handler, stream_handler]

    # Reroute third-party loggers through the root so their output also
    # goes through our JSON formatter (NFR-M4: every log line single-
    # line JSON). Without this uvicorn keeps its own colorized handler.
    for name in _PROPAGATING_LOGGERS:
        third_party = logging.getLogger(name)
        third_party.handlers = []
        third_party.propagate = True
        third_party.setLevel(logging.INFO)

    # ------------------------------------------------------------------
    # structlog — JSON output pipeline shared across the app
    # ------------------------------------------------------------------
    structlog.reset_defaults()
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
        # Cache disabled so re-configuration in tests is observable.
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger. Use in modules that need logging."""

    return structlog.get_logger(name)
