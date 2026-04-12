# Story 6.4: Strategy-Notizen & Versionshistorie

Status: ready-for-dev

## Story

As a Chef,
I want to write notes on my strategies with version history,
so that I can document my evolving thinking about each approach.

## Acceptance Criteria

1. **Given** die Strategy-Detailansicht, **When** eine Freitext-Notiz geschrieben und gespeichert wird, **Then** wird sie mit Zeitstempel als eigener Eintrag in der Versionshistorie gespeichert (FR37)
2. **Given** mehrere Notizen zu einer Strategie, **When** die Versionshistorie angezeigt wird, **Then** sind alle Notizen chronologisch sortiert mit Zeitstempel sichtbar (FR37)

## Tasks / Subtasks

- [ ] Task 1: Migration 009_strategy_notes_table.sql
  - [ ] Tabelle `strategy_notes`: id, strategy_id (FK), content TEXT, created_at TIMESTAMPTZ
- [ ] Task 2: Notes-Service
  - [ ] `app/services/strategy_notes.py` — add_note, list_notes
- [ ] Task 3: Notes-Section in Strategy-Detail
  - [ ] Neue Section im strategy_detail.html
  - [ ] Textarea fuer neue Notiz
  - [ ] Liste mit Zeitstempel-Sortierung
- [ ] Task 4: POST /strategies/{id}/notes Endpoint
- [ ] Task 5: Test: Notizen bleiben bestehen nach Update der Strategy

## Dev Notes

**Schema:**
```sql
CREATE TABLE strategy_notes (
    id SERIAL PRIMARY KEY,
    strategy_id INT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_strategy_notes_strategy_id ON strategy_notes(strategy_id, created_at DESC);
```

**Wichtig:** Notizen sind **append-only** (analog zu Audit-Log, aber ohne DB-Trigger). Kein Edit, kein Delete. Jede Notiz ist ein eigener historischer Snapshot.

**UI-Layout:**
```
┌─ Notes ───────────────────────────────────┐
│ [New note textarea.............]          │
│                               [Save]      │
├───────────────────────────────────────────┤
│ 2026-04-10 14:23                          │
│ Viktor's Rating war falsch positiv fuer   │
│ EARN-Plays. Ab jetzt nur bei Post-Earnings│
│                                           │
│ 2026-04-05 09:15                          │
│ Strategie erweitert auf Crypto-Breakouts  │
│                                           │
│ 2026-04-01 10:00                          │
│ Initiale Strategie-Definition             │
└───────────────────────────────────────────┘
```

**File Structure:**
```
migrations/
└── 009_strategy_notes_table.sql    # NEW
app/
├── services/
│   └── strategy_notes.py           # NEW
└── templates/
    └── fragments/
        └── strategy_notes.html     # NEW (included in strategy_detail.html)
```

### References

- PRD: FR37
- Dependency: Story 6.1 (strategies-Tabelle)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
