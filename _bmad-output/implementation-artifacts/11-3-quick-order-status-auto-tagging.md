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
  - [ ] Strategy aus strategies-Tabelle (post Epic 6)
  - [ ] Trigger-Source aus taxonomy
- [ ] Task 2: ib_async Order-Status-Events (AC: 1)
  - [ ] Subscribe auf ib.orderStatusEvent fuer Quick-Orders
  - [ ] Update `ib_quick_orders.status` basierend auf Event
  - [ ] Mapping: Submitted/Filled/PartiallyFilled/Rejected/Cancelled → order_status enum
- [ ] Task 3: Auto-Trade-Creation bei Fill (AC: 2)
  - [ ] Bei FILLED → INSERT in trades-Tabelle
  - [ ] trigger_spec aus Quick-Order-Form-Daten bauen:
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
  - [ ] strategy_id aus Form
- [ ] Task 4: Status-Display im Journal (AC: 1)
  - [ ] Journal zeigt Quick-Orders mit passendem status_badge
  - [ ] Bei "submitted" noch keine Trade-Zeile (nur in ib_quick_orders)
  - [ ] Bei "filled" → normale trade-Zeile + Link zum quick-order
- [ ] Task 5: Partial-Fill Handling
  - [ ] Mehrere Trade-Zeilen moeglich bei mehreren partial fills
  - [ ] Aggregation in der UI

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

**ib_async Status-Event-Listener:**
```python
ib.orderStatusEvent += on_order_status_change

async def on_order_status_change(trade):
    if not trade.order.orderRef.startswith("ctrader-quick-"):
        return  # Not our order

    order_ref = trade.order.orderRef

    # Update ib_quick_orders
    await db_pool.execute(
        "UPDATE ib_quick_orders SET status = $1, updated_at = NOW() WHERE order_ref = $2",
        map_ib_status(trade.orderStatus.status),
        order_ref,
    )

    # If filled → create trade row
    if trade.orderStatus.status == "Filled":
        quick_order = await get_quick_order_by_ref(order_ref)
        await create_trade_from_quick_order(quick_order, trade.orderStatus)
```

**Auto-Trade-Creation:**
```python
async def create_trade_from_quick_order(qo, status):
    trigger_spec = {
        "trigger_type": "manual_quick_order",
        "horizon": qo.horizon,  # from form
        "entry_reason": "Quick Order platziert aus ctrader",
        "source": "manual",
        "followed": True,
    }
    await db_pool.execute("""
        INSERT INTO trades (
            symbol, asset_class, side, quantity, entry_price,
            opened_at, broker, perm_id, trigger_spec, strategy_id
        ) VALUES ($1, 'stock', $2, $3, $4, NOW(), 'ib', $5, $6, $7)
    """,
        qo.symbol, qo.side, qo.quantity, status.avgFillPrice,
        str(status.permId), trigger_spec, qo.strategy_id,
    )
```

**File Structure:**
```
app/
├── services/
│   └── quick_order_sync.py           # NEW - status tracking
└── templates/
    └── fragments/
        └── quick_order_form.html     # UPDATE - tagging fields
```

### References

- PRD: FR56, FR57, FR17
- Dependency: Story 11.1 (Form), Story 11.2 (Order-Placement), Story 6.1 (strategies)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
