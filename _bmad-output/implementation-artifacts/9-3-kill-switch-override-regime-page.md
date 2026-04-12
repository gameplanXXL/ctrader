# Story 9.3: Kill-Switch-Override & Regime-Seite

Status: ready-for-dev

## Story

As a Chef,
I want to manually override the kill-switch and see current regime status,
so that I can make informed decisions about continuing to trade in volatile markets.

## Acceptance Criteria

1. **Given** eine automatisch pausierte Strategie, **When** Chef den Kill-Switch manuell ueberschreibt, **Then** wird die Strategie re-aktiviert und ein Audit-Log-Eintrag "manual override of kill-switch" erstellt (FR44)
2. **Given** die Regime-Seite (/regime), **When** geladen, **Then** zeigt sie: aktueller F&G-Index, VIX-Level, Liste der durch Kill-Switch pausierten Strategien, Override-Historie (FR45, UX-DR75)
3. **Given** die Regime-Informationen, **When** im Footer des Approval-Viewports angezeigt, **Then** sind F&G, VIX und Kill-Switch-Status sichtbar als Kontext fuer Approval-Entscheidungen (UX-DR75)

## Tasks / Subtasks

- [ ] Task 1: Regime-Page Template
  - [ ] `app/templates/pages/regime.html`
  - [ ] Sections: Current F&G + VIX (Hero-Style), Kill-Switch-Paused Strategies, Override-History
- [ ] Task 2: Regime-Service
  - [ ] `app/services/regime.py` — `get_current_regime()`
  - [ ] Neuester regime_snapshot + paused-strategies + recent-overrides
- [ ] Task 3: Manual-Override-Endpoint (AC: 1)
  - [ ] POST `/strategies/{id}/override-kill-switch`
  - [ ] UPDATE strategies SET status='active', paused_by=NULL (explizit NICHT 'manual' setzen — nur bei manueller Pause)
  - [ ] INSERT audit_log event_type='kill_switch_manual_override'
- [ ] Task 4: Footer-Integration in Approval-Viewport (AC: 3)
  - [ ] Story 7.3 Template um Regime-Footer erweitern
  - [ ] Kompakte Darstellung: "F&G 15 · VIX 28 · Kill-Switch: ACTIVE (3 Strategien pausiert)"
- [ ] Task 5: Override-Historie
  - [ ] Query: audit_log WHERE event_type IN ('kill_switch_pause', 'kill_switch_recover', 'kill_switch_manual_override')
  - [ ] Anzeige: Zeitstempel + Strategy + Action

## Dev Notes

**Regime-Page-Layout:**
```
┌─ MARKET REGIME ──────────────────────────────────┐
│                                                   │
│    FEAR & GREED    VIX        KILL-SWITCH        │
│    ═══════════     ══════     ══════════════     │
│        15           28.4       🔴 ACTIVE         │
│    (Extreme Fear)              3 pausiert        │
│                                                   │
├───────────────────────────────────────────────────┤
│ Paused by Kill-Switch (3)                         │
│  • Mean Reversion Crypto  [Override]              │
│  • Momentum Intraday      [Override]              │
│  • News Breakout          [Override]              │
├───────────────────────────────────────────────────┤
│ Override-History (last 30 days)                   │
│  2026-04-10 14:23  Momentum Intraday  override    │
│  2026-04-05 09:00  News Breakout      auto-pause  │
│  ...                                              │
└───────────────────────────────────────────────────┘
```

**Footer in Approval-Viewport (Story 7.3):**
```
Regime: F&G 15 · VIX 28 · Kill-Switch: ACTIVE (3 paused)
```

**Manual-Override-Flow:**
```python
@router.post("/strategies/{id}/override-kill-switch")
async def override_kill_switch(id: int):
    strategy = await get_strategy(id)
    if strategy.paused_by != 'kill_switch':
        raise HTTPException(400, "Strategy not paused by kill-switch")

    # Re-activate
    await db_pool.execute(
        "UPDATE strategies SET status = 'active', paused_by = NULL WHERE id = $1",
        id
    )

    # Audit-log
    await db_pool.execute("""
        INSERT INTO audit_log (event_type, strategy_id, override_flags, actor, notes)
        VALUES ('kill_switch_manual_override', $1, $2, 'chef', $3)
    """, id, {'automated': False}, "Chef manually overrode kill-switch")

    return {"status": "active"}
```

**Wichtig (FR44):**
> "Das System dokumentiert jeden Override als Audit-Log-Eintrag 'manual override of kill-switch'"

Jeder manuelle Override muss im Audit-Log stehen — vollstaendig reproduzierbar, wer wann was ueberstimmt hat.

**File Structure:**
```
app/
├── services/
│   └── regime.py                   # NEW
├── routers/
│   ├── strategies.py               # UPDATE - override endpoint
│   └── pages.py                    # UPDATE - /regime
└── templates/
    └── pages/
        └── regime.html             # UPDATE
```

### References

- PRD: FR44, FR45
- UX-Spec: UX-DR75 (regime-context-display)
- Dependency: Story 9.1 (snapshots), Story 9.2 (kill-switch), Story 7.5 (audit-log), Story 7.3 (approval-viewport)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
