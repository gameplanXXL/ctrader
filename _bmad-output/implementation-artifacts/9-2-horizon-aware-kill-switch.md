# Story 9.2: Horizon-bewusster Kill-Switch

Status: ready-for-dev

## Story

As a Chef,
I want automatic strategy pausing in crash regimes based on horizon,
so that short-term strategies are protected while long-term positions ride through volatility.

## Acceptance Criteria

1. **Given** Fear & Greed Index < 20, **When** der Kill-Switch evaluiert, **Then** werden alle Strategien mit Horizon in {intraday, swing<5d} automatisch auf "paused" gesetzt (FR42)
2. **Given** Fear & Greed Index < 20, **When** der Kill-Switch evaluiert, **Then** werden Strategien mit Horizon {swing>=5d, position} NICHT automatisch pausiert (FR43)
3. **Given** Fear & Greed Index >= 20 (wieder normal), **When** der Kill-Switch re-evaluiert, **Then** werden zuvor automatisch pausierte Strategien wieder auf "active" gesetzt

## Tasks / Subtasks

- [ ] Task 1: Migration 016_kill_switch_state.sql
  - [ ] Neue Column auf strategies: `paused_by TEXT` ('manual' | 'kill_switch' | NULL)
  - [ ] Tracking: Wer hat pausiert (damit Kill-Switch nur seine eigenen Pausen aufhebt)
- [ ] Task 2: Kill-Switch-Service
  - [ ] `app/services/kill_switch.py` — `evaluate_kill_switch(db_pool, fear_greed_index)`
  - [ ] Short-Horizon-Definition: intraday oder swing_short (< 5 Tage)
  - [ ] Long-Horizon-Definition: swing_long oder position
  - [ ] UPDATE strategies SET status='paused', paused_by='kill_switch' WHERE ...
- [ ] Task 3: Re-Evaluation bei Recovery
  - [ ] Wenn F&G >= 20: UPDATE strategies SET status='active' WHERE paused_by='kill_switch'
  - [ ] paused_by NULL setzen
- [ ] Task 4: Trigger nach Regime-Snapshot (Story 9.1)
  - [ ] Nach jedem regime_snapshot-Job → evaluate_kill_switch
  - [ ] Audit-Log-Eintrag bei State-Wechsel
- [ ] Task 5: Tests
  - [ ] Seed: active intraday strategy + active position strategy
  - [ ] F&G 15 → intraday paused, position bleibt active
  - [ ] F&G 30 → intraday wieder active
  - [ ] Manual paused Strategy bleibt paused bei Recovery (paused_by='manual')

## Dev Notes

**Kill-Switch-SQL:**
```sql
-- Pause short-horizon strategies
UPDATE strategies
SET status = 'paused', paused_by = 'kill_switch'
WHERE status = 'active'
  AND horizon IN ('intraday', 'swing_short')
  AND $1 < 20;  -- F&G threshold

-- Recover strategies pauseed by kill-switch (not manually)
UPDATE strategies
SET status = 'active', paused_by = NULL
WHERE status = 'paused'
  AND paused_by = 'kill_switch'
  AND $1 >= 20;
```

**Horizon-Definition:**
- `intraday` → pause
- `swing_short` (< 5 Tage) → pause
- `swing_long` (>= 5 Tage) → **KEIN pause**
- `position` → **KEIN pause**

Die Taxonomie aus Story 1.3 sollte zwischen `swing_short` und `swing_long` unterscheiden. Wenn taxonomy.yaml nur `swing` hat, muss diese Story sie differenzieren.

**Audit-Log bei Kill-Switch:**
```python
async def log_kill_switch_action(action: str, strategy_id: int, f_and_g: int):
    await db_pool.execute("""
        INSERT INTO audit_log (event_type, strategy_id, override_flags, notes)
        VALUES ($1, $2, $3, $4)
    """,
        'kill_switch_pause' if action == 'pause' else 'kill_switch_recover',
        strategy_id,
        {'fear_greed_index': f_and_g, 'automated': True},
        f"Kill-switch triggered: F&G = {f_and_g}"
    )
```

**Trigger-Integration (Story 9.1 Job):**
```python
async def regime_snapshot_job(db_pool):
    # ... create snapshot ...
    fg = snapshot['fear_greed_index']
    await evaluate_kill_switch(db_pool, fg)
```

**File Structure:**
```
migrations/
└── 016_kill_switch_state.sql     # NEW
app/
├── services/
│   └── kill_switch.py             # NEW
└── jobs/
    └── regime_snapshot.py         # UPDATE - call evaluate after snapshot
```

### References

- PRD: FR42, FR43
- Dependency: Story 9.1 (regime_snapshots), Story 6.1 (strategies + status), Story 7.5 (audit_log)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
