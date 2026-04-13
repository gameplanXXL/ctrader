# Story 11.2: Bestaetigungs-UI & Bracket-Order-Submission

Status: ready-for-dev

## Story

As a Chef,
I want a confirmation screen before order submission and atomic bracket order execution,
so that I can review all parameters and have automatic stop-loss protection from the start.

## Acceptance Criteria

1. **Given** ein ausgefuelltes Quick-Order-Formular, **When** "Weiter" geklickt wird, **Then** zeigt eine Bestaetigungs-Zusammenfassung: Symbol, Seite, Menge, Limit, Trailing-Stop-Betrag, berechnetes initiales Stop-Level, geschaetztes Risiko in $ — alles in einem Viewport ohne Scrollen (FR54, NFR-R3b)
2. **Given** die Bestaetigung, **When** der explizite Bestaetigungs-Klick erfolgt, **Then** sendet das System eine Bracket Order via ib_async: Parent (Limit) + Child (Trailing Stop-Loss), atomar (`transmit=False` auf Parent, `transmit=True` auf letzter Child) mit einer ctrader-generierten `orderRef` (FR55)
3. **Given** die Order, **When** gesendet, **Then** wird die orderRef als Idempotenz-Schluessel verwendet; ein Retry kann keine Duplikat-Order erzeugen (NFR-R3a)
4. **Given** keine Bestaetigung (One-Click), **When** das Formular angezeigt wird, **Then** ist keine One-Click-Platzierung moeglich — der Bestaetigungs-Schritt ist verpflichtend (FR54)

## Tasks / Subtasks

- [ ] Task 1: Confirmation-Viewport Template (AC: 1)
  - [ ] `app/templates/components/quick_order_preview.html` (Tier 2, Woche 3)
  - [ ] Alle Parameter als zusammenfassende Ansicht
  - [ ] Berechnete Felder: initial_stop_price, estimated_risk_dollars
  - [ ] **Single-Viewport, kein Scroll (NFR-R3b)** — alle Zahlen ohne Scrollen sichtbar
  - [ ] Bei aktivem Kill-Switch: gelber Warnbanner oberhalb (nicht blockierend — Quick-Order-Exemption)
- [ ] Task 2: order_service.py — Risk-Calculation + Orchestrierung (AC: 1)
  - [ ] `app/services/order_service.py` (dediziert, getrennt von trade_service — Architecture Decision A1)
  - [ ] `calculate_initial_stop(side, limit, trailing_amount, trailing_unit) -> Decimal`
  - [ ] `calculate_risk(quantity, limit, initial_stop) -> Decimal`
  - [ ] `submit_quick_order(spec: QuickOrderRequest) -> OrderSubmitResult` — orchestriert Validation, DB-Insert, Bracket-Submission, Status-Tracking
