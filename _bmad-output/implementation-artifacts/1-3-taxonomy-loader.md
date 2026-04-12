# Story 1.3: Taxonomie-Loader (taxonomy.yaml)

Status: ready-for-dev

## Story

As a Chef,
I want the system to load trading taxonomy from a YAML file,
so that trigger types, exit reasons, regime tags, strategies, and horizons are consistent across the application.

## Acceptance Criteria

1. **Given** taxonomy.yaml existiert mit Trigger-Typen, Exit-Gruenden, Regime-Tags, Strategie-Kategorien, Horizon-Optionen und Mistake-Tags, **When** die App startet, **Then** sind alle Taxonomie-Eintraege geladen und als Singleton verfuegbar (FR14)
2. **Given** taxonomy.yaml fehlt, **When** die App startet, **Then** wird ein klarer Fehler geloggt und die App bricht kontrolliert ab (fail fast)
3. **Given** ein beliebiges Modul fragt Taxonomie-Daten an, **When** die Daten zurueckgegeben werden, **Then** stammen sie aus derselben Singleton-Instanz

## Tasks / Subtasks

- [ ] Task 1: taxonomy.yaml Schema definieren (AC: 1)
  - [ ] `taxonomy.yaml` im Projekt-Root erstellen
  - [ ] Sections: `trigger_types`, `exit_reasons`, `regime_tags`, `strategy_categories`, `horizons`, `mistake_tags`
  - [ ] Initial-Werte befuellen (Entwurf-Set aus UX-Spec ableiten)
- [ ] Task 2: Pydantic-Models fuer Taxonomie (AC: 1, 3)
  - [ ] `app/models/taxonomy.py` mit TriggerType, ExitReason, RegimeTag, StrategyCategory, HorizonType, MistakeTag
  - [ ] Root-Model `Taxonomy` mit allen Sections
  - [ ] Validation: keine leeren Sections
- [ ] Task 3: Loader-Service mit Singleton-Pattern (AC: 1, 3)
  - [ ] `app/services/taxonomy.py` mit `load_taxonomy()` Funktion
  - [ ] Singleton via `lru_cache` oder Modul-Level-Variable
  - [ ] Dependency-Injection fuer FastAPI-Routes: `get_taxonomy()`
- [ ] Task 4: Fail-Fast bei fehlender Datei (AC: 2)
  - [ ] Lifespan-Hook: Taxonomie beim Start laden
  - [ ] Bei FileNotFoundError: structlog-ERROR + raise RuntimeError
  - [ ] App-Start wird abgebrochen
- [ ] Task 5: Unit-Tests (AC: 1, 2, 3)
  - [ ] Test: Load mit gueltiger YAML
  - [ ] Test: Missing File → RuntimeError
  - [ ] Test: Malformed YAML → ValidationError
  - [ ] Test: Singleton gibt identische Instanz zurueck

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

### Debug Log References

### Completion Notes List

### File List
