# Story 5.2: Fundamental im Trade-Drilldown (Side-by-Side)

Status: ready-for-dev

## Story

As a Chef,
I want to see the fundamental assessment at trade time alongside the current assessment,
so that I can evaluate whether the market thesis has changed since my entry.

## Acceptance Criteria

1. **Given** einen Trade im Drilldown, **When** die Fundamental-Sektion geladen wird, **Then** werden die damalige Einschaetzung (gespeichert zum Trade-Zeitpunkt) und die aktuelle Einschaetzung (live via MCP) side-by-side angezeigt (FR20)
2. **Given** die damalige Einschaetzung existiert nicht (z.B. alter Import), **When** angezeigt, **Then** wird "Keine historische Einschaetzung verfuegbar" in --text-muted angezeigt
3. **Given** die aktuelle Einschaetzung ist nicht verfuegbar (MCP-Outage), **When** angezeigt, **Then** wird "N/A (letzter Stand: HH:MM)" mit Staleness-Banner angezeigt (UX-DR57)

## Tasks / Subtasks

- [ ] Task 1: Migration 006_fundamental_snapshots_table.sql
  - [ ] Tabelle `fundamental_snapshots`: id, trade_id (FK to trades), asset_class, agent_id, snapshot_data JSONB, snapshot_at TIMESTAMPTZ
  - [ ] Index: `idx_fundamental_snapshots_trade_id`
- [ ] Task 2: Fundamental-Snapshot-Capture (AC: 1)
  - [ ] Hook in Story 2.2 Live-Sync: bei neuem Trade → Fundamental abrufen + in snapshots speichern
  - [ ] Hook in Story 2.1 Flex-Import: **NICHT** (historische Trades haben keinen current-time-context)
  - [ ] Hook in Story 8.1 Bot-Execution: bei Order-Placement → Snapshot speichern
- [ ] Task 3: Trade-Drilldown Fundamental-Section (AC: 1, 2, 3)
  - [ ] Template-Erweiterung `fragments/trade_detail.html`
  - [ ] 2 Spalten: "Damals" | "Jetzt"
  - [ ] Damals: aus fundamental_snapshots (if exists)
  - [ ] Jetzt: via Story 5.1 get_fundamental live
- [ ] Task 4: Empty-State fuer Alt-Trades (AC: 2)
  - [ ] "Keine historische Einschaetzung verfuegbar" wenn snapshot fehlt
  - [ ] Begruendung anzeigen: "Dieser Trade wurde vor der Fundamental-Integration importiert"
- [ ] Task 5: Staleness-Integration (AC: 3)
  - [ ] Bei is_stale=True: staleness_banner Component (Story 5.3)

## Dev Notes

**fundamental_snapshots Schema:**
```sql
CREATE TABLE fundamental_snapshots (
    id SERIAL PRIMARY KEY,
    trade_id INT NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    asset_class TEXT NOT NULL,
    agent_id TEXT NOT NULL,  -- 'viktor' or 'satoshi'
    snapshot_data JSONB NOT NULL,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fundamental_snapshots_trade_id ON fundamental_snapshots(trade_id);
```

**Side-by-Side Layout:**
```
┌─ FUNDAMENTAL ─────────────────────────────┐
│  DAMALS (Entry)     │     JETZT (Live)    │
│  ────────────       │     ─────────────    │
│  Rating: BUY        │     Rating: HOLD     │
│  Confidence: 78%    │     Confidence: 62%  │
│  Thesis: Growth...  │     Thesis: Mixed... │
│  Stand: 2026-04-10  │     Stand: vor 12min │
└───────────────────────────────────────────┘
```

**Diff-Indicator (optional):**
Wenn Rating zwischen "Damals" und "Jetzt" abweicht, visueller Hinweis (z.B. Pfeil).

**Capture-Hook-Pattern:**
```python
# In app/services/ib_live_sync.py on_execution():
async def on_execution(execution):
    trade = await insert_trade(execution)
    # Fire-and-forget fundamental snapshot
    asyncio.create_task(
        capture_fundamental_snapshot(trade.id, trade.symbol, trade.asset_class)
    )

async def capture_fundamental_snapshot(trade_id, symbol, asset_class):
    try:
        result = await get_fundamental(symbol, asset_class, mcp_client)
        await db_pool.execute("""
            INSERT INTO fundamental_snapshots (trade_id, asset_class, agent_id, snapshot_data)
            VALUES ($1, $2, $3, $4)
        """, trade_id, asset_class, agent_id_from(asset_class), result.data)
    except Exception as e:
        logger.warning("fundamental_snapshot_failed", trade_id=trade_id, error=str(e))
```

**File Structure:**
```
migrations/
└── 006_fundamental_snapshots_table.sql   # NEW
app/
├── services/
│   ├── fundamental_snapshot.py           # NEW - capture logic
│   └── ib_live_sync.py                   # UPDATE - fire hook
└── templates/
    └── fragments/
        └── trade_detail.html             # UPDATE - side-by-side section
```

### References

- PRD: FR20
- UX-Spec: UX-DR57 (Graceful Degradation)
- Dependency: Story 5.1 (Fundamental-Service), Story 2.2 (Live-Sync Hook), Story 2.4 (Drilldown)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
