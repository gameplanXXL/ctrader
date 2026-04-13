# Story 2.3: Journal-Startseite — Trade-Liste & Untagged-Zaehler

Status: review

## Story

As a Chef,
I want to see all my trades in a unified, chronologically sorted list with an untagged counter,
so that I can quickly scan my trading activity and identify trades that need tagging.

## Acceptance Criteria

1. **Given** Trades aus IB und cTrader existieren in der Datenbank, **When** die Journal-Startseite geladen wird, **Then** werden alle Trades in einer einheitlichen, chronologisch sortierten Liste angezeigt (neueste zuerst) (FR8)
2. **Given** die Trade-Liste, **When** gerendert, **Then** zeigt jede Zeile via trade_row-Macro: Symbol, Side, Entry-Time, P&L (farbig), Trigger-Type, Horizon, Status-Indikator (UX-DR11, UX-DR96)
3. **Given** es existieren untagged manuelle Trades, **When** die Journal-Startseite geladen wird, **Then** wird ein prominenter Zaehler mit Anzahl ungetaggter Trades angezeigt (FR11, UX-DR77)
4. **Given** die Trade-Liste hat mehr als 30 Eintraege, **When** die Seite geladen wird, **Then** wird Pagination mit 30 Trades/Seite angezeigt (`?page=N`) mit Pfeiltasten-Navigation (UX-DR46, UX-DR102)
5. **Given** die Journal-Startseite, **When** geladen bei <= 2000 Trades, **Then** laedt sie vollstaendig innerhalb von 1.5 Sekunden (NFR-P1)
6. **Given** P&L-Werte in der Trade-Liste, **When** gerendert, **Then** sind Gewinne in #3fb950, Verluste in #f85149, R-Multiples mit einer Dezimale, NULL als "NULL", leere Felder als em-dash (UX-DR69, UX-DR70)

## Tasks / Subtasks

- [x] Task 1: Trade Query Service (AC: 1, 4, 5)
  - [x] `app/services/trade_query.py` mit `list_trades(page, per_page=30)`
  - [x] SQL: `SELECT ... FROM trades ORDER BY opened_at DESC LIMIT 30 OFFSET ?`
  - [x] Zaehler: `COUNT(*) FROM trades WHERE trigger_spec IS NULL AND broker = 'ib'`
- [x] Task 2: trade_row Macro implementieren (AC: 2, 6)
  - [x] `app/templates/components/trade_row.html` (ersetzt Stub)
  - [x] Jinja2-Macro mit Parameter `trade`
  - [x] Spalten: Symbol, Side, Entry-Time, P&L (colored), Trigger-Type, Horizon, Status
  - [x] Monospace-Numerik rechtsbuendig
  - [x] Null-Handling: em-dash fuer leer, "NULL" fuer R-Multiple ohne Stop
- [x] Task 3: Journal-Startseite Template (AC: 1, 2, 3)
  - [x] `app/templates/pages/journal.html` erweitern
  - [x] Import trade_row macro
  - [x] Untagged-Counter-Banner oben (prominent)
  - [x] Trade-Liste darunter
- [x] Task 4: Pagination (AC: 4)
  - [x] Query-Param `?page=N`
  - [x] Pagination-Controls: "Zurueck | Seite X von Y | Weiter"
  - [x] Keyboard: Arrow-Keys (Alpine.js oder vanilla JS)
- [x] Task 5: Performance-Test (AC: 5)
  - [x] Seed: 2000 Trades
  - [x] Measure: Page-Load-Time
  - [x] Assert: <= 1.5s
- [x] Task 6: P&L-Formatting (AC: 6)
  - [x] Jinja2 Filter `format_pnl(value)` → returns (class, text)
  - [x] Grün wenn > 0, Rot wenn < 0, neutral wenn 0 oder NULL

## Dev Notes

**trade_row Macro Signature:**
```jinja2
{% macro trade_row(trade) %}
<tr class="hover:bg-[var(--bg-surface)]" data-trade-id="{{ trade.id }}">
  <td class="font-mono">{{ trade.symbol }}</td>
  <td>{{ trade.side }}</td>
  <td class="font-mono text-right">{{ trade.opened_at | format_time }}</td>
  <td class="font-mono text-right {{ pnl_class(trade.pnl) }}">{{ trade.pnl | format_pnl }}</td>
  <td>{{ trade.trigger_type | default('—') }}</td>
  <td>{{ trade.horizon | default('—') }}</td>
  <td>{{ status_badge(trade.status) }}</td>
</tr>
{% endmacro %}
```

**Status-Indikator-Werte (UX-DR77):**
- `untagged` → orange badge
- `awaiting_approval` → yellow badge
- `approved` → neutral
- `rejected` → gray

**Untagged-Counter-SQL:**
```sql
SELECT COUNT(*) FROM trades
WHERE trigger_spec IS NULL
  AND broker = 'ib'
  AND closed_at IS NOT NULL;  -- nur abgeschlossene
```

**Pagination URL-State:**
- Default: `/journal` (page=1)
- Navigate: `/journal?page=2`
- Combined with facets: `/journal?page=2&asset_class=stock` (kommt in Story 4.1)

**NFR-P1 Messung:**
- Journal-Seite mit 2000 Trades seeden
- `curl -w "%{time_total}" http://127.0.0.1:8000/journal` sollte <= 1.5s sein
- Test via pytest + httpx.AsyncClient

**File Structure:**
```
app/
├── services/
│   └── trade_query.py              # NEW
├── routers/
│   └── pages.py                    # UPDATE - journal endpoint
├── templates/
│   ├── components/
│   │   └── trade_row.html          # UPDATE (ersetzt Stub)
│   └── pages/
│       └── journal.html            # UPDATE
└── filters/
    └── formatting.py               # NEW - Jinja2 filters
```

### References

- PRD: FR8, FR11, FR12, NFR-P1
- UX-Spec: UX-DR11 (trade_row), UX-DR46 (pagination), UX-DR69/70 (P&L formatting), UX-DR77 (status), UX-DR96 (dense rows)
- Dependency: Story 2.1 (trades-Tabelle), Story 1.5 (Component-Stubs)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
