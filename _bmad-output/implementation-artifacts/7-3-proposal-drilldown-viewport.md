# Story 7.3: Proposal-Drilldown & Single-Viewport-Entscheidung

Status: ready-for-dev

## Story

As a Chef,
I want all decision-relevant information in one viewport without scrolling,
so that I can make fast, informed approval decisions.

## Acceptance Criteria

1. **Given** ein Proposal im Dashboard, **When** geklickt, **Then** expandiert der proposal_viewport als Inline-Expansion mit 3-Spalten-Layout (~440px): Agent-Vorschlag | Fundamental-Einschaetzung | Risk-Gate-Status (FR26, UX-DR22, UX-DR27)
2. **Given** den Proposal-Viewport, **When** bei 1440px x ~850px angezeigt, **Then** sind alle entscheidungsrelevanten Infos sichtbar ohne Scroll: Agent-Proposal, Fundamental (aktuell via MCP, FR21), Risk-Gate, Regime-Kontext (Footer), Action-Buttons (Footer) (UX-DR67, UX-DR99)
3. **Given** die Fundamental-Einschaetzung im Proposal, **When** nicht verfuegbar (MCP-Outage), **Then** zeigt die mittlere Spalte den Staleness-State statt einen Fehler (UX-DR22)
4. **Given** den Proposal-Viewport, **When** das Risk-Gate RED ist, **Then** ist der Approve-Button grau/disabled und der "Decision Point" visuell dominant (UX-DR99)

## Tasks / Subtasks

- [ ] Task 1: proposal_viewport Macro (AC: 1, 2)
  - [ ] `app/templates/components/proposal_viewport.html` (ersetzt Stub)
  - [ ] 3 Columns ~440px jeweils
  - [ ] Agent | Fundamental | Risk-Gate
- [ ] Task 2: Fundamental-Fetch fuer Proposal (AC: 3, FR21)
  - [ ] Nutzt Story 5.1 `get_fundamental` fuer aktuelle Einschaetzung
  - [ ] Graceful Degradation bei Outage
- [ ] Task 3: Regime-Kontext im Footer
  - [ ] F&G + VIX + Kill-Switch-Status aus Story 9.1
  - [ ] Placeholder wenn Epic 9 noch nicht implementiert
- [ ] Task 4: Inline-Expansion-Route
  - [ ] GET `/proposals/{id}/drilldown` → HTMX fragment
  - [ ] HX-Target: below-clicked-card
- [ ] Task 5: Focus-Center "Decision Point" (AC: 4)
  - [ ] Action-Buttons-Row visuell dominant
  - [ ] CSS: border top, padding, klarer visueller Focus
- [ ] Task 6: Keyboard-Shortcuts
  - [ ] `A` key → Approve (Story 7.4)
  - [ ] `R` key → Reject (Story 7.4)
  - [ ] Nur aktiv wenn proposal_viewport offen

## Dev Notes

**Layout (aus UX-DR22, UX-DR67):**
```
┌─ Proposal #42 — Satoshi / BTCUSD Long ─────────────────────────────┐
│                                                                     │
│ ┌─ AGENT ──────┐ ┌─ FUNDAMENTAL ──┐ ┌─ RISK GATE ──────────────┐   │
│ │ Satoshi      │ │ Rating: BUY    │ │ ● GREEN                  │   │
│ │ Conf: 72%    │ │ Conf: 78%      │ │ Flags: none              │   │
│ │ Horizon: SW  │ │ Thesis: ...    │ │ Details: ...             │   │
│ │ Entry: 68100 │ │ Stand: vor 5m  │ │ Budget-Check: OK         │   │
│ │ Stop: 66500  │ │                │ │ Correlation: OK          │   │
│ │ Target:70200 │ │                │ │ Regime: OK               │   │
│ │ Size: $5000  │ │                │ │                          │   │
│ │ R-Budget:200 │ │                │ │                          │   │
│ └──────────────┘ └────────────────┘ └──────────────────────────┘   │
│                                                                     │
│ Regime: F&G 55 · VIX 18 · Kill-Switch: OFF                          │
│                                                                     │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │  [Approve A]  [Reject R]  [Revise]          Override Fund: []  │ │
│ └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**Single-Viewport-Constraint:**
- Target: 1440px x 850px
- Alles sichtbar ohne Scroll
- 3 Columns mit jeweils ~440px = 1320px + margins = 1400px
- Tight aber machbar

**Fundamental-Loading:**
```python
# In route handler
async def get_proposal_drilldown(proposal_id: int):
    proposal = await get_proposal(proposal_id)
    try:
        fundamental = await get_fundamental(
            proposal.symbol,
            proposal.asset_class,
            mcp_client,
        )
    except:
        fundamental = None  # Template handles None

    regime = await get_current_regime()  # Epic 9

    return templates.TemplateResponse(
        "fragments/proposal_drilldown.html",
        {
            "proposal": proposal,
            "fundamental": fundamental,
            "regime": regime,
        }
    )
```

**File Structure:**
```
app/
├── routers/
│   └── approvals.py              # UPDATE - /proposals/{id}/drilldown
└── templates/
    ├── components/
    │   └── proposal_viewport.html  # UPDATE
    └── fragments/
        └── proposal_drilldown.html # NEW
```

### References

- PRD: FR21 (current fundamental im proposal), FR26 (single viewport)
- UX-Spec: UX-DR22 (proposal_viewport), UX-DR27 (Layout), UX-DR67 (Single Viewport), UX-DR99 (Focus-Center)
- Dependency: Story 5.1 (Fundamental), Story 7.1 (proposals), Story 7.2 (Risk-Gate)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
