# Story 12.2: Bestaetigungs-UI & Atomare Bracket-Order-Submission (Stock + Option, fester Stop)

Status: ready-for-dev

<!-- Created 2026-04-14 after PM-scope-update. Supersedes the old Story 11.2 (Trailing-Stop Aktien-only). New scope: fester STP-Stop + Option-Contract-Qualifizierung + whatIfOrder-Margin-Check + Margin-Acknowledge-Checkbox bei Sell-To-Open. -->

## Story

As a Chef,
I want a mandatory confirmation step with a fixed-stop-loss bracket submission for both stocks and single-leg options, so that every order has automatic stop protection and I can review the margin requirement (especially for short options) before sending.

## Acceptance Criteria

1. **Given** ein ausgefuelltes Quick-Order-Formular (Stock oder Option), **When** "Weiter" geklickt wird, **Then** zeigt eine Bestaetigungs-Zusammenfassung alle Parameter + berechnetes Stop-Level + geschaetztes Risiko in $ **ohne Scrollen in einem Viewport** (FR54, NFR-R3b).

2. **Given** eine Option-Order im Bestaetigungs-Viewport, **When** inspiziert, **Then** wird zusaetzlich die **geschaetzte IB-Margin-Anforderung** via `ib_async.whatIfOrder()` angezeigt, inklusive Initial Margin und Maintenance Margin aus der IB-Response (FR54).

3. **Given** eine Short-Option-Order (Sell-To-Open), **When** die Bestaetigung angezeigt wird, **Then** erfordert der Bestaetigungs-Screen eine explizite **Margin-Acknowledge-Checkbox** "Ich verstehe Margin-Anforderung und Assignment-Risk"; ohne Haken ist "Order senden" disabled (FR54).

4. **Given** eine bestaetigte Stock-Order, **When** der Bestaetigungs-Klick erfolgt, **Then** sendet das System eine atomare Bracket Order via `ib_async`: Parent-Order (Limit, `transmit=False`) + Child-Order (**fester STP-Stop auf Aktien-Preis**, `transmit=True`), mit einer von ctrader generierten `orderRef` als Idempotenz-Key (FR55).

5. **Given** eine bestaetigte Option-Order, **When** der Bestaetigungs-Klick erfolgt, **Then** wird zuerst der Option-Contract via `ib_async.Option(symbol, expiry, strike, right, 'SMART')` qualifiziert, anschliessend eine atomare Bracket Order gesendet: Parent-Order (Limit auf Contract, `transmit=False`) + Child-Order (**fester STP-Stop auf den Option-Preis**, `transmit=True`), mit derselben `orderRef`-Idempotenz (FR55).

6. **Given** die Order (Stock oder Option), **When** gesendet, **Then** wird die `orderRef` als Idempotenz-Schluessel verwendet; ein Retry mit identischer `orderRef` kann keine Duplikat-Order erzeugen (NFR-R3a).

7. **Given** keine Bestaetigung (One-Click), **When** das Formular angezeigt wird, **Then** ist keine One-Click-Platzierung moeglich — der Bestaetigungs-Schritt ist verpflichtend (FR54).

## Tasks / Subtasks

- [ ] Task 1: Preview-Endpoint (AC: 1, 2)
  - [ ] `POST /trades/quick-order/preview` in `app/routers/trades.py` — nimmt Formular-Daten an, validiert, baut Preview-Payload
  - [ ] Bei Option-Modus: `whatIfOrder()` Call fuer Margin-Schaetzung
  - [ ] Returns `quick_order_preview.html` Fragment mit HX-Swap

- [ ] Task 2: Confirmation-Template (AC: 1, 2, 3)
  - [ ] `app/templates/components/quick_order_preview.html` — Grid-Layout
  - [ ] Stock-Variante: Symbol | Side | Qty | Limit | Stop-Level (--accent) | Risk-$
  - [ ] Option-Variante: Contract-String ("SPY 2026-05-16 580 PUT") | Side | Contracts×Multiplier | Limit/C | Stop $/C | Risk-$ | **Margin-Req** (whatIfOrder) + bei Sell-To-Open mit `--color-loss`-Hervorhebung
  - [ ] Bei Short-Option: Pflicht-Checkbox "Ich verstehe Margin und Assignment-Risk"
  - [ ] Submit-Button disabled bis Checkbox gesetzt (Alpine.js `x-data`)

