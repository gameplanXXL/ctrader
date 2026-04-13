# Story 2.4: Trade-Drilldown — Inline Expansion

Status: review

## Story

As a Chef,
I want to drill into any trade to see full details including P&L, timing, and provenance,
so that I can understand every aspect of a trade decision.

## Acceptance Criteria

1. **Given** eine Trade-Zeile in der Journal-Liste, **When** geklickt, **Then** expandiert eine Detail-Ansicht inline unterhalb der Zeile (nicht als Modal) (FR9, UX-DR25, UX-DR40)
2. **Given** den expandierten Trade-Drilldown, **When** angezeigt, **Then** sind sichtbar: Symbol, Side, Entry/Exit-Preis, Size, P&L (inkl. Gebuehren/Funding-Rates), Expectancy-at-Entry, R-Multiple (oder NULL bei fehlendem Stop-Loss, nie "0"), Zeitstempel, Broker, Strategie (FR12, UX-DR73)
3. **Given** eine offene Inline-Expansion, **When** Escape gedrueckt oder die Zeile erneut geklickt wird, **Then** schliesst sich die Expansion (UX-DR40)
4. **Given** eine offene Expansion, **When** die URL inspiziert wird, **Then** enthaelt sie `?expand={id}` fuer Bookmarkability (UX-DR45)
5. **Given** nur eine Expansion ist erlaubt, **When** eine andere Trade-Zeile geklickt wird, **Then** schliesst sich die aktuelle und oeffnet die neue Expansion (UX-DR40)
6. **Given** den Trade-Drilldown bei Cache-Miss, **When** geladen, **Then** erscheint er innerhalb von 3 Sekunden (NFR-P2)
7. **Given** den Trade-Drilldown, **When** angezeigt, **Then** zeigt er Core-Fields immer, und Advanced-Metrics (MFE/MAE, Regime-Kontext, Full-Trigger-Spec) in expandierbaren Sections (UX-DR100)

## Tasks / Subtasks

- [x] Task 1: Trade-Detail-Query (AC: 2, 6)
  - [x] `app/services/trade_query.py` — `get_trade_detail(trade_id)`
  - [x] JOIN mit spaeter: strategies (Epic 6), fundamentals (Epic 5)
  - [x] Initial: Nur Felder aus trades-Tabelle
- [x] Task 2: P&L-Berechnung mit Fees (AC: 2)
  - [x] `app/services/pnl.py` — `compute_pnl(trade)` inklusive fees
  - [x] CFD-Funding-Rates: Phase 2, vorerst `NULL`
- [x] Task 3: R-Multiple-Berechnung (AC: 2)
  - [x] `app/services/r_multiple.py` — `compute_r_multiple(trade)`
  - [x] Bei fehlendem Stop-Loss: return `None` (kein "0"!)
  - [x] Formel: `(exit_price - entry_price) / (entry_price - stop_price)` (long) bzw. invertiert (short)
- [x] Task 4: Expectancy-at-Entry (AC: 2)
  - [x] `app/services/expectancy.py` — `compute_expectancy_at_entry(trade)`
  - [x] Basiert auf Strategie-Historie (placeholder bis Epic 6 — vorerst NULL)
- [x] Task 5: HTMX Inline-Expansion Route (AC: 1, 3, 5)
  - [x] GET `/trades/{id}/detail_fragment` → rendert detail partial
  - [x] Trade-Row mit `hx-get="/trades/{id}/detail_fragment"` `hx-target="#expansion-{id}"` `hx-push-url="true"`
  - [x] Alpine.js oder vanilla JS fuer Escape-Close
- [x] Task 6: URL-State (AC: 4)
  - [x] `?expand={id}` wird beim Initial-Load ausgewertet
  - [x] Server rendert expanded direkt wenn Parameter vorhanden
- [x] Task 7: Progressive Disclosure (AC: 7)
  - [x] Core-Fields immer sichtbar
  - [x] "Advanced Metrics"-Section collapsible
  - [x] Alpine.js `x-data="{ open: false }"` Pattern

## Dev Notes

**R-Multiple-Business-Rule (FR12, kritisch):**
> "R-Multiple (oder NULL bei fehlendem Stop-Loss, nie '0')"

Fehlender Stop-Loss darf **niemals** als "0 R" dargestellt werden, weil das Aggregationen verfaelschen wuerde. Immer `NULL` (DB) oder `"NULL"` (UI).

**Drilldown Layout (aus UX-Spec UX-DR73, UX-DR100):**
```
┌────────────────────────────────────┐
│ Core Fields:                       │
│   Symbol: AAPL    Side: BUY        │
│   Entry: 150.00   Exit: 155.50     │
│   Size: 100       R-Mult: +0.55R   │
│   P&L: +$549      Expectancy: 0.42 │
├────────────────────────────────────┤
│ [+ Advanced Metrics]               │
│   (collapsed by default)           │
│   MFE/MAE, Regime, Full Trigger    │
├────────────────────────────────────┤
│ Trigger-Provenance: (Story 3.3)    │
├────────────────────────────────────┤
│ Fundamental: (Story 5.2)           │
├────────────────────────────────────┤
│ OHLC-Chart: (Story 4.5)            │
└────────────────────────────────────┘
```

**Wichtig:** Diese Story legt nur das Skelett an. Die Integration mit Fundamental (Epic 5), MAE/MFE (Epic 4), OHLC-Chart (Epic 4) passiert spaeter — der Drilldown wird iterativ erweitert.

**HTMX Pattern fuer Inline-Expansion:**
```html
<!-- Trade-Row mit Click-to-Expand -->
<tr hx-get="/trades/{{ trade.id }}/detail_fragment"
    hx-target="#expansion-{{ trade.id }}"
    hx-swap="innerHTML"
    hx-push-url="/journal?expand={{ trade.id }}">
  ...
</tr>
<tr id="expansion-{{ trade.id }}"></tr>
```

**File Structure:**
```
app/
├── services/
│   ├── trade_query.py              # UPDATE - get_trade_detail
│   ├── pnl.py                      # NEW
│   ├── r_multiple.py               # NEW
│   └── expectancy.py               # NEW (placeholder)
├── routers/
│   └── trades.py                   # NEW - /trades/{id}/detail_fragment
└── templates/
    └── fragments/
        └── trade_detail.html       # NEW
```

### References

- PRD: FR9, FR12, NFR-P2
- UX-Spec: UX-DR25, UX-DR40 (Inline-Expansion), UX-DR45 (URL-State), UX-DR73 (Details-Panel), UX-DR100 (Progressive Disclosure)
- Dependency: Story 2.3 (Trade-Liste + trade_row)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
