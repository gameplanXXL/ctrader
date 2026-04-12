# Story 6.5: Strategy-Status-Enforcement im Bot-Pfad

Status: ready-for-dev

## Story

As a Chef,
I want paused and retired strategies to be blocked from generating new proposals,
so that I can confidently pause underperforming strategies without worrying about rogue bot trades.

## Acceptance Criteria

1. **Given** eine Strategie mit Status "paused" oder "retired", **When** der Bot-Execution-Pfad prueft, **Then** werden keine neuen Proposals fuer diese Strategie generiert (FR39)
2. **Given** eine Strategie wird von "active" auf "paused" gesetzt, **When** bereits ein Pending-Proposal fuer diese Strategie existiert, **Then** bleibt das bestehende Proposal unveraendert (Chef kann es noch manuell ablehnen)

## Tasks / Subtasks

- [ ] Task 1: Strategy-Status-Check-Function
  - [ ] `app/services/strategy.py` — `is_strategy_active(strategy_id) -> bool`
  - [ ] SELECT status FROM strategies WHERE id = $1
  - [ ] Return True nur wenn status = 'active'
- [ ] Task 2: Proposal-Generation-Hook (Placeholder)
  - [ ] Wird in Epic 7 Story 7.1 implementiert — hier nur der Check-Helper
  - [ ] Dokumentieren: "Bevor ein Proposal erstellt wird, MUSS is_strategy_active gechecked werden"
- [ ] Task 3: Kill-Switch-Integration-Check (Cross-Reference Epic 9)
  - [ ] Epic 9 Story 9.2 setzt strategies auf paused via Kill-Switch
  - [ ] Check: Nach Kill-Switch wird kein neues Proposal generiert (Integration-Test)
- [ ] Task 4: Unit-Test
  - [ ] Seed: Strategy status=paused
  - [ ] Mock: Proposal-Generator versucht zu erstellen
  - [ ] Assert: Proposal wird NICHT erstellt, Warning wird geloggt
- [ ] Task 5: Existing-Proposals-Preservation (AC: 2)
  - [ ] Wenn Status-Change → Pending-Proposals bleiben unveraendert
  - [ ] Nur Neu-Generation wird blockiert

## Dev Notes

**Check-Function:**
```python
async def is_strategy_active(db_pool, strategy_id: int) -> bool:
    status = await db_pool.fetchval(
        "SELECT status FROM strategies WHERE id = $1",
        strategy_id
    )
    return status == 'active'
```

**Usage-Pattern (in Epic 7 Story 7.1):**
```python
async def generate_proposal(strategy_id, ...):
    if not await is_strategy_active(db_pool, strategy_id):
        logger.info(
            "proposal_generation_blocked",
            strategy_id=strategy_id,
            reason="strategy_not_active"
        )
        return None
    # ... create proposal ...
```

**Integration-Test mit Kill-Switch (Cross-Reference Epic 9):**
```python
async def test_kill_switch_blocks_proposals():
    # Setup: active strategy, intraday horizon
    strategy = await create_strategy(horizon='intraday')

    # Simulate F&G < 20 → Kill-Switch triggers
    await trigger_kill_switch(f_and_g_index=15)

    # Assert: strategy is now paused
    assert (await get_strategy(strategy.id)).status == 'paused'

    # Try to generate proposal
    proposal = await generate_proposal(strategy.id, ...)

    # Assert: no proposal generated
    assert proposal is None
```

**Kritisches Prinzip (FR39):**
> "Das System verhindert im Bot-Execution-Pfad, dass Strategien mit Status paused oder retired neue Proposals generieren."

Das ist eine **harte Invariante** — keine Ausnahmen. Selbst wenn Bot-Code fehlerhaft ist, muss die Strategy-Active-Check den Gate-Keeper spielen.

**File Structure:**
```
app/
├── services/
│   └── strategy.py              # UPDATE - is_strategy_active helper
└── tests/
    └── integration/
        └── test_strategy_enforcement.py  # NEW
```

### References

- PRD: FR39
- Dependency: Story 6.1 (strategies), Epic 7 Story 7.1 (wird diesen Check nutzen), Epic 9 Story 9.2 (Kill-Switch setzt status)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
