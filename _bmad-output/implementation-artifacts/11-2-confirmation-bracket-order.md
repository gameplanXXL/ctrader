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

- [ ] Task 1: Confirmation-Viewport Template
  - [ ] `app/templates/fragments/quick_order_confirm.html`
  - [ ] Alle Parameter als zusammenfassende Ansicht
  - [ ] Berechnete Felder: initial_stop_price, estimated_risk_dollars
  - [ ] Single-Viewport, kein Scroll (NFR-R3b)
- [ ] Task 2: Risk-Calculation-Helper
  - [ ] `app/services/quick_order.py` — `calculate_initial_stop`, `calculate_risk`
  - [ ] Initial-Stop = Limit - Trailing-Amount (long) oder Limit + Trailing-Amount (short)
  - [ ] Estimated-Risk = Quantity * abs(Limit - Initial-Stop)
- [ ] Task 3: Bracket-Order-Submission via ib_async (AC: 2, 3)
  - [ ] `app/services/ib_order.py` — `place_bracket_order(params)`
  - [ ] Parent: LMT mit `transmit=False`
  - [ ] Child: TRAIL mit `transmit=True`
  - [ ] orderRef = `f"ctrader-quick-{uuid4().hex[:12]}"`
- [ ] Task 4: Atomic Submission
  - [ ] Beide Orders in einem Call, letzte mit transmit=True
  - [ ] IB processiert atomar
- [ ] Task 5: Idempotency via orderRef (AC: 3)
  - [ ] orderRef gespeichert als UNIQUE in `ib_quick_orders`-Tabelle (neue Migration)
  - [ ] Bei Retry: check existing orderRef → return existing
- [ ] Task 6: Migration 019_ib_quick_orders.sql
  - [ ] Tabelle `ib_quick_orders`: id, order_ref UNIQUE, parent_order_id, child_order_id, symbol, side, quantity, limit_price, trailing_amount, trailing_unit, status, created_at
- [ ] Task 7: Mandatory Confirmation (AC: 4)
  - [ ] POST /quick-order mit Flag `confirmed=true`
  - [ ] Backend-Guard: if not confirmed → 400 Error

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

**ib_quick_orders Schema:**
```sql
CREATE TABLE ib_quick_orders (
    id SERIAL PRIMARY KEY,
    order_ref TEXT NOT NULL UNIQUE,
    parent_order_id INT,  -- IB's orderId
    child_order_id INT,
    symbol TEXT NOT NULL,
    side trade_side NOT NULL,
    quantity INT NOT NULL,
    limit_price NUMERIC NOT NULL,
    trailing_amount NUMERIC NOT NULL,
    trailing_unit TEXT NOT NULL,  -- '$' or '%'
    strategy_id INT REFERENCES strategies(id),
    status order_status NOT NULL DEFAULT 'submitted',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**File Structure:**
```
migrations/
└── 019_ib_quick_orders.sql           # NEW
app/
├── services/
│   ├── quick_order.py                 # NEW - risk calc
│   └── ib_order.py                    # NEW - bracket order
├── routers/
│   └── quick_order.py                 # UPDATE - /quick-order/confirm
└── templates/
    └── fragments/
        └── quick_order_confirm.html   # NEW
```

### References

- PRD: FR54, FR55, NFR-R3a, NFR-R3b
- Dependency: Story 11.1 (Form), Story 2.2 (ib_async Client)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
