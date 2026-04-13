"""Taxonomy models — typed wrappers around taxonomy.yaml.

Loaded once at startup (Story 1.3, FR14). Every dropdown in the app
sources its options from here so values stay consistent between the
post-hoc tagging form, the strategy template, and the facet filters.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaxonomyEntry(BaseModel):
    """Base shape — every taxonomy item has at least an id and a label."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str = Field(..., min_length=1)
    label: str | None = None
    description: str | None = None


class HorizonEntry(TaxonomyEntry):
    """Horizon entries carry an optional typical-hold hint for the UI."""

    typical_hold_hours: str | None = None
    typical_hold_days: str | None = None


class Taxonomy(BaseModel):
    """Top-level taxonomy aggregate, mirrors taxonomy.yaml structure."""

    model_config = ConfigDict(frozen=True)

    trigger_types: list[TaxonomyEntry]
    exit_reasons: list[TaxonomyEntry]
    regime_tags: list[TaxonomyEntry]
    strategy_categories: list[TaxonomyEntry]
    horizons: list[HorizonEntry]
    mistake_tags: list[TaxonomyEntry]

    @field_validator(
        "trigger_types",
        "exit_reasons",
        "regime_tags",
        "strategy_categories",
        "horizons",
        "mistake_tags",
    )
    @classmethod
    def _section_must_be_non_empty(cls, value: list[TaxonomyEntry]) -> list[TaxonomyEntry]:
        if not value:
            raise ValueError("taxonomy section must not be empty")
        return value

    def ids(self, section: str) -> list[str]:
        """Return the list of `id`s for a given section. Convenience for tests."""

        entries = getattr(self, section)
        return [e.id for e in entries]
