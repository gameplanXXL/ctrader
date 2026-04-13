# Story 11.3: Order-Status-Tracking & Auto-Tagging

Status: ready-for-dev

## Story

As a Chef,
I want my quick orders to be automatically tracked and tagged in the journal,
so that I don't need to manually enter trade details after placing an order.

## Acceptance Criteria

1. **Given** eine platzierte Quick-Order, **When** der Status sich aendert, **Then** wird er im Journal aktualisiert: submitted / filled / partial / rejected / cancelled (FR56)
2. **Given** eine Quick-Order bei Platzierung, **When** der Trade im Journal erstellt wird, **Then** wird er automatisch mit Strategie, Trigger-Quelle und Horizon aus dem Quick-Order-Formular getaggt (auto-tagged, kein Post-hoc-Tagging noetig) (FR57)

## Tasks / Subtasks

- [ ] Task 1: Extended Quick-Order-Form (Story 11.1 Update)
  - [ ] Zusaetzliche Felder fuer Auto-Tagging: Strategy, Trigger-Source, Horizon
  - [ ] Strategy aus strategies-Tabelle (post Epic 6 — Cross-Epic-Dependency, akzeptabel weil Epic 6 vor Epic 11)
  - [ ] Trigger-Source aus taxonomy.yaml
  - [ ] **Auto-Tagging passiert bei Submission** (nicht erst bei Fill): Die `trades`-Row wird mit `trigger_spec`, `strategy_id`, `horizon` direkt beim INSERT in Story 11.2 befuellt
- [ ] Task 2: ib_async Order-Status-Events (AC: 1)
  - [ ] Subscribe auf `ib.orderStatusEvent` fuer Quick-Orders (orderRef-Prefix `ctrader-quick-`)
  - [ ] **Update `trades.order_status`** basierend auf Event (nicht ib_quick_orders — die Tabelle existiert nicht, Architecture Decision C1)
  - [ ] Mapping: Submitted/Filled/PartiallyFilled/Rejected/Cancelled → `order_status_enum`
- [ ] Task 3: Auto-Merge bei Fill (AC: 2)
  - [ ] Bei FILLED → `UPDATE trades SET order_status='filled', entry_price=<avgFillPrice>, opened_at=<fillTime>, perm_id=<permId> WHERE order_ref=<orderRef>`
  - [ ] **Kein INSERT** — die Row existiert bereits seit Submission (Story 11.2)
  - [ ] Der Merge-Flow via `order_ref` ist das Herzstueck von Decision C1 (Trade ist Trade, egal welcher Lifecycle-Status)
  - [ ] `trigger_spec` wurde bereits bei Submission gefuellt:
    ```json
    {
      "trigger_type": "manual_quick_order",
      "confidence": null,
      "horizon": "...",
      "entry_reason": "Quick Order",
      "source": "manual",
      "followed": true
    }
    ```
- [ ] Task 4: Status-Display im Journal (AC: 1)
  - [ ] Journal zeigt Quick-Orders sofort als `trades`-Zeile mit `status_badge` (submitted/filled/partial/rejected/cancelled)
  - [ ] Bei `submitted` zeigt die Zeile noch kein P&L (nur Limit-Preis + Trailing-Stop)
  - [ ] Bei `filled` erscheint die normale Trade-Info (entry_price, opened_at, etc.)
  - [ ] Bei `rejected` / `cancelled` bleibt die Zeile als Provenance-Eintrag sichtbar (filterbar ueber Status-Facette)
- [ ] Task 5: Partial-Fill Handling
  - [ ] Bei `PartiallyFilled` → `UPDATE trades SET order_status='partial', quantity=<filledQty>, entry_price=<avgFillPrice>` (average der bisherigen Fills)
  - [ ] Bei letztem Fill → `order_status='filled'`, vollstaendige Quantity
  - [ ] Keine separaten Trade-Rows pro Fill — alles in derselben Row via Update

## Dev Notes

**Extended Quick-Order-Form (Update zu Story 11.1):**

```
┌─ QUICK ORDER — AAPL ─────────────┐
│ SIDE     [Buy] [Sell]             │
│ QUANTITY  [100]                   │
│ LIMIT     [150.00]                │
│ TRAIL     [2.50] [$][%]           │
│ STRATEGY  [Momentum Stocks ▾]     │  ← NEW (Story 11.3)
│ TRIGGER   [technical_breakout ▾]  │  ← NEW
│ HORIZON   [intraday ▾]            │  ← NEW
│        [Continue →]                │
└───────────────────────────────────┘
```

