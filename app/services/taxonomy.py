"""Taxonomy loader + singleton accessor.

`load_taxonomy()` reads taxonomy.yaml from the project root, validates it
against `Taxonomy`, and caches the result. `get_taxonomy()` is the
FastAPI-friendly accessor — wire it into routes via `Depends`.

Fail-fast on missing or malformed file (Story 1.3 AC #2).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.logging import get_logger
from app.models.taxonomy import Taxonomy

logger = get_logger(__name__)

# Project-root relative default. Override in tests via `load_taxonomy(path=...)`.
DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "taxonomy.yaml"


def load_taxonomy(path: Path | None = None) -> Taxonomy:
    """Read and validate a taxonomy.yaml file.

    Raises:
        RuntimeError: if the file does not exist (fail-fast at startup).
        ValidationError: if any required section is missing or empty.
    """

    target = path or DEFAULT_TAXONOMY_PATH
    if not target.is_file():
        logger.error("taxonomy.missing", path=str(target))
        raise RuntimeError(f"taxonomy.yaml not found at {target}")

    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        logger.error("taxonomy.malformed", path=str(target))
        raise RuntimeError(f"taxonomy.yaml at {target} did not parse to a mapping")

    taxonomy = Taxonomy.model_validate(raw)
    logger.info(
        "taxonomy.loaded",
        path=str(target),
        trigger_types=len(taxonomy.trigger_types),
        exit_reasons=len(taxonomy.exit_reasons),
        regime_tags=len(taxonomy.regime_tags),
        strategy_categories=len(taxonomy.strategy_categories),
        horizons=len(taxonomy.horizons),
        mistake_tags=len(taxonomy.mistake_tags),
    )
    return taxonomy


@lru_cache(maxsize=1)
def get_taxonomy() -> Taxonomy:
    """Singleton accessor. First call loads from disk; subsequent calls are cached.

    Use `get_taxonomy.cache_clear()` in tests if you need to swap the file
    out from under the cache.
    """

    return load_taxonomy()
