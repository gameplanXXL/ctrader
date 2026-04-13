# Story 2.1: Trade-Datenmodell & IB Flex Query Import

Status: in-progress

## Story

As a Chef,
I want to import my historical IB stock and options trades via Flex Query,
so that my trading history is captured in ctrader from day one.

## Acceptance Criteria

1. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die `trades`-Tabelle erstellt mit: id, symbol, asset_class, side, quantity, entry_price, exit_price, opened_at (TIMESTAMPTZ), closed_at, pnl, fees, broker (trade_source enum), perm_id, trigger_spec (JSONB), und allen relevanten Indizes (FR1, FR2)
2. **Hinweis:** `strategy_id` und `agent_id` werden NICHT in dieser Story angelegt — sie werden per ALTER TABLE in Story 6.1 (strategy_id) und Story 8.1 (agent_id) ergaenzt
3. **Given** eine IB Flex Query XML-Datei mit Aktien-Trades, **When** der Import ausgefuehrt wird, **Then** werden alle Trades korrekt geparst und in die trades-Tabelle eingefuegt (FR1)
4. **Given** eine IB Flex Query XML-Datei mit Single-Leg-Options-Trades, **When** der Import ausgefuehrt wird, **Then** werden Options-Trades korrekt importiert; Multi-Leg-Spreads werden ignoriert mit Log-Warnung (FR2)
5. **Given** ein Trade mit identischem permId existiert bereits, **When** derselbe Trade erneut importiert wird, **Then** wird kein Duplikat erstellt; die Zeile bleibt unveraendert (FR4, NFR-R1)

## Tasks / Subtasks

- [ ] Task 1: Migration 002_trades_table.sql (AC: 1)
  - [ ] Tabelle `trades` mit allen Spalten
  - [ ] UNIQUE constraint auf `(broker, perm_id)`
  - [ ] Indices: `idx_trades_symbol`, `idx_trades_opened_at`, `idx_trades_broker`, GIN `idx_trades_trigger_spec`
- [ ] Task 2: Pydantic-Models (AC: 1)
  - [ ] `app/models/trade.py` mit `Trade` Model
  - [ ] Enum-Bindings an trade_source, trade_side
- [ ] Task 3: IB Flex Query Parser (AC: 3, 4)
  - [ ] `app/services/ib_flex_import.py`
  - [ ] XML-Parsing via `xml.etree.ElementTree` oder `lxml`
  - [ ] Handles Trades-Node fuer Aktien
  - [ ] Handles OptionsTrades-Node fuer Single-Leg
  - [ ] Multi-Leg-Spread-Detection (TradeID-Gruppierung) + Skip mit WARN
- [ ] Task 4: Duplikat-Erkennung via permId (AC: 5)
  - [ ] INSERT ... ON CONFLICT (broker, perm_id) DO NOTHING
  - [ ] Return-Count (imported, skipped)
- [ ] Task 5: CLI-Command / Endpoint fuer Import (AC: 3, 4)
  - [ ] `python -m app.cli ib-flex-import <xml-file>`
  - [ ] Oder POST `/admin/import/ib-flex` mit file upload
- [ ] Task 6: Integration-Tests (AC: 3, 4, 5)
  - [ ] Test mit Sample-XML fuer Aktien
  - [ ] Test mit Sample-XML fuer Options
  - [ ] Test Duplikat-Import (Row-Count unveraendert)

## Dev Notes

**IB Flex Query XML Structure (vereinfacht):**
```xml
<FlexQueryResponse>
  <FlexStatements>
    <FlexStatement accountId="U12345">
      <Trades>
        <Trade
          tradeID="12345"
          permID="1234567890"
          symbol="AAPL"
          assetCategory="STK"
          buySell="BUY"
          quantity="100"
          tradePrice="150.00"
          ibCommission="-1.0"
          dateTime="20260410;093000"
          ...
        />
      </Trades>
      <OptionsTrades>
        <!-- Options, ggf. mit LegId fuer Multi-Leg -->
      </OptionsTrades>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
```

**Trades Table Schema:**
```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL,  -- 'stock', 'option', 'crypto', 'cfd'
    side trade_side NOT NULL,
    quantity NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    pnl NUMERIC,
    fees NUMERIC DEFAULT 0,
    broker trade_source NOT NULL,
    perm_id TEXT NOT NULL,
    trigger_spec JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (broker, perm_id)
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_opened_at ON trades(opened_at DESC);
CREATE INDEX idx_trades_broker ON trades(broker);
CREATE INDEX idx_trades_trigger_spec ON trades USING GIN (trigger_spec);
```

**Wichtige Hinweise:**
- FR2 explizit: Nur **Single-Leg** Options-Trades im MVP. Multi-Leg (Spreads) wird als WARNING geloggt und uebersprungen.
- Die `pnl`-Spalte ist NULL, solange der Trade offen ist (kein closed_at)
- `trigger_spec` wird in dieser Story NICHT befuellt (kommt in Epic 3)

**File Structure:**
```
migrations/
└── 002_trades_table.sql
app/
├── models/
│   └── trade.py              # NEW
├── services/
│   └── ib_flex_import.py     # NEW
└── cli/
    └── ib_flex_import.py     # NEW (CLI entrypoint)
```

**Dependencies:**
- `ib_async` (fuer spaetere Live-Sync Story 2.2)
- Fuer Flex XML: Standard `xml.etree` reicht, keine zusaetzliche Dep

### References

- PRD: FR1, FR2, FR4, NFR-R1
- Architecture: "Database & Data Architecture", "IB Integration" — `ib_async` + Flex Queries
- CLAUDE.md: "Locked Technical Decisions" — `ib_async` (nicht `ib_insync`)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
