# Story 7.5: Unveraenderlicher Audit-Log

Status: ready-for-dev

## Story

As a Chef,
I want an immutable audit trail for every approval decision,
so that I can always reconstruct why a trade was approved and under what conditions.

## Acceptance Criteria

1. **Given** ein Proposal wird genehmigt oder abgelehnt, **When** die Entscheidung gespeichert wird, **Then** wird ein Audit-Log-Eintrag erstellt mit: Zeitstempel, genehmigtes Risikobudget, Risk-Gate-Snapshot (volle Response), Override-Flags, Strategie-Version, Fundamental-Einschaetzung (FR32, NFR-R8)
2. **Given** die audit_log-Tabelle, **When** ein UPDATE oder DELETE versucht wird, **Then** wird die Operation via PostgreSQL `BEFORE UPDATE OR DELETE` Trigger mit `RAISE EXCEPTION 'audit log is append-only'` verhindert (NFR-S3)
3. **Given** den Audit-Log, **When** inspiziert, **Then** ist jede historische Approval-Entscheidung allein aus dem Log reproduzierbar (NFR-R8)

## Tasks / Subtasks

- [ ] Task 1: Migration 011_audit_log_trigger.sql (AC: 2)
  - [ ] CREATE OR REPLACE FUNCTION audit_log_append_only()
  - [ ] RAISE EXCEPTION 'audit log is append-only'
  - [ ] CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()
- [ ] Task 2: Audit-Service (AC: 1)
  - [ ] `app/services/audit.py` — `log_proposal_decision(event_type, proposal, risk_budget, override_flags, notes)`
  - [ ] Captures: proposal + risk-gate-snapshot + fundamental-snapshot + strategy-version
  - [ ] INSERT audit_log
- [ ] Task 3: Integration in Story 7.4 Endpoints (AC: 1)
  - [ ] Approve: log_proposal_decision('proposal_approved', ...)
  - [ ] Reject: log_proposal_decision('proposal_rejected', ...)
  - [ ] Revision: log_proposal_decision('proposal_revision', ...)
- [ ] Task 4: Append-Only-Test (AC: 2)
  - [ ] Integration-Test:
    ```python
    async def test_audit_log_append_only():
        await db.execute("INSERT INTO audit_log ...")
        with pytest.raises(PostgresError, match='audit log is append-only'):
            await db.execute("UPDATE audit_log SET ...")
        with pytest.raises(PostgresError, match='audit log is append-only'):
            await db.execute("DELETE FROM audit_log ...")
    ```
- [ ] Task 5: Audit-Log-View (fuer Story 12.2 Settings)
  - [ ] Read-only Ansicht aller Eintraege chronologisch
  - [ ] Filter by event_type
  - [ ] Kein Edit/Delete UI

## Dev Notes

**PostgreSQL Trigger (Architecture-Spec):**
```sql
CREATE OR REPLACE FUNCTION audit_log_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update_delete
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
```

**Snapshot-Capture-Logic:**
```python
async def log_proposal_decision(
    db_pool,
    event_type: str,
    proposal: Proposal,
    risk_budget: float,
    override_flags: dict,
    notes: str | None = None,
):
    # Fetch strategy version at decision time
    strategy_snapshot = await db_pool.fetchrow(
        "SELECT * FROM strategies WHERE id = $1",
        proposal.strategy_id
    )

    await db_pool.execute("""
        INSERT INTO audit_log (
            event_type, proposal_id, strategy_id,
            risk_budget, risk_gate_snapshot, fundamental_snapshot,
            override_flags, strategy_version, actor, notes
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'chef', $9)
    """,
        event_type,
        proposal.id,
        proposal.strategy_id,
        risk_budget,
        proposal.risk_gate_response,  # full snapshot
        await fetch_fundamental_snapshot_for_proposal(proposal),
        override_flags,
        strategy_snapshot,  # snapshot as JSONB
        notes,
    )
```

**Reproduktions-Kriterium (NFR-R8):**
Aus dem Audit-Log allein muss sich rekonstruieren lassen:
- Welcher Agent hat empfohlen?
- Welche Strategie war aktiv (inkl. deren Version)?
- Welches Risk-Gate-Ergebnis lag vor?
- Welche Fundamental-Einschaetzung existierte zum Entscheidungs-Zeitpunkt?
- Hat Chef den Fundamental-Agent ueberstimmt?
- Wie hoch war das genehmigte Risikobudget?

**Wichtig:** Auch wenn sich Strategien spaeter aendern, das Audit-Log haelt den **Snapshot zum Zeitpunkt der Entscheidung**. strategy_version ist das komplette strategies-Row-Dict als JSONB.

**File Structure:**
```
migrations/
└── 011_audit_log_trigger.sql     # NEW
app/
├── services/
│   └── audit.py                  # NEW
└── tests/
    └── integration/
        └── test_audit_log.py     # NEW
```

### References

- PRD: FR32, NFR-R8, NFR-S3
- Architecture: "Audit Logging" — Append-Only Constraint via PG Trigger
- Dependency: Story 7.1 (audit_log Tabelle angelegt), Story 7.4 (integriert audit-logging)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