- [ ] Task 3: `order_service.py` — Stock-Bracket (AC: 4, 6)
  - [ ] `app/services/order_service.py` mit `submit_stock_bracket(ib, symbol, side, qty, limit, stop_price) → orderRef`
  - [ ] Nutzt `ib_async.Order` direkt (nicht die `bracketOrder()` Convenience), weil die Convenience-Method nur Stock unterstuetzt und kein `transmit=False/True` Pattern expliziert erlaubt
  - [ ] Parent: Order(action='BUY'/'SELL', orderType='LMT', lmtPrice=limit, totalQuantity=qty, transmit=False, orderRef=orderRef)
  - [ ] Child: Order(action=opposite, orderType='STP', auxPrice=stop_price, totalQuantity=qty, parentId=parent.orderId, transmit=True, orderRef=orderRef+'_stop')

- [ ] Task 4: `order_service.py` — Option-Bracket (AC: 5, 6)
  - [ ] `submit_option_bracket(ib, underlying, expiry, strike, right, side, contracts, limit_per_contract, stop_per_contract) → orderRef`
  - [ ] `contract = Option(underlying, expiry, strike, right, 'SMART', currency='USD')`
  - [ ] `await ib.qualifyContractsAsync(contract)` — populates conId etc.
  - [ ] Same Parent+Child Bracket-Pattern, aber Contract-Target ist das Option-Contract
  - [ ] Stop-Auslöser ist der **Option-Preis**, nicht der Underlying — das ist eine `STP`-Order auf den Option-Contract selbst

- [ ] Task 5: `whatIfOrder()` fuer Margin-Check (AC: 2)
  - [ ] `order_service.py` → `estimate_margin(ib, contract, order) → WhatIfResult`
  - [ ] Nutzt `ib.whatIfOrderAsync()` statt `placeOrder()` — IB returnt Margin-Info ohne die Order tatsaechlich zu senden
  - [ ] Cached fuer 30 Sekunden pro (contract, side, qty) Kombination um IB-Rate-Limits zu schonen

- [ ] Task 6: `orderRef`-Generierung (AC: 6)
  - [ ] `f"ctrader-qo-{uuid.uuid4().hex[:12]}"` — 12 chars zur Sicherheit
  - [ ] Vor dem `placeOrder`-Call persistiert in einer neuen Tabelle `quick_orders` (Migration in dieser Story) mit unique constraint auf orderRef
  - [ ] Bei Retry nach Netzwerkfehler: check ob orderRef in der DB existiert → skip place, re-fetch Status

- [ ] Task 7: Migration
  - [ ] `migrations/0XX_quick_orders.sql` — Tabelle `quick_orders` mit Columns: id, order_ref (unique), proposal_id (nullable — Quick-Orders sind ausserhalb der Approval-Pipeline), asset_class, symbol (fuer Stocks) / underlying+expiry+strike+right (fuer Options), side, quantity_or_contracts, limit_price, stop_price, ib_order_id (nullable bis place), status (submitted/filled/…), created_at, updated_at
  - [ ] Auto-updated_at Trigger wie in anderen Migrations

- [ ] Task 8: Submit-Router (AC: 4, 5, 7)
  - [ ] `POST /trades/quick-order/submit` — akzeptiert bestaetigten Form-State, ruft `submit_stock_bracket()` oder `submit_option_bracket()` je nach asset_class auf
  - [ ] Schreibt quick_orders row VOR place_order (orderRef-Persistenz fuer Idempotenz)
  - [ ] Bei Short-Option: verify dass `acknowledge_margin=true` im Form-Payload (sonst 422)
  - [ ] Kein One-Click: Nur aus der Preview heraus erreichbar, `Referer` / `HX-Request` check optional

