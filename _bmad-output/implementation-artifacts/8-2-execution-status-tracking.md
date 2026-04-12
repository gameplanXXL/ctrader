# Story 8.2: Execution-Status-Tracking & Journal-Verknuepfung

Status: ready-for-dev

## Story

As a Chef,
I want to see the execution status of every bot trade,
so that I know whether approved trades were successfully placed and filled.

## Acceptance Criteria

1. **Given** eine platzierte Bot-Order, **When** der Status sich aendert, **Then** wird der Execution-Status aktualisiert: submitted / filled / partial / rejected / cancelled (FR7)
2. **Given** eine ausgefuehrte (filled) Bot-Order, **When** der Trade in die trades-Tabelle geschrieben wird, **Then** wird die trigger_spec automatisch aus dem genehmigten Proposal befuellt (FR17)
3. **Given** einen Bot-Trade im Journal, **When** der Status-Indikator angezeigt wird, **Then** reflektiert er den aktuellen Execution-Status mit passendem status_badge (UX-DR77)

## Tasks / Subtasks

- [ ] Task 1: cTrader Status-Event-Listener (AC: 1)
  - [ ] Subscribe auf Order-Update-Events (ProtoOAExecutionEvent)
  - [ ] Mapping cTrader-Status → order_status enum
  - [ ] UPDATE proposals SET execution_status
- [ ] Task 2: Trade-Creation bei Filled (AC: 2)
  - [ ] Bei FILLED-Event → INSERT in trades-Tabelle
  - [ ] trigger_spec wird aus proposal.trigger_spec kopiert (FR17)
  - [ ] strategy_id, agent_id gesetzt
  - [ ] broker='ctrader', perm_id=cTrader order-id
- [ ] Task 3: Journal-Integration (AC: 3)
  - [ ] trade_row zeigt status_badge (aus Story 6.1)
  - [ ] Filter-Option: "nur Bot-Trades"
- [ ] Task 4: Partial-Fill-Handling (AC: 1)
  - [ ] Bei PARTIAL → Trade mit reduzierter quantity erstellen
  - [ ] Weitere Fills → update existing trade
- [ ] Task 5: Tests
  - [ ] Mock-Event-Stream
  - [ ] Assert: proposals.execution_status updated
  - [ ] Assert: trades row erstellt bei FILLED
  - [ ] Assert: trigger_spec korrekt kopiert

## Dev Notes

**cTrader Status → order_status Mapping:**
```python
CTRADER_STATUS_MAPPING = {
    "ORDER_STATUS_ACCEPTED": "submitted",
    "ORDER_STATUS_FILLED": "filled",
    "ORDER_STATUS_PARTIALLY_FILLED": "partial",
    "ORDER_STATUS_REJECTED": "rejected",
    "ORDER_STATUS_CANCELLED": "cancelled",
}
```

**Trade-Creation-Logic:**
```python
async def on_execution_event(event):
    proposal = await get_proposal_by_client_order_id(event.clientOrderId)
    if not proposal:
        logger.warning("unknown_client_order_id", id=event.clientOrderId)
        return

    new_status = CTRADER_STATUS_MAPPING.get(event.orderStatus)

    # Update proposals
    await db_pool.execute(
        "UPDATE proposals SET execution_status = $1, execution_updated_at = NOW() WHERE id = $2",
        new_status, proposal.id
    )

    # If filled → create trade
    if new_status == "filled":
        await db_pool.execute("""
            INSERT INTO trades (
                symbol, asset_class, side, quantity, entry_price,
                opened_at, broker, perm_id, trigger_spec, strategy_id, agent_id
            ) VALUES ($1, $2, $3, $4, $5, $6, 'ctrader', $7, $8, $9, $10)
        """,
            proposal.symbol,
            proposal.asset_class,
            proposal.side,
            event.filled_volume,
            event.filled_price,
            event.execution_time,
            event.order_id,
            proposal.trigger_spec,  # FR17 — auto-fill
            proposal.strategy_id,
            proposal.agent_id,
        )
```

**Story 7.1 needs update:**
- `proposals` table braucht weitere Columns: `execution_status order_status`, `execution_updated_at TIMESTAMPTZ`, `execution_details JSONB`
- → Migration 014_proposals_execution_fields.sql in dieser Story

**File Structure:**
```
migrations/
└── 014_proposals_execution_fields.sql   # NEW
app/
└── services/
    └── bot_execution.py                 # UPDATE - event handler
```

### References

- PRD: FR7, FR17
- UX-Spec: UX-DR77 (Trade-Status-Indikatoren)
- Dependency: Story 8.1 (cTrader-Client + Order-Execution), Story 7.1 (proposals), Story 3.2 (trigger_spec)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
