# Story 7.1: Proposal-Datenmodell & Approval-Dashboard

Status: ready-for-dev

## Story

As a Chef,
I want to see all pending bot proposals in a dashboard,
so that I can efficiently review and act on AI trading recommendations.

## Acceptance Criteria

1. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** werden `proposals`-Tabelle (id, agent_id, strategy_id, symbol, asset_class, side, horizon, entry_price, stop_price, target_price, position_size, risk_budget, trigger_spec JSONB, risk_gate_result, risk_gate_response JSONB, status, created_at, decided_at) und `audit_log`-Tabelle erstellt
2. **Given** die Approvals-Seite, **When** geladen, **Then** zeigt sie alle offenen Bot-Proposals als Cards mit: Agent-Name, Strategie, Asset, Horizon, vorgeschlagene Position, Risk-Gate-Status-Badge (FR25)
3. **Given** das Approval-Dashboard, **When** geladen, **Then** erscheint es innerhalb von 2 Sekunden inklusive MCP-Calls bei Cache-Miss (NFR-P5)

## Tasks / Subtasks

- [ ] Task 1: Migration 010_proposals_and_audit_log.sql (AC: 1)
  - [ ] CREATE TABLE proposals (siehe Schema unten)
  - [ ] CREATE TABLE audit_log (append-only, siehe Story 7.5)
  - [ ] Indices: proposals_status_idx, proposals_strategy_idx
- [ ] Task 2: Pydantic-Models
  - [ ] `app/models/proposal.py` mit Proposal, ProposalCreate, ProposalDecision
- [ ] Task 3: Proposal-Service
  - [ ] `app/services/proposal.py`
  - [ ] `list_pending_proposals()`, `get_proposal(id)`, `create_proposal(...)`, `decide_proposal(id, decision, ...)`
- [ ] Task 4: Approval-Dashboard-Page (AC: 2)
  - [ ] `app/templates/pages/approvals.html`
  - [ ] Card-Layout mit allen Pflichtfeldern
- [ ] Task 5: Performance (AC: 3)
  - [ ] Prefetch strategies, MCP-Cache warm
  - [ ] Load-Test mit N=10 Proposals
- [ ] Task 6: Proposal-Generator Integration (Placeholder)
  - [ ] Interface fuer Bot-Agents zur Proposal-Creation
  - [ ] Nutzt `is_strategy_active` aus Story 6.5
- [ ] Task 7: audit_log-Tabelle (hier NUR anlegen, Trigger kommt in Story 7.5)

## Dev Notes

**proposals Schema:**
```sql
CREATE TABLE proposals (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    strategy_id INT REFERENCES strategies(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    side trade_side NOT NULL,
    horizon horizon_type NOT NULL,
    entry_price NUMERIC NOT NULL,
    stop_price NUMERIC,
    target_price NUMERIC,
    position_size NUMERIC NOT NULL,
    risk_budget NUMERIC NOT NULL,
    trigger_spec JSONB NOT NULL,
    risk_gate_result risk_gate_result,  -- green/yellow/red
    risk_gate_response JSONB,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/revision
    created_at TIMESTAMPTZ DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    decided_by TEXT  -- 'chef' (single-user)
);

CREATE INDEX idx_proposals_status ON proposals(status, created_at DESC);
CREATE INDEX idx_proposals_strategy ON proposals(strategy_id);
```

**audit_log Schema (Grundgeruest, Trigger in Story 7.5):**
```sql
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,  -- 'proposal_approved', 'proposal_rejected', 'kill_switch_override', etc.
    proposal_id INT REFERENCES proposals(id),
    strategy_id INT REFERENCES strategies(id),
    risk_budget NUMERIC,
    risk_gate_snapshot JSONB,
    fundamental_snapshot JSONB,
    override_flags JSONB,
    strategy_version INT,  -- snapshot version
    actor TEXT NOT NULL DEFAULT 'chef',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);
```

**Dashboard-Card-Layout:**
```
┌─ Proposal #42 ─────────────────────────────┐
│ Satoshi | Mean Reversion Crypto            │
│ BTCUSD · Long · Swing · $5000 @ 68100     │
│ Stop: 66500  Target: 70200  R-Budget: $200│
│ [● GREEN Risk-Gate]                        │
│ [Review in Detail]                         │
└────────────────────────────────────────────┘
```

**File Structure:**
```
migrations/
└── 010_proposals_and_audit_log.sql   # NEW
app/
├── models/
│   └── proposal.py                    # NEW
├── services/
│   └── proposal.py                    # NEW
├── routers/
│   └── approvals.py                   # NEW
└── templates/
    └── pages/
        └── approvals.html             # UPDATE
```

### References

- PRD: FR25, NFR-P5
- Architecture: "Audit Logging", "Database Schemas"
- Dependency: Story 6.1 (strategies), Story 6.5 (status enforcement)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
