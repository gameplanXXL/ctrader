# Story 10.3: Strategie-Kandidat aus HOT-Pick erstellen

Status: ready-for-dev

## Story

As a Chef,
I want to create a strategy candidate directly from a Gordon HOT-pick,
so that I can quickly act on trend intelligence without manual data entry.

## Acceptance Criteria

1. **Given** einen Gordon-HOT-Pick in der Trends-Ansicht, **When** "Strategie erstellen" geklickt wird, **Then** oeffnet sich das Strategy-Formular mit vorausgefuelltem Symbol, Horizon und Trigger-Quelle (=Gordon) (FR48)
2. **Given** das vorausgefuellte Formular, **When** Chef die restlichen Felder vervollstaendigt und speichert, **Then** wird eine neue Strategie erstellt und verlinkt mit dem Gordon-Snapshot

## Tasks / Subtasks

- [ ] Task 1: Button auf HOT-Pick-Liste (AC: 1)
  - [ ] In Story 10.2 Trends-Page
  - [ ] Jeder HOT-Pick-Eintrag hat Button "Als Strategie anlegen"
- [ ] Task 2: Pre-fill Redirect (AC: 1)
  - [ ] GET `/strategies/new?symbol=NVDA&horizon=swing&trigger_source=gordon`
  - [ ] Query-Params werden ins Strategy-Formular (Story 6.1) uebernommen
- [ ] Task 3: Linkage-Field in strategies-Tabelle (AC: 2)
  - [ ] Migration 018_strategy_source_snapshot.sql
  - [ ] Neue Column `source_snapshot_id INT REFERENCES gordon_snapshots(id)` (nullable)
- [ ] Task 4: Form-Handler-Update
  - [ ] POST /strategies nimmt source_snapshot_id als optional
  - [ ] Speichert Verlinkung
- [ ] Task 5: Strategy-Detail-View zeigt Snapshot-Referenz
  - [ ] Wenn source_snapshot_id gesetzt → Link zum Gordon-Snapshot
  - [ ] Anzeige: "Erstellt aus Gordon Wochen-Radar vom 2026-04-07"

## Dev Notes

**Pre-fill-Pattern:**
```html
<!-- In trends.html HOT-Pick Loop -->
<a href="/strategies/new?symbol={{ pick.symbol }}&horizon={{ pick.horizon }}&trigger_source=gordon&source_snapshot_id={{ snapshot.id }}"
   class="btn btn-sm">
  Als Strategie anlegen
</a>
```

**Strategy-Form Query-Param-Handling:**
```python
@router.get("/strategies/new")
async def new_strategy_form(
    symbol: str | None = None,
    horizon: str | None = None,
    trigger_source: str | None = None,
    source_snapshot_id: int | None = None,
):
    return templates.TemplateResponse(
        "fragments/strategy_form.html",
        {
            "prefill": {
                "name": f"{symbol} ({horizon})" if symbol else "",
                "horizon": horizon,
                "trigger_sources": [trigger_source] if trigger_source else [],
                "source_snapshot_id": source_snapshot_id,
            }
        }
    )
```

**strategies Schema-Erweiterung:**
```sql
ALTER TABLE strategies ADD COLUMN source_snapshot_id INT REFERENCES gordon_snapshots(id);
```

**Strategy-Detail-Link:**
```jinja2
{% if strategy.source_snapshot_id %}
  <a href="/trends?snapshot={{ strategy.source_snapshot_id }}" class="text-[var(--accent)]">
    Erstellt aus Gordon-Snapshot vom {{ snapshot.created_at | format_date }}
  </a>
{% endif %}
```

**File Structure:**
```
migrations/
└── 018_strategy_source_snapshot.sql   # NEW
app/
├── routers/
│   └── strategies.py                  # UPDATE - query-param handling
└── templates/
    ├── pages/
    │   └── trends.html                # UPDATE - add button
    └── fragments/
        └── strategy_form.html         # UPDATE - accept prefill
```

### References

- PRD: FR48
- Dependency: Story 10.1, 10.2 (Gordon-Integration), Story 6.1 (Strategy-Form)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
