# Story 7.2: Risk-Gate-Integration (Rita & Cassandra)

Status: ready-for-dev

## Story

As a Chef,
I want every bot proposal to be automatically risk-assessed,
so that I'm protected from approving dangerously risky trades.

## Acceptance Criteria

1. **Given** ein neues Proposal wird erstellt, **When** es in die Pipeline eintritt, **Then** fuehrt das System automatisch ein Risk-Gate via Rita (Aktien) oder Cassandra (Crypto) per MCP aus mit dreistufigem Ergebnis: GREEN, YELLOW, RED (FR27)
2. **Given** ein Risk-Gate-Ergebnis RED, **When** das Proposal im Dashboard angezeigt wird, **Then** ist der Approve-Button technisch blockiert (disabled, `cursor: not-allowed`) — es gibt keinen Workaround (FR28, UX-DR56)
3. **Given** ein Risk-Gate-Ergebnis YELLOW, **When** das Proposal angezeigt wird, **Then** wird eine Warnung angezeigt aber der Approve-Button bleibt klickbar (UX-DR56)
4. **Given** die Risk-Gate-Response, **When** gespeichert, **Then** wird die volle Response als JSONB im Proposal gespeichert fuer den Audit-Log

## Tasks / Subtasks

- [ ] Task 1: Risk-Gate-Service (AC: 1, 4)
  - [ ] `app/services/risk_gate.py` — `run_risk_gate(proposal) -> RiskGateResult`
  - [ ] Routing: asset_class='stock' → rita, 'crypto' → cassandra
  - [ ] MCP-Call mit Proposal-Details
  - [ ] Timeout: 10s (NFR-I1)
- [ ] Task 2: RiskGateResult-Model
  - [ ] `app/models/risk_gate.py` mit `level: Literal["green", "yellow", "red"]`, `flags: list[str]`, `details: dict`
- [ ] Task 3: Proposal-Pipeline-Integration (AC: 1)
  - [ ] Bei Proposal-Creation: Async Risk-Gate ausfuehren
  - [ ] UPDATE proposals SET risk_gate_result, risk_gate_response
- [ ] Task 4: Disabled-Approve-Button-Logic (AC: 2, 3)
  - [ ] Template: wenn risk_gate_result='red' → disabled + cursor-not-allowed
  - [ ] YELLOW → Warning icon + clickable
  - [ ] GREEN → normal clickable
- [ ] Task 5: Fallback bei MCP-Outage (NFR-R6)
  - [ ] Wenn Risk-Gate nicht erreichbar → State "unreachable"
  - [ ] Approval-Flow blockiert explizit mit "Risk-Gate unreachable" (FR23 Section fuer Action-Views)
- [ ] Task 6: Tests
  - [ ] Mock Rita/Cassandra MCP-Responses (green/yellow/red)
  - [ ] Assert: Button state per level
  - [ ] Mock: MCP timeout → blockierter State

## Dev Notes

**Risk-Gate-Service:**
```python
class RiskGateResult(BaseModel):
    level: Literal["green", "yellow", "red", "unreachable"]
    flags: list[str]  # z.B. ["position_oversized", "correlation_high"]
    details: dict  # full MCP response
    evaluated_at: datetime

async def run_risk_gate(
    proposal: Proposal,
    mcp_client: MCPClient,
) -> RiskGateResult:
    agent = "rita" if proposal.asset_class == "stock" else "cassandra"
    try:
        response = await mcp_client.call(
            tool="risk_gate",
            agent=agent,
            symbol=proposal.symbol,
            side=proposal.side,
            position_size=proposal.position_size,
            risk_budget=proposal.risk_budget,
        )
        return RiskGateResult(
            level=response['level'],
            flags=response.get('flags', []),
            details=response,
            evaluated_at=datetime.utcnow(),
        )
    except (asyncio.TimeoutError, ConnectionError):
        logger.error("risk_gate_unreachable", proposal_id=proposal.id)
        return RiskGateResult(
            level="unreachable",
            flags=["mcp_unreachable"],
            details={},
            evaluated_at=datetime.utcnow(),
        )
```

**Button-State-Logic (Template):**
```jinja2
{% macro approve_button(proposal) %}
  {% if proposal.risk_gate_result == 'red' or proposal.risk_gate_result == 'unreachable' %}
    <button disabled class="cursor-not-allowed opacity-40"
            aria-describedby="risk-gate-block-reason">
      Approve [A]
    </button>
    <p id="risk-gate-block-reason" class="text-[var(--color-red)]">
      {% if proposal.risk_gate_result == 'red' %}
        Risk-Gate blockiert: {{ proposal.risk_gate_response.flags | join(', ') }}
      {% else %}
        Risk-Gate unreachable — Approval gesperrt
      {% endif %}
    </p>
  {% else %}
    <button class="btn-primary" hx-post="/proposals/{{ proposal.id }}/approve">
      Approve [A]
    </button>
  {% endif %}
{% endmacro %}
```

**Hart-Invariante (FR28):**
> "Das System blockiert den Approval-Button technisch, wenn das Risk-Gate RED liefert. Es gibt keinen Workaround zur Umgehung der RED-Blockade."

Backend MUSS die RED-Blockade durchsetzen (nicht nur Frontend). POST `/proposals/{id}/approve` muss:
```python
if proposal.risk_gate_result == 'red':
    raise HTTPException(status_code=403, detail="Risk-Gate RED — Approval not allowed")
```

**File Structure:**
```
app/
├── services/
│   └── risk_gate.py            # NEW
├── models/
│   └── risk_gate.py            # NEW
└── templates/
    └── components/
        └── approve_button.html # NEW (macro)
```

### References

- PRD: FR27, FR28, NFR-R6
- UX-Spec: UX-DR56 (Risk-Gate Status-Display)
- Dependency: Story 1.6 (MCP-Client), Story 7.1 (proposals table)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