- [ ] Task 9: Tests
  - [ ] Unit test: preview shows margin field only for options
  - [ ] Unit test: preview short-option shows acknowledge checkbox
  - [ ] Unit test: preview submit button disabled without ack
  - [ ] Unit test: submit_stock_bracket builds correct Parent + Child Order with transmit pattern
  - [ ] Unit test: submit_option_bracket qualifies contract + builds bracket on option
  - [ ] Unit test: orderRef persisted before place_order (idempotency test)
  - [ ] Unit test: double-submit with same orderRef → no duplicate order
  - [ ] Integration test (skipif no Docker): Migration applies; quick_orders unique on order_ref

## Dev Notes

**Preview-Layout (Short-Option):**
```
┌─ CONFIRM ORDER ─────────────────────────────┐
│ Contract:  SPY 2026-05-16 580 PUT           │
│ Side:      SELL-TO-OPEN                     │
│ Contracts: 5 × 100                          │
│ Limit/C:   $3.20                            │
│ Stop $/C:  $1.60                            │
│ Risk:      $800                             │
│ Margin:    $~12,500  ← whatIfOrder()       │ (--color-loss)
│                                              │
│ ⚠ SHORT OPTION                               │
│ [x] Ich verstehe Margin und Assignment-Risk  │ (pflicht)
│                                              │
│ [Zurück]              [Order senden]         │ (submit disabled bis [x] gesetzt)
└──────────────────────────────────────────────┘
```

**ib_async Bracket-Pattern fuer Stock:**
```python
parent = Order(
    action='BUY',
    orderType='LMT',
    lmtPrice=185.0,
    totalQuantity=100,
    transmit=False,
    orderRef='ctrader-qo-abc123',
)
stop = Order(
    action='SELL',  # opposite of parent
    orderType='STP',
    auxPrice=180.0,  # fester Stop
    totalQuantity=100,
    parentId=parent.orderId,  # set after placing parent
    transmit=True,
    orderRef='ctrader-qo-abc123_stop',
)
p_trade = ib.placeOrder(contract, parent)
stop.parentId = p_trade.order.orderId
ib.placeOrder(contract, stop)
```

**ib_async Option-Contract-Qualifizierung:**
```python
from ib_async import Option

contract = Option('SPY', '20260516', 580.0, 'P', 'SMART', currency='USD')
await ib.qualifyContractsAsync(contract)
# contract.conId is now populated
```

**whatIfOrder-Margin-Check:**
```python
parent_whatif = Order(
    action='SELL',
    orderType='LMT',
    lmtPrice=3.20,
    totalQuantity=5,
    whatIf=True,  # IB returns OrderState with commission + margin
)
trade = ib.placeOrder(option_contract, parent_whatif)
# trade.orderState.initMarginChange / maintMarginChange
```

**Idempotenz via quick_orders-Tabelle:**
1. Generate orderRef = `f"ctrader-qo-{uuid.uuid4().hex[:12]}"`
2. INSERT INTO quick_orders (order_ref, …) — UNIQUE constraint catches duplicates
3. Call `ib.placeOrder(contract, parent)` with orderRef
4. On exception/retry: check if order_ref exists in DB → skip placement, probe IB status
5. On success: UPDATE quick_orders SET ib_order_id = parent.orderId, status = 'submitted'

**File Structure:**
```
app/
├── routers/trades.py              # UPDATE — preview + submit endpoints
├── services/
│   ├── order_service.py           # NEW — submit_stock_bracket, submit_option_bracket
│   └── ib_options_chain.py        # Shared with Story 12.1 (chain fetch + cache)
├── templates/
│   └── components/
│       └── quick_order_preview.html   # NEW
migrations/
└── 0XX_quick_orders.sql           # NEW — quick_orders table
```

### References

- PRD: FR54, FR55, NFR-R3a, NFR-R3b
- Architecture: Decision #9 (order_service.py, trades-Tabelle-Erweiterung, Kill-Switch-Exemption)
- UX-Spec: Component `quick_order_preview`, Journey 6 Schritt 4+5
- epics.md: Epic 12 Story 12.2
- Dependency: Story 12.1 (Quick-Order-Form + Options-Chain-Service), Story 2.2 (IB-Connection-State)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
