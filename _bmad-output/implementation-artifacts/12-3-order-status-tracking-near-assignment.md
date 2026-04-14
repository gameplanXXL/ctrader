# Story 12.3: Order-Status-Tracking, Auto-Tagging & near-assignment-Warnung

Status: ready-for-dev

<!-- Created 2026-04-14 after PM-scope-update. Supersedes the old Story 11.3. New scope: Option-spezifisches near-assignment-Tagging (Expiry < 3 Tage oder ITM) + Warn-Toast. -->

## Story

As a Chef,
I want my quick orders to be automatically tracked, tagged, and monitored for near-assignment risk so that I don't need manual post-hoc tagging and I get a warning before a short option can be exercised against me.

## Acceptance Criteria

1. **Given** eine platzierte Quick-Order (Stock oder Option), **When** der Status sich aendert, **Then** wird er im Journal aktualisiert: `submitted / filled / partial / rejected / cancelled` ueber den IB Execution-Event-Handler (FR56).

2. **Given** eine Quick-Order bei Platzierung, **When** der Trade im Journal erstellt wird, **Then** wird er automatisch mit Strategie (falls aus dem Quick-Order-Kontext bekannt), Trigger-Quelle, Horizon (`swing`) und Asset-Class (Stock/Option) getaggt — **auto-tagged statt untagged** (FR57).

3. **Given** eine gefuellte Option-Position (filled), **When** ein Scheduled Job taeglich (Story 11.1 / 9.1 Framework) die offenen Option-Positionen pruft, **Then** wird der Tag `near-assignment` gesetzt, sobald die Expiry naeher als **3 Kalendertage** ist **ODER** die Position **ITM** geht (Strike liegt auf der wrong side des aktuellen Underlying-Preises) (FR56).

4. **Given** eine Option-Position mit neu gesetztem `near-assignment`-Tag, **When** Chef die App das naechste Mal oeffnet, **Then** sieht er einen **Warn-Toast** oben rechts: "Option AAPL 180P expires in 2 days — near assignment risk" (FR56, UX-DR52).

5. **Given** eine gefuellte Option-Position, **When** der Trade-Drilldown geoeffnet wird, **Then** zeigt er zusaetzliche Option-spezifische Metadaten: Strike, Expiry, Right, Contract-Multiplier, Days-to-Expiry (live), Moneyness-Indikator (ITM / ATM / OTM).

## Tasks / Subtasks

- [ ] Task 1: IB-Execution-Event-Handler-Erweiterung (AC: 1)
  - [ ] Reuse der Story-2.2-live-sync-Pipeline — `app/services/ib_live_sync.py` hat bereits einen Execution-Event-Listener
  - [ ] Bei neuer orderRef mit `ctrader-qo-` prefix: Match gegen `quick_orders.order_ref`
  - [ ] UPDATE quick_orders SET status = mapped_status, ib_order_id = event.order.orderId
  - [ ] Bei FILLED: INSERT in `trades` mit prefilled trigger_spec, strategy_id, agent_id aus quick_orders

- [ ] Task 2: Auto-Tagging beim INSERT in trades (AC: 2)
  - [ ] `quick_orders` hat Felder: `strategy_id` (optional, wenn aus Kontext bekannt), `trigger_source` (TEXT), `horizon` (immer 'swing'), `asset_class` (stock/option)
  - [ ] Beim FILLED-Event: Trade-Row bekommt trigger_spec JSONB mit `{"source": quick_orders.trigger_source, "strategy_id": quick_orders.strategy_id, "horizon": "swing", "asset_class": quick_orders.asset_class}`
  - [ ] trigger_spec ist nicht NULL → trade ist auto-tagged, erscheint NICHT im Untagged-Counter

- [ ] Task 3: Option-Metadaten auf trades (AC: 5)
  - [ ] Migration `0XX_trades_option_metadata.sql` — ALTER TABLE trades ADD COLUMNS: `option_expiry DATE`, `option_strike NUMERIC`, `option_right CHAR(1) CHECK (option_right IN ('C','P'))`, `option_multiplier INT DEFAULT 100`
  - [ ] Nur fuer `asset_class='option'` befuellt, sonst NULL

- [ ] Task 4: near-assignment-Checker Scheduled Job (AC: 3)
  - [ ] `app/services/near_assignment_check.py` (NEW) mit `check_near_assignment(conn, ib) -> list[trade_id]`
  - [ ] SQL-Query: offene Option-Trades (asset_class='option', closed_at IS NULL) mit expiry < NOW() + interval '3 days'
  - [ ] Fuer jedes matching trade: zusaetzlich Live-Quote via `ib.reqMktData()` + Vergleich mit Strike um ITM zu bestimmen
  - [ ] UPDATE trades SET trigger_spec = jsonb_set(trigger_spec, '{near_assignment}', 'true', true)
  - [ ] APScheduler-Registration in `app/main.py` lifespan: 1× pro Stunde wahrend Marktzeit
  - [ ] Reuse job_executions-logging-Framework aus Story 11.1

