# Story 4.7: Daten-Export (CSV) & Save-Query-Presets

Status: ready-for-dev

## Story

As a Chef,
I want to export my journal data as CSV and save query presets,
so that I can analyze trades in external tools like Excel and quickly recall complex filter combinations.

## Acceptance Criteria

1. **Given** die Journal-Ansicht mit aktiven Filtern, **When** der Export-Button geklickt wird, **Then** wird eine CSV-Datei mit allen gefilterten Trades heruntergeladen (UX-DR105, FR60)
2. **Given** die exportierte CSV, **When** in Excel geoeffnet, **Then** sind alle Spalten korrekt formatiert und importierbar (UX-DR105)
3. **Given** die aktive Query, **When** der Star-Icon im Hero-Block geklickt wird, **Then** wird die Filter-Kombination als benannter Preset gespeichert mit Toast-Bestaetigung (UX-DR106, FR61)

## Tasks / Subtasks

- [ ] Task 1: Migration 005_query_presets_table.sql
  - [ ] `query_presets` Tabelle: id, name, filters (JSONB), created_at
- [ ] Task 2: CSV-Export-Endpoint (AC: 1, 2)
  - [ ] GET `/journal/export?format=csv&...facets` in `app/routers/journal.py`
  - [ ] Wiedernutzung von Story 4.1 Facet-Query (selbe Filter)
  - [ ] Python `csv.DictWriter` mit UTF-8 BOM fuer Excel-Compat
  - [ ] Response: `Content-Type: text/csv`, `Content-Disposition: attachment; filename="ctrader-trades-YYYY-MM-DD.csv"`
- [ ] Task 3: Export-Button im Hero-Block (AC: 1)
  - [ ] Icon-Button rechts im Hero-Block
  - [ ] `onclick="window.location.href='/journal/export?' + currentFilters"`
  - [ ] Oder HTMX `hx-get` mit download-Trigger
- [ ] Task 4: Save-Query-Flow (AC: 3)
  - [ ] Star-Icon im Hero-Block (neben Export)
  - [ ] Click → Prompt-Dialog fuer Preset-Name (Alpine.js modal)
  - [ ] POST `/api/presets` mit {name, filters}
  - [ ] Response-Header `HX-Trigger: showToast`
- [ ] Task 5: Preset-Loading (AC: 3)
  - [ ] GET `/journal?preset=X` laedt Filter aus query_presets-Tabelle
  - [ ] Redirect zur `/journal?facet1=...&facet2=...` URL
- [ ] Task 6: Integration mit Command Palette (AC: 3)
  - [ ] Story 4.6 Command-Palette-Data-Endpoint liest Presets aus query_presets-Tabelle
  - [ ] Presets erscheinen als Items mit Category "Saved Queries"

## Dev Notes

**query_presets Schema:**
```sql
CREATE TABLE query_presets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    filters JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Filters JSONB-Format (entspricht Facet-URL-Params):**
```json
{
  "asset_class": "crypto",
  "broker": "ctrader",
  "trigger_source": ["satoshi"],
  "followed_vs_override": "override",
  "horizon": ["intraday", "swing_short"]
}
```

**CSV-Format:**
```csv
trade_id,symbol,asset_class,side,quantity,entry_price,exit_price,opened_at,closed_at,pnl,fees,r_multiple,broker,strategy,trigger_type,horizon,mistakes
1,AAPL,stock,buy,100,150.00,155.50,2026-04-10T09:30:00Z,2026-04-10T15:45:00Z,549.00,1.00,0.55,ib,momentum,technical_breakout,intraday,
2,BTCUSD,crypto,sell,0.5,68000,67500,2026-04-09T12:00:00Z,2026-04-09T18:30:00Z,250.00,0.50,0.3,ctrader,mean_reversion,news_event,swing_short,"fomo,no-stop"
```

**UTF-8 BOM fuer Excel:**
```python
from io import StringIO
import csv

def generate_csv(trades):
    buffer = StringIO()
    buffer.write('\ufeff')  # UTF-8 BOM
    writer = csv.DictWriter(buffer, fieldnames=[...])
    writer.writeheader()
    for trade in trades:
        writer.writerow(trade)
    return buffer.getvalue()
```

**Star-Icon-Save-Flow:**
```
1. Click Star → Prompt "Preset name:"
2. User input "Satoshi Overrides Lost"
3. POST /api/presets {name, filters: current_url_params}
4. Response: { id: 12, name: "...", success: true }
5. HX-Trigger: showToast → Toast: "Query 'Satoshi Overrides Lost' saved"
6. Star-Icon changes to "filled" state
```

**File Structure:**
```
migrations/
└── 005_query_presets_table.sql     # NEW
app/
├── services/
│   ├── csv_export.py                # NEW
│   └── query_presets.py             # NEW
├── routers/
│   ├── journal.py                   # UPDATE - /journal/export, /journal?preset
│   └── api.py                       # UPDATE - /api/presets
└── templates/
    ├── pages/
    │   └── journal.html             # UPDATE - export + star icons
    └── components/
        └── hero_block.html          # NEW or inline
```

### References

- PRD: FR60 (CSV-Export), FR61 (Query-Presets)
- UX-Spec: UX-DR105 (Data-Export), UX-DR106 (Save-Query)
- Dependency: Story 4.1 (Facet-System), Story 4.6 (Command Palette)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
