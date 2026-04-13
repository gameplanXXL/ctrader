"""Unit tests for taxonomy loader and singleton accessor (Story 1.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.models.taxonomy import Taxonomy
from app.services.taxonomy import DEFAULT_TAXONOMY_PATH, get_taxonomy, load_taxonomy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_DOC: dict = {
    "trigger_types": [{"id": "manual", "label": "Manuelle Idee"}],
    "exit_reasons": [{"id": "stop_hit", "label": "Stop-Loss"}],
    "regime_tags": [{"id": "ranging", "label": "Seitwaerts"}],
    "strategy_categories": [{"id": "ad_hoc", "label": "Ad-hoc"}],
    "horizons": [{"id": "intraday", "label": "Intraday", "typical_hold_hours": "1-8"}],
    "mistake_tags": [{"id": "fomo", "label": "FOMO"}],
}


def _write_yaml(tmp_path: Path, payload: dict, name: str = "taxonomy.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC #1 — load with valid YAML
# ---------------------------------------------------------------------------


def test_load_valid_yaml_returns_taxonomy(tmp_path: Path) -> None:
    """`load_taxonomy` returns a populated `Taxonomy` for a valid file."""

    path = _write_yaml(tmp_path, VALID_DOC)
    taxonomy = load_taxonomy(path=path)

    assert isinstance(taxonomy, Taxonomy)
    assert taxonomy.ids("trigger_types") == ["manual"]
    assert taxonomy.ids("horizons") == ["intraday"]
    # HorizonEntry passes through extra fields.
    assert taxonomy.horizons[0].typical_hold_hours == "1-8"


def test_real_project_taxonomy_loads() -> None:
    """The committed `taxonomy.yaml` parses cleanly."""

    taxonomy = load_taxonomy(path=DEFAULT_TAXONOMY_PATH)

    assert len(taxonomy.trigger_types) >= 1
    assert "manual" in taxonomy.ids("trigger_types")
    assert "intraday" in taxonomy.ids("horizons")
    assert "fomo" in taxonomy.ids("mistake_tags")


# ---------------------------------------------------------------------------
# AC #2 — fail-fast on missing or malformed file
# ---------------------------------------------------------------------------


def test_missing_file_raises_runtime_error(tmp_path: Path) -> None:
    """Missing taxonomy.yaml is a hard startup failure."""

    missing = tmp_path / "nope.yaml"
    with pytest.raises(RuntimeError, match="not found"):
        load_taxonomy(path=missing)


def test_empty_section_raises_validation_error(tmp_path: Path) -> None:
    """An empty section is rejected by the Pydantic validator."""

    broken = {**VALID_DOC, "trigger_types": []}
    path = _write_yaml(tmp_path, broken)
    with pytest.raises(ValidationError):
        load_taxonomy(path=path)


def test_non_mapping_yaml_raises_runtime_error(tmp_path: Path) -> None:
    """A YAML file that doesn't parse to a dict is rejected."""

    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="did not parse to a mapping"):
        load_taxonomy(path=path)


# ---------------------------------------------------------------------------
# AC #3 — singleton via lru_cache
# ---------------------------------------------------------------------------


def test_get_taxonomy_returns_same_instance() -> None:
    """`get_taxonomy()` returns the cached singleton across calls."""

    get_taxonomy.cache_clear()
    first = get_taxonomy()
    second = get_taxonomy()
    assert first is second


def test_cache_clear_releases_cached_instance() -> None:
    """`cache_clear()` lets the next call re-read the file (used in tests)."""

    get_taxonomy.cache_clear()
    first = get_taxonomy()
    get_taxonomy.cache_clear()
    second = get_taxonomy()
    # Different objects after clear, even though contents are equal.
    assert first is not second
    assert first.ids("trigger_types") == second.ids("trigger_types")
