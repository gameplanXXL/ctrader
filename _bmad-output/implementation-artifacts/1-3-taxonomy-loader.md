# Story 1.3: Taxonomie-Loader (taxonomy.yaml)

Status: review

## Story

As a Chef,
I want the system to load trading taxonomy from a YAML file,
so that trigger types, exit reasons, regime tags, strategies, and horizons are consistent across the application.

## Acceptance Criteria

1. **Given** taxonomy.yaml existiert mit Trigger-Typen, Exit-Gruenden, Regime-Tags, Strategie-Kategorien, Horizon-Optionen und Mistake-Tags, **When** die App startet, **Then** sind alle Taxonomie-Eintraege geladen und als Singleton verfuegbar (FR14)
2. **Given** taxonomy.yaml fehlt, **When** die App startet, **Then** wird ein klarer Fehler geloggt und die App bricht kontrolliert ab (fail fast)
3. **Given** ein beliebiges Modul fragt Taxonomie-Daten an, **When** die Daten zurueckgegeben werden, **Then** stammen sie aus derselben Singleton-Instanz

## Tasks / Subtasks

- [x] Task 1: taxonomy.yaml Schema definieren (AC: 1)
  - [x] `taxonomy.yaml` im Projekt-Root mit 6 Sections
  - [x] 8 trigger_types, 8 exit_reasons, 7 regime_tags, 7 strategy_categories, 4 horizons, 9 mistake_tags
  - [x] Werte abgeleitet aus UX-Spec und PRD
- [x] Task 2: Pydantic-Models fuer Taxonomie (AC: 1, 3)
  - [x] `app/models/taxonomy.py` mit `TaxonomyEntry` (base), `HorizonEntry` (extended), `Taxonomy` (aggregate)
  - [x] `model_config = ConfigDict(frozen=True)` — immutable Singleton
  - [x] `field_validator` fuer alle 6 Sections: raise wenn empty (Fail-Fast)
  - [x] Convenience-Methode `Taxonomy.ids(section)` fuer Tests
- [x] Task 3: Loader-Service mit Singleton-Pattern (AC: 1, 3)
  - [x] `app/services/taxonomy.py` mit `load_taxonomy(path=None)` Funktion
  - [x] Singleton via `@lru_cache(maxsize=1)` auf `get_taxonomy()`
  - [x] Dependency-Injection-tauglich: `Depends(get_taxonomy)` in spaeteren Routern
  - [x] `DEFAULT_TAXONOMY_PATH` Konstante fuer Projekt-Root-Override
- [x] Task 4: Fail-Fast bei fehlender Datei (AC: 2)
  - [x] `app/main.py` Lifespan ruft `load_taxonomy()` **vor** `run_migrations()` auf
  - [x] `get_taxonomy.cache_clear()` vor Load, dann primen
  - [x] Bei FileNotFoundError: structlog `taxonomy.missing` ERROR + `raise RuntimeError`
  - [x] Bei Non-Mapping-YAML: `taxonomy.malformed` ERROR + RuntimeError
- [x] Task 5: Unit-Tests (AC: 1, 2, 3)
  - [x] `test_load_valid_yaml_returns_taxonomy` — happy-path
  - [x] `test_real_project_taxonomy_loads` — echte committed taxonomy.yaml
  - [x] `test_missing_file_raises_runtime_error` — AC #2
  - [x] `test_empty_section_raises_validation_error` — Pydantic-Validator
  - [x] `test_non_mapping_yaml_raises_runtime_error` — YAML-Liste statt Mapping
  - [x] `test_get_taxonomy_returns_same_instance` — AC #3 (Singleton-Identity)
  - [x] `test_cache_clear_releases_cached_instance` — cache_clear-Contract

## Dev Notes