Das sind 7 Felder. Grenzt an die Max-6-Regel (UX-DR62) — aber vertretbar, da Auto-Tagging spaeter Zeit spart.

**ib_async Status-Event-Listener (Merge-Flow via order_ref):**
```python
# In app/services/order_service.py — registriert beim FastAPI-Lifespan-Start
ib.orderStatusEvent += on_order_status_change

async def on_order_status_change(trade):
    if not trade.order.orderRef.startswith("ctrader-quick-"):
        return  # Not our order

    order_ref = trade.order.orderRef
    ib_status = trade.orderStatus.status  # "Submitted", "Filled", "PartiallyFilled", "Cancelled", ...

    new_status = map_ib_status_to_enum(ib_status)

    # UPDATE trades via order_ref — Merge-Flow (Decision C1)
    if new_status == "filled":
        await db_pool.execute("""
            UPDATE trades
            SET order_status = $1,
                entry_price = $2,
                opened_at = NOW(),
                perm_id = $3
            WHERE order_ref = $4
        """,
            new_status,
            trade.orderStatus.avgFillPrice,
            str(trade.orderStatus.permId),
            order_ref,
        )
    else:
        await db_pool.execute(
            "UPDATE trades SET order_status = $1 WHERE order_ref = $2",
            new_status, order_ref,
        )
```

**Auto-Tagging bei Submission (bereits in Story 11.2 implementiert):**

Die `trigger_spec`, `strategy_id` und `horizon` werden **direkt beim INSERT** in Story 11.2 gesetzt. Story 11.3 fuegt nur den Status-Update-Flow hinzu. Kein separater "Create Trade from Quick Order"-Flow — der Trade **ist** die Quick-Order-Row, die bei Submission entsteht.

```python
# In app/services/order_service.py (Task 2 aus Story 11.2 + erweitert in Story 11.3)
async def submit_quick_order(spec: QuickOrderRequest) -> OrderSubmitResult:
    order_ref = f"ctrader-quick-{uuid4().hex[:12]}"

    trigger_spec = {
        "trigger_type": "manual_quick_order",
        "horizon": spec.horizon,
        "entry_reason": "Quick Order platziert aus ctrader",
        "source": "manual",
        "followed": True,
    }

    # INSERT in trades mit vollstaendigen Metadaten (Auto-Tagging)
    trade_id = await db_pool.fetchval("""
        INSERT INTO trades (
            symbol, asset_class, side, quantity,
            limit_price, trailing_stop_amount, trailing_stop_unit,
            order_ref, order_status, submitted_at,
            trigger_spec, strategy_id, horizon, source
        )
        VALUES ($1, 'stock', $2, $3, $4, $5, $6, $7, 'submitted', NOW(), $8, $9, $10, 'ib')
        ON CONFLICT (order_ref) DO NOTHING
        RETURNING id
    """,
        spec.symbol, spec.side, spec.quantity,
        spec.limit_price, spec.trailing_amount, spec.trailing_unit,
        order_ref, trigger_spec, spec.strategy_id, spec.horizon,
    )

    # Bracket-Order an IB senden via clients/ib.py
    await ib_client.place_bracket_order(...)

    return OrderSubmitResult(trade_id=trade_id, order_ref=order_ref, ...)
```

**File Structure:**
```
app/
├── services/
│   └── order_service.py              # UPDATE - orderStatusEvent-Handler + Merge-Logik (Decision A1)
└── templates/
    └── components/
        └── quick_order_form.html     # UPDATE - tagging fields (Strategy, Trigger-Source, Horizon)
```

### References

- PRD: FR56, FR57, FR17
- Architecture: Decision #9 (Merge-Flow via order_ref, kein separates ib_quick_orders-Schema), Decision C1 (erweiterte trades-Tabelle), Decision A1 (order_service)
- UX-Spec: Component `quick_order_form` Tier 2 (Form-Felder inkl. Auto-Tagging)
- Dependency: Story 11.1 (Form), Story 11.2 (INSERT mit trigger_spec), Story 6.1 (strategies-Tabelle fuer Dropdown)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