- [ ] Task 3: Bracket-Order-Submission via clients/ib.py (AC: 2, 3)
  - [ ] Neue Funktion `place_bracket_order(...)` in `app/clients/ib.py` (Erweiterung, nicht neuer Service — Architecture Decision #9)
  - [ ] Verwendet `ib_async.IB.bracketOrder()` Convenience-Methode
  - [ ] Parent: LMT mit `transmit=False`
  - [ ] Child: TRAIL mit `transmit=True`
  - [ ] `orderRef = f"ctrader-quick-{uuid4().hex[:12]}"` — UUID v4 als Idempotenz-Key
- [ ] Task 4: Atomic Submission
  - [ ] Beide Orders in einem Call, letzte mit `transmit=True`
  - [ ] IB processiert atomar
- [ ] Task 5: Idempotency via orderRef (AC: 3, NFR-R3a)
  - [ ] **`order_ref` als UNIQUE-Constraint in erweiterter `trades`-Tabelle** (Architecture Decision C1)
  - [ ] `INSERT INTO trades (order_ref, order_status, limit_price, trailing_stop_amount, ...) ON CONFLICT (order_ref) DO NOTHING` — Collision = "schon gesendet, Status abrufen"
  - [ ] Bei Retry: `order_service.submit_quick_order()` prüft existing row via `order_ref` und returned OrderSubmitResult ohne zweite IB-Submission
- [ ] Task 6: Migration 005_quick_order_columns.sql (Architecture Decision C1)
  - [ ] `ALTER TABLE trades ADD COLUMN order_status order_status_enum NULL` (submitted/filled/partial/rejected/cancelled/synced)
  - [ ] `ALTER TABLE trades ADD COLUMN order_ref TEXT NULL UNIQUE` (Idempotenz-Key)
  - [ ] `ALTER TABLE trades ADD COLUMN limit_price NUMERIC NULL`
  - [ ] `ALTER TABLE trades ADD COLUMN trailing_stop_amount NUMERIC NULL`
  - [ ] `ALTER TABLE trades ADD COLUMN trailing_stop_unit trailing_unit_enum NULL` (absolute/percent)
  - [ ] `ALTER TABLE trades ADD COLUMN submitted_at TIMESTAMPTZ NULL`
  - [ ] Idempotent via `IF NOT EXISTS`-Guards
  - [ ] **Kein separates `ib_quick_orders`-Schema** — Rejected Orders bleiben in `trades` als Provenance-Einträge mit `order_status='rejected'`
- [ ] Task 7: Mandatory Confirmation (AC: 4)
  - [ ] `POST /trades/quick-order` erfordert vorherigen `POST /trades/quick-order/preview`-Call
  - [ ] Backend-Guard: Ohne Preview-Token im Session-State → 400 Error
  - [ ] Keine One-Click-Platzierung moeglich, auch nicht via Direct-API-Call

## Dev Notes

**Bracket-Order-Pattern (ib_async):**
```python
from ib_async import IB, Stock, LimitOrder, Order

async def place_bracket_order(
    ib: IB,
    symbol: str,
    side: str,  # 'BUY' or 'SELL'
    quantity: int,
    limit_price: float,
    trailing_amount: float,
    trailing_unit: str,  # '$' or '%'
    order_ref: str,
):
    contract = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)

    # Parent: Limit Order
    parent = LimitOrder(
        action=side,
        totalQuantity=quantity,
        lmtPrice=limit_price,
        orderRef=order_ref,
        transmit=False,  # Don't send yet
    )

    # Child: Trailing Stop
    child = Order()
    child.action = 'SELL' if side == 'BUY' else 'BUY'
    child.orderType = 'TRAIL'
    child.totalQuantity = quantity
    child.parentId = None  # set after parent placement
    child.orderRef = order_ref + '-tsl'
    child.transmit = True  # Transmit both atomically
    if trailing_unit == '$':
        child.auxPrice = trailing_amount
    else:
        child.trailingPercent = trailing_amount

    # Submit
    parent_trade = ib.placeOrder(contract, parent)
    child.parentId = parent_trade.order.orderId
    child_trade = ib.placeOrder(contract, child)

    return parent_trade, child_trade
```

**Confirmation-Layout (NFR-R3b: Single-Viewport):**
```
┌─ CONFIRM ORDER ──────────────────────────┐
│ Symbol:            AAPL                   │
│ Side:              BUY                    │
│ Quantity:          100                    │
│ Limit Price:       $150.00                │
│ Trailing Stop:     $2.50                  │
│ Initial Stop:      $147.50 (calculated)   │
│ Est. Risk:         $250.00 (calculated)   │
│                                           │
│ ⚠ Diese Order wird sofort platziert      │
│                                           │
│         [Cancel]  [Confirm & Place]       │
└───────────────────────────────────────────┘
```

**Kein One-Click (FR54):**
Backend MUSS einen expliziten Confirmation-Step erzwingen. Frontend-Bypass ist nicht moeglich.

**Trade-Schema-Erweiterung (Architecture Decision C1 — kein separates ib_quick_orders-Schema):**

Die `trades`-Tabelle aus Story 2.1 wird in Migration 005 um Order-Lifecycle-Spalten erweitert. Rejected Orders bleiben in `trades` als Provenance-Eintraege mit `order_status='rejected'` — das ist bewusst Teil des Trigger-Provenance-Versprechens (siehe Architecture Decision #9).

```sql
-- migrations/005_quick_order_columns.sql

-- ENUMs (idempotent)
DO $$ BEGIN
    CREATE TYPE order_status_enum AS ENUM ('synced', 'submitted', 'filled', 'partial', 'rejected', 'cancelled');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE trailing_unit_enum AS ENUM ('absolute', 'percent');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- Spalten auf trades-Tabelle
ALTER TABLE trades ADD COLUMN IF NOT EXISTS order_status order_status_enum NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS order_ref TEXT NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS limit_price NUMERIC NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_stop_amount NUMERIC NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_stop_unit trailing_unit_enum NULL;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ NULL;

-- UNIQUE-Constraint fuer Idempotenz (NFR-R3a)
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_order_ref
    ON trades(order_ref) WHERE order_ref IS NOT NULL;

-- Fuer bestehende synced-Trades explizit 'synced' setzen
UPDATE trades SET order_status = 'synced' WHERE order_status IS NULL;
```

**Bei Quick-Order-Submission wird eine neue Row in `trades` eingefuegt:**

```sql
INSERT INTO trades (
    symbol, asset_class, side, quantity,
    limit_price, trailing_stop_amount, trailing_stop_unit,
    order_ref, order_status, submitted_at,
    trigger_spec, strategy_id, horizon,
    source
)
VALUES ($1, 'stock', $2, $3, $4, $5, $6, $7, 'submitted', NOW(), $8, $9, $10, 'ib')
ON CONFLICT (order_ref) DO NOTHING
RETURNING id;
```

**File Structure (laut Architecture Decision A1 + B2 + #9):**
```
migrations/
└── 005_quick_order_columns.sql         # NEW (ALTER TABLE trades, nicht CREATE TABLE ib_quick_orders)
app/
├── services/
│   └── order_service.py                # NEW - Risk-Calc + Orchestrierung (Decision A1)
├── clients/
│   └── ib.py                           # UPDATE - neue Funktion place_bracket_order() (Decision #9)
├── routers/
│   └── trades.py                       # UPDATE - POST /trades/quick-order/preview, POST /trades/quick-order (Decision B2)
└── templates/
    └── components/
        ├── quick_order_form.html       # Story 11.1
        └── quick_order_preview.html    # NEW - Bestaetigungs-Zusammenfassung
```

### References

- PRD: FR54, FR55, NFR-R3a, NFR-R3b, FR42 (Kill-Switch-Exemption)
- Architecture: Decision #9 IB Quick-Order, Decision A1 (dedizierter order_service), Decision B2 (Router unter trades.py), Decision C1 (erweiterte trades-Tabelle, kein separates ib_quick_orders)
- UX-Spec: Component `quick_order_preview` Tier 2, Journey 6
- Dependency: Story 11.1 (Form), Story 1.6 (MCP-Client fuer IB-Connection), Story 2.1 (trades-Tabelle)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