**taxonomy.yaml Beispiel-Struktur:**
```yaml
trigger_types:
  - id: news_event
    label: News-Event
    description: Reaktion auf Unternehmensmeldung
  - id: technical_breakout
    label: Technischer Ausbruch
  # ...

exit_reasons:
  - id: stop_hit
    label: Stop-Loss getriggert
  - id: target_hit
    label: Target erreicht
  - id: time_stop
    label: Zeit-Exit
  # ...

regime_tags:
  - id: bullish_calm
  - id: bearish_panic
  - id: ranging
  # ...

strategy_categories:
  - id: mean_reversion
    label: Mean Reversion
  - id: momentum
    label: Momentum
  # ...

horizons:
  - id: intraday
    label: Intraday
    typical_hold_hours: 1-8
  - id: swing_short
    label: Short Swing (< 5d)
    typical_hold_days: 1-4
  - id: swing_long
    label: Long Swing (>= 5d)
    typical_hold_days: 5-30
  - id: position
    label: Position
    typical_hold_days: 30+

mistake_tags:
  - id: fomo
    label: FOMO (Fear of Missing Out)
  - id: no_stop
    label: Ohne Stop-Loss
  - id: revenge
    label: Revenge-Trading
  - id: overrode_own_rules
  - id: oversized
  - id: ignored_risk_gate
```

**Architektur-Hinweis:**
- Die Taxonomie ist **Quelle der Wahrheit** fuer Dropdown-Optionen in allen Forms
- Story 3.1 (Tagging-Form) verwendet sie als Fallback-Quelle fuer Strategy-Dropdown vor Epic 6
- Story 6.1 (Strategy-Management) ergaenzt user-definierte Strategien, die strategy_categories referenzieren

**Zu erstellende Dateien:**
```
taxonomy.yaml                      # Projekt-Root
app/models/taxonomy.py             # Pydantic Models
app/services/taxonomy.py           # Loader + Singleton
tests/unit/test_taxonomy.py
```

### References

- PRD: `prd.md` — FR14
- CLAUDE.md — "taxonomy.yaml" als Teil der Projektstruktur
- UX-Spec: `ux-design-specification.md` — Mistake-Tag-System (UX-DR110)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context), bmad-dev-story workflow, 2026-04-13.

### Completion Notes List

- **Alle 3 AC erfuellt**, 7 Unit-Tests fuer den Loader gruen, 22/22 Unit-Tests gesamt.
- **Fail-Fast-Layering:** Drei Fehlerkategorien werden klar getrennt: (1) Datei fehlt → `RuntimeError("not found")`, (2) YAML parst nicht zu Mapping → `RuntimeError("did not parse to a mapping")`, (3) Mapping verletzt Schema → `pydantic.ValidationError`. Alle drei werden im Test abgedeckt.
- **Lifespan-Reihenfolge:** `configure_logging → load_taxonomy → run_migrations → create_pool → yield`. Taxonomy laedt vor den Migrations, weil ein kaputter Taxonomy-File einen App-Start auch ohne DB-Zugriff scheitern lassen sollte (billig zu verifizieren).
- **HorizonEntry extra-fields:** `TaxonomyEntry` nutzt `extra="allow"`, damit `HorizonEntry` die `typical_hold_hours`/`typical_hold_days`-Felder ohne eigenes Subklassen-Handling aufnehmen kann. Pydantic-v2-Pattern.
- **Singleton-Pattern via `@lru_cache(maxsize=1)`** statt Modul-Level-Global: explizite `cache_clear()` fuer Tests, und `get_taxonomy()` bleibt der einzige Entry-Point fuer alle Router.

### File List

**Neu erstellt (5):**
- `taxonomy.yaml` — Projekt-Root, 6 Sections, ~45 Eintraege
- `app/models/__init__.py` — Package-Marker
- `app/models/taxonomy.py` — `TaxonomyEntry`, `HorizonEntry`, `Taxonomy`
- `app/services/__init__.py` — Package-Marker
- `app/services/taxonomy.py` — `load_taxonomy()`, `get_taxonomy()` singleton
- `tests/unit/test_taxonomy.py` — 7 Unit-Tests

**Geaendert (1):**
- `app/main.py` — Lifespan ruft `load_taxonomy()` vor `run_migrations()` auf

### Change Log

- 2026-04-13: Story 1.3 implementiert. Taxonomy mit 6 Sections + Pydantic-Validierung + lru_cache-Singleton + Lifespan-Hook. 7 neue Unit-Tests. Status ready-for-dev → review.