- [ ] Task 5: Warn-Toast beim naechsten App-Load (AC: 4)
  - [ ] `app/services/notifications.py` (NEW) oder Erweiterung des Toast-Systems aus Story 7.4
  - [ ] Query bei jedem Seitenaufruf: `SELECT trades WHERE trigger_spec->>'near_assignment'='true' AND seen_by_chef IS NULL`
  - [ ] Template-Partial: `persistent_toasts.html` rendert Warn-Toasts in base.html
  - [ ] "Als gelesen markieren"-Klick → UPDATE trades SET seen_by_chef = NOW() (neue Column notwendig)
  - [ ] Migration `0XX_trades_seen_by_chef.sql` — ALTER TABLE trades ADD COLUMN seen_by_chef TIMESTAMPTZ

- [ ] Task 6: Trade-Drilldown Option-Metadaten (AC: 5)
  - [ ] `app/templates/fragments/trade_detail.html` — Option-Section conditional on asset_class='option'
  - [ ] Felder: Strike, Expiry, Right, Multiplier, Days-to-Expiry (live-computed), Moneyness
  - [ ] Moneyness via Live-Quote + Strike-Vergleich (reuse Logik aus Task 4)
  - [ ] Near-assignment-Indikator als rotes Bubble wenn trigger_spec.near_assignment=true

- [ ] Task 7: Tests
  - [ ] Unit test: execution event → trades row created with prefilled trigger_spec
  - [ ] Unit test: near-assignment-checker picks up expiry < 3d
  - [ ] Unit test: near-assignment-checker picks up ITM position at any DTE
  - [ ] Unit test: near-assignment-checker idempotent (re-run doesn't double-tag)
  - [ ] Unit test: warn-toast shows until seen_by_chef is set
  - [ ] Unit test: trade-drilldown shows option metadata only for asset_class='option'

## Dev Notes

**trigger_spec-JSONB-Shape bei auto-tagged quick orders:**
```json
{
    "source": "quick_order",
    "strategy_id": 5,
    "horizon": "swing",
    "asset_class": "option",
    "confidence_band": "high",
    "near_assignment": false
}
```

**Moneyness-Logik:**
```python
def moneyness(right: str, strike: Decimal, underlying: Decimal) -> str:
    if right == 'C':
        if underlying > strike:
            return 'ITM'
        elif underlying == strike:
            return 'ATM'
        else:
            return 'OTM'
    else:  # Put
        if underlying < strike:
            return 'ITM'
        elif underlying == strike:
            return 'ATM'
        else:
            return 'OTM'
```

**near-assignment-Trigger (ODER-Kombination):**
```sql
SELECT id FROM trades
 WHERE asset_class = 'option'
   AND closed_at IS NULL
   AND (
       option_expiry - CURRENT_DATE <= 3          -- expiry window
       OR (                                         -- or ITM now
           (option_right = 'C' AND live_underlying > option_strike)
           OR (option_right = 'P' AND live_underlying < option_strike)
       )
   )
   AND NOT COALESCE((trigger_spec->>'near_assignment')::boolean, false)
```

Live underlying ist nicht in der DB — muss ueber `reqMktData` + 200ms-Snapshot bezogen werden. Der Checker-Job sollte pro Symbol **cachen** um IB-Rate-Limits zu schonen.

**File Structure:**
```
app/
├── services/
│   ├── ib_live_sync.py              # UPDATE — handle quick-order orderRefs
│   ├── near_assignment_check.py     # NEW — scheduled job
│   └── notifications.py             # NEW — persistent warn-toasts
├── templates/
│   ├── base.html                    # UPDATE — include persistent_toasts fragment
│   └── fragments/
│       ├── persistent_toasts.html   # NEW
│       └── trade_detail.html        # UPDATE — option metadata section
migrations/
├── 0XX_trades_option_metadata.sql   # NEW
└── 0XX_trades_seen_by_chef.sql      # NEW
```

### References

- PRD: FR56, FR57, UX-DR52
- epics.md: Epic 12 Story 12.3
- UX-Spec: Journey 6 Schritt 7, Component `status_badge`
- Dependency: Story 12.2 (quick_orders table + order_service), Story 11.1 (Scheduled-Jobs-Framework), Story 2.2 (ib_live_sync execution-event loop), Story 7.4 (Toast-System)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
