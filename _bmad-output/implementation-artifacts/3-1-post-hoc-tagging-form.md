# Story 3.1: Post-hoc-Tagging-Formular

Status: ready-for-dev

## Story

As a Chef,
I want to tag my manual trades with strategy, trigger, horizon, and exit reason,
so that I can later analyze my trading patterns and decision quality.

## Acceptance Criteria

1. **Given** einen ungetaggten manuellen Trade im Drilldown, **When** das Tagging-Formular angezeigt wird, **Then** enthaelt es: Strategy-Dropdown, Trigger-Source, Horizon, Exit-Reason (4 Pflichtfelder) plus optionale Mistake-Tags und Freitext-Notiz (FR15, UX-DR58)
2. **Given** das Strategy-Dropdown, **When** gerendert vor Epic 6 (strategies-Tabelle existiert noch nicht), **Then** zeigt es die Strategie-Kategorien aus `taxonomy.yaml` als Auswahl-Werte an (Fallback-Quelle)
3. **Given** das Strategy-Dropdown, **When** gerendert nach Epic 6 (strategies-Tabelle existiert), **Then** zeigt es die user-definierten Strategie-Instanzen aus der strategies-Tabelle an
4. **Given** das Tagging-Formular, **When** geoeffnet, **Then** ist das erste Feld auto-fokussiert, Tab navigiert zwischen Feldern, Enter auf dem letzten Feld speichert sofort (kein Submit-Button) (UX-DR58, UX-DR62)
5. **Given** die Dropdown-Felder, **When** geoeffnet, **Then** unterstuetzen sie Fuzzy-Search-Filtering fuer schnelle Auswahl (UX-DR60)
6. **Given** ein Trade wurde erfolgreich getaggt, **When** die Submission abgeschlossen ist, **Then** erscheint ein Success-Toast (bottom-right, gruen, 3s) und der naechste ungetaggte Trade wird automatisch angezeigt (UX-DR34, UX-DR51)
7. **Given** Form-Labels, **When** gerendert, **Then** sind sie uppercase, 11px, --text-muted, letter-spacing 0.05em, ueber dem Feld, mit explizitem `<label for>` (UX-DR61)
8. **Given** eine Validierungsverletzung, **When** ein Feld den Fokus verliert (blur), **Then** erscheint ein roter Rahmen + Fehlertext unterhalb des Feldes (UX-DR59)

## Tasks / Subtasks

- [ ] Task 1: Tagging Form Component (AC: 1, 4, 7)
  - [ ] `app/templates/fragments/tagging_form.html`
  - [ ] 4 Dropdowns: strategy, trigger_source, horizon, exit_reason
  - [ ] Optional: mistake_tags (multi-select), freetext note
  - [ ] Auto-focus first field, tab-order, Enter submits
- [ ] Task 2: Fuzzy-Search-Dropdowns (AC: 5)
  - [ ] Alpine.js component mit Fuzzy-Match
  - [ ] Oder vanilla JS mit `<datalist>` + JS filtering
- [ ] Task 3: Toast-Macro implementieren (AC: 6)
  - [ ] `app/templates/components/toast.html` (ersetzt Stub)
  - [ ] Alpine.js fuer auto-dismiss nach 3s
  - [ ] `HX-Trigger: showToast` Response-Header pattern
- [ ] Task 4: Strategy-Dropdown Source-Adapter (AC: 2, 3)
  - [ ] `app/services/strategy_source.py` — `get_strategies_for_dropdown()`
  - [ ] Check ob strategies-Tabelle existiert
  - [ ] Fallback: taxonomy.yaml strategy_categories
  - [ ] Nach Epic 6: Query strategies-Tabelle
- [ ] Task 5: POST /trades/{id}/tag Endpoint (AC: 1, 6)
  - [ ] Validiert Input via Pydantic
  - [ ] UPDATE trades SET trigger_spec = $1 WHERE id = $2
  - [ ] Response mit HX-Trigger-Header fuer Toast
  - [ ] Liefert naechsten ungetaggten Trade als HTMX-Target
- [ ] Task 6: Next-Untagged-Trade Logik (AC: 6)
  - [ ] `app/services/trade_query.py` — `next_untagged_trade()`
  - [ ] Returns Trade mit SQL `WHERE trigger_spec IS NULL ORDER BY opened_at LIMIT 1`
- [ ] Task 7: Inline-Validation (AC: 8)
  - [ ] HTMX `hx-validate="true"` oder Alpine.js
  - [ ] On-blur: Validation-Error anzeigen

## Dev Notes

**Form-Layout (aus UX-DR58):**
```
┌─ TAG THIS TRADE ────────────────────┐
│ STRATEGY                            │
│ [_______________________________▾]  │  ← auto-focus
│ TRIGGER SOURCE                      │
│ [_______________________________▾]  │
│ HORIZON                             │
│ [_______________________________▾]  │
│ EXIT REASON                         │
│ [_______________________________▾]  │
│ MISTAKE TAGS (optional)             │
│ [ ] fomo  [ ] no-stop  [ ] revenge  │
│ NOTE (optional)                     │
│ [______________________________]    │
│ Press ENTER to save                 │
└─────────────────────────────────────┘
```

**Source-Adapter Pattern (Concern m2 Fix):**
```python
async def get_strategies_for_dropdown(db_pool):
    # Check if strategies table exists (post Epic 6)
    exists = await db_pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'strategies')"
    )
    if exists:
        rows = await db_pool.fetch("SELECT id, name FROM strategies WHERE status = 'active'")
        return [{"id": r["id"], "label": r["name"]} for r in rows]
    else:
        # Fallback to taxonomy.yaml
        taxonomy = get_taxonomy()
        return [{"id": c.id, "label": c.label} for c in taxonomy.strategy_categories]
```

**Labels CSS:**
```css
.form-label {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  display: block;
  margin-bottom: 4px;
}
```

**File Structure:**
```
app/
├── services/
│   ├── strategy_source.py          # NEW
│   └── tagging.py                  # NEW
├── routers/
│   └── trades.py                   # UPDATE - POST /trades/{id}/tag
└── templates/
    ├── components/
    │   └── toast.html              # UPDATE (replaces stub)
    └── fragments/
        ├── tagging_form.html       # NEW
        └── trade_detail.html       # UPDATE - integrate form
```

### References

- PRD: FR15
- UX-Spec: UX-DR34 (Post-hoc Journey), UX-DR51 (Toast), UX-DR58 (Tagging Form), UX-DR59 (Validation), UX-DR60 (Fuzzy), UX-DR61 (Labels), UX-DR62 (Max 6 fields)
- Dependency: Story 1.3 (taxonomy), Story 2.4 (Trade-Drilldown)
- Concern m2 aus Readiness-Report: Strategy-Dropdown Fallback-Pattern

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
