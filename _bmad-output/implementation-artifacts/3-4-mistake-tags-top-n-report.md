# Story 3.4: Mistake-Tags & Top-N-Report

Status: ready-for-dev

## Story

As a Chef,
I want to tag trading mistakes and see a report of my most costly errors,
so that I can identify and eliminate recurring behavioral patterns.

## Acceptance Criteria

1. **Given** das Tagging-Formular, **When** Mistake-Tags ausgewaehlt werden, **Then** kann ein Trade null, eine oder mehrere Mistake-Tags tragen (fomo, no-stop, revenge, overrode-own-rules, oversized, ignored-risk-gate) (FR18a)
2. **Given** Trades mit Mistake-Tags existieren, **When** der Top-N-Mistakes-Report aufgerufen wird mit einem Zeitfenster, **Then** werden Mistakes nach Haeufigkeit und nach aggregierten $-Kosten (Summe P&L aller Trades mit diesem Tag) sortiert angezeigt (FR18b)
3. **Given** den Mistakes-Report, **When** Facetten aus FR10 angewendet werden, **Then** ist der Report weiter filterbar (FR18b)

## Tasks / Subtasks

- [ ] Task 1: mistake_tags in trigger_spec speichern (AC: 1)
  - [ ] trigger_spec JSONB-Model erweitern um `mistake_tags: list[str]`
  - [ ] Tagging-Form aus Story 3.1: Multi-Select-Checkboxes
  - [ ] Validierung gegen taxonomy.yaml.mistake_tags
- [ ] Task 2: Top-N-Mistakes-Query (AC: 2)
  - [ ] `app/services/mistakes_report.py` — `top_n_mistakes(start_date, end_date, n=10)`
  - [ ] SQL: UNNEST der mistake_tags + GROUP BY tag
  - [ ] Metriken: COUNT(*), SUM(pnl)
  - [ ] Sortierung: nach count DESC oder cost ASC (negativer pnl = hoechste Kosten)
- [ ] Task 3: Report-Page Template (AC: 2, 3)
  - [ ] Neuer Tab / Section auf Journal-Seite oder eigene `/journal/mistakes` Route
  - [ ] Tabelle: Mistake | Haeufigkeit | Gesamt-Kosten | Durchschnitt pro Trade
  - [ ] Time-Range-Selector (All Time, This Week, Last 30 Days, Custom)
- [ ] Task 4: Integration mit Facet-Filter (AC: 3)
  - [ ] Report respektiert aktive Facetten aus Epic 4 Story 4.1
  - [ ] SQL-WHERE wird dynamisch zusammengesetzt
- [ ] Task 5: Tests
  - [ ] Seed: Trades mit verschiedenen Mistakes
  - [ ] Assert: Report aggregiert korrekt
  - [ ] Test: Trade mit mehreren Mistake-Tags erscheint in allen Gruppen

## Dev Notes

**trigger_spec Erweiterung:**
```json
{
  "trigger_type": "technical_breakout",
  "confidence": 0.6,
  "horizon": "intraday",
  "entry_reason": "FOMO-Einstieg nach Gap-Up",
  "source": "manual",
  "followed": true,
  "mistake_tags": ["fomo", "no-stop"]
}
```

**SQL fuer Top-N-Report:**
```sql
SELECT
    mistake_tag,
    COUNT(*) as trade_count,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl
FROM trades,
     jsonb_array_elements_text(trigger_spec->'mistake_tags') as mistake_tag
WHERE opened_at BETWEEN $1 AND $2
  AND trigger_spec ? 'mistake_tags'
GROUP BY mistake_tag
ORDER BY total_pnl ASC  -- meistens negativ, also "teuerste zuerst"
LIMIT 10;
```

**Mistake-Taxonomie (aus Story 1.3 taxonomy.yaml):**
- `fomo` — Fear Of Missing Out
- `no-stop` — Ohne Stop-Loss
- `revenge` — Revenge-Trading nach Verlust
- `overrode-own-rules` — Eigene Regeln ueberstimmt
- `oversized` — Zu grosse Position
- `ignored-risk-gate` — Risk-Gate ignoriert (Bot-Override)

**Report-Layout:**
```
┌─ TOP MISTAKES (Last 30 Days) ────────────────────┐
│ Filter: [Date Range] [Asset-Class] [Strategy]   │
├──────────────────────────────────────────────────┤
│ Mistake          │ Count │  Cost   │ Avg/Trade  │
├──────────────────────────────────────────────────┤
│ revenge          │   12  │ -$2,340 │  -$195     │
│ no-stop          │    8  │ -$1,100 │  -$138     │
│ oversized        │    5  │ -$890   │  -$178     │
│ fomo             │   15  │ -$650   │   -$43     │
└──────────────────────────────────────────────────┘
```

**File Structure:**
```
app/
├── services/
│   └── mistakes_report.py        # NEW
├── routers/
│   └── journal.py                # UPDATE - add /journal/mistakes
└── templates/
    └── pages/
        └── mistakes_report.html  # NEW
```

### References

- PRD: FR18a, FR18b
- Dependency: Story 3.1 (Tagging-Form), Story 3.2 (trigger_spec), Story 1.3 (taxonomy)
- Cross-Reference: Epic 4 Story 4.1 (Facet-Filter-Integration)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
