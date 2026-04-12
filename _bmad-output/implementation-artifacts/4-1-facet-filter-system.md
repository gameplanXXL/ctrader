# Story 4.1: Facetten-Filter-System

Status: ready-for-dev

## Story

As a Chef,
I want to filter my journal by multiple facets simultaneously,
so that I can quickly find specific trade patterns and answer analytical questions.

## Acceptance Criteria

1. **Given** die Journal-Startseite, **When** Facetten angezeigt werden, **Then** ist das Facet-Framework implementiert und zeigt die initial verfuegbaren Facetten an: Asset-Class, Broker, Horizon (basieren auf Daten aus Epic 2). Das Framework ist so gebaut, dass weitere Facetten automatisch aktiviert werden, sobald die zugehoerigen Spalten/Datenquellen in spaeteren Epics landen: Strategy (Epic 6), Trigger-Source (Epic 5/10), Followed-vs-Override (Epic 7), Confidence-Band (Epic 7), Regime-Tag (Epic 9). FR10 ist final erfuellt, wenn alle 8 Facetten aktiv sind (spaetestens mit Abschluss Epic 9). (FR10, UX-DR47)
2. **Given** eine noch nicht implementierte Facette (z.B. Strategy vor Abschluss Epic 6), **When** die Facet-Bar gerendert wird, **Then** wird die Facette ausgeblendet ODER als "keine Werte" disabled angezeigt — kein Fehler, kein leerer Dropdown (Graceful Degradation)
3. **Given** eine Facette, **When** ein Wert angeklickt wird, **Then** wird die Trade-Liste sofort per HTMX aktualisiert (kein Apply-Button), innerhalb von 500ms (UX-DR37, NFR-P3)
4. **Given** der facet_chip, **When** aktiv, **Then** ist er in --accent-Farbe hervorgehoben mit Badge-Count und aria-pressed (UX-DR12)
5. **Given** der facet_bar, **When** >= 1 Filter aktiv ist, **Then** erscheint ein Reset-Link; Arrow-Key-Navigation zwischen Chips ist moeglich (UX-DR13)
6. **Given** aktive Facetten, **When** die URL inspiziert wird, **Then** sind alle Filter-States in der URL encodiert (`?asset_class=crypto&trigger_source=satoshi`) via hx-push-url (UX-DR45, FR62, UX-DR108)
7. **Given** Shift+Click auf einen Facet-Wert, **When** bereits ein Wert derselben Facette aktiv ist, **Then** werden beide Werte als Multi-Select kombiniert ("Crypto OR CFDs") (UX-DR38)

## Tasks / Subtasks

- [ ] Task 1: Facet-Framework-Architektur (AC: 1, 2)
  - [ ] `app/services/facets.py` mit `Facet` Protocol/Base-Class
  - [ ] Jede Facette hat: `name`, `is_available()`, `get_values(query)`, `apply_to_query(query, selected)`
  - [ ] Registry-Pattern fuer dynamische Aktivierung
- [ ] Task 2: Initial Facetten implementieren (AC: 1)
  - [ ] AssetClassFacet (aus trades.asset_class)
  - [ ] BrokerFacet (aus trades.broker)
  - [ ] HorizonFacet (aus trigger_spec->>'horizon')
- [ ] Task 3: Placeholder Facetten mit Availability-Check (AC: 2)
  - [ ] StrategyFacet: is_available = strategies-Tabelle existiert
  - [ ] TriggerSourceFacet: is_available = trigger_spec hat agent_id Werte
  - [ ] FollowedFacet: is_available = trigger_spec hat followed Flag gesetzt
  - [ ] ConfidenceBandFacet: is_available = trigger_spec hat confidence
  - [ ] RegimeTagFacet: is_available = regime_snapshots-Tabelle existiert (Epic 9)
- [ ] Task 4: facet_chip Macro (AC: 4)
  - [ ] `app/templates/components/facet_chip.html` (ersetzt Stub)
  - [ ] States: Inactive, Active (accent), Hover, Disabled
  - [ ] Badge mit Count
  - [ ] `aria-pressed="true/false"`
- [ ] Task 5: facet_bar Macro (AC: 5)
  - [ ] `app/templates/components/facet_bar.html` (ersetzt Stub)
  - [ ] Horizontale Strip mit facet_chips
  - [ ] Reset-Link bei aktiven Filtern
  - [ ] role="toolbar" + Arrow-Key-Handling (Alpine.js oder vanilla JS)
- [ ] Task 6: HTMX Facet-Route (AC: 3, 6)
  - [ ] GET `/journal?asset_class=...&broker=...` rendert Journal mit Filter
  - [ ] HTMX: `hx-get` + `hx-target="#trade-list"` + `hx-push-url="true"`
  - [ ] Facet-Bar + Aggregation (aus 4.2) + Trade-List gleichzeitig aktualisieren via `hx-swap-oob`
- [ ] Task 7: Multi-Select via Shift+Click (AC: 7)
  - [ ] JS: Shift+Click setzt Query-Param `?asset_class=stock,crypto`
  - [ ] SQL WHERE `asset_class = ANY($1)`
- [ ] Task 8: Performance-Test (AC: 3)
  - [ ] 2000 Trades seeded
  - [ ] Measure: Facet-Click → New Page < 500ms
- [ ] Task 9: URL-State-Round-Trip (AC: 6, FR62)
  - [ ] Test: Facet setzen → URL copy → neu oeffnen → selbe Filter aktiv

## Dev Notes

**Facet-Framework-Pattern:**
```python
class Facet(Protocol):
    name: str  # 'asset_class'
    label: str  # 'Asset Class'

    async def is_available(self, db_pool) -> bool: ...
    async def get_values(self, db_pool, query: Query) -> list[FacetValue]: ...
    def apply_to_query(self, query: Query, selected: list[str]) -> Query: ...
```

**Graceful Degradation (Issue M2 Fix):**
- Nicht verfuegbare Facetten werden ausgeblendet ODER disabled
- Niemals Fehler bei fehlenden Daten
- Log auf INFO: "Facet X not yet available, hidden"

**URL-State-Pattern (FR62):**
```
/journal?asset_class=crypto&broker=ib&horizon=intraday
/journal?asset_class=stock,crypto&trigger_source=satoshi
/journal?page=2&asset_class=crypto  # combined with pagination
```

**Reset-Link:** Ein Klick → `/journal` ohne Query-Params

**File Structure:**
```
app/
├── services/
│   ├── facets/
│   │   ├── __init__.py               # NEW
│   │   ├── base.py                   # NEW - Facet Protocol
│   │   ├── asset_class.py            # NEW
│   │   ├── broker.py                 # NEW
│   │   ├── horizon.py                # NEW
│   │   ├── strategy.py               # NEW (placeholder)
│   │   ├── trigger_source.py         # NEW (placeholder)
│   │   └── registry.py               # NEW
│   └── trade_query.py                # UPDATE - apply facets
├── routers/
│   └── journal.py                    # UPDATE - facet parameters
└── templates/
    └── components/
        ├── facet_chip.html           # UPDATE
        └── facet_bar.html            # UPDATE
```

### References

- PRD: FR10, FR62, NFR-P3
- UX-Spec: UX-DR12/13 (Chips/Bar), UX-DR37 (Facet-Filter-Pattern), UX-DR38 (Multi-Select), UX-DR45 (URL-State), UX-DR47 (8 Facetten), UX-DR108 (URL-Sharing)
- Issue M2 aus Readiness-Report (Framework-Approach)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
