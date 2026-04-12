# Story 8.1: cTrader-Client & Idempotente Order-Execution

Status: ready-for-dev

## Story

As a Chef,
I want approved proposals to be executed on the cTrader demo account,
so that AI-recommended trades are placed automatically after my approval.

## Acceptance Criteria

1. **Given** ein genehmigtes Proposal, **When** die Execution getriggert wird, **Then** verbindet sich das System via OpenApiPy (Protobuf/SSL) mit dem cTrader-Demo-Account und platziert die Order (FR6)
2. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die trades-Tabelle per `ALTER TABLE trades ADD COLUMN agent_id TEXT` erweitert inklusive `idx_trades_agent_id` Index (schliesst Issue M1 der Readiness-Review; agent_id ist TEXT als Multi-Agent-Konzession aus dem MVP-Scope)
3. **Given** ein genehmigtes Proposal, **When** die Order gesendet wird, **Then** wird eine Client-Order-ID als Idempotenz-Schluessel verwendet; ein Retry nach Netzausfall erzeugt keine Doppel-Order (FR6, NFR-R3)
4. **Given** ein Netzwerkfehler bei der Order-Platzierung, **When** ein Retry ausgefuehrt wird, **Then** nutzt das System Exponential Backoff (1s Start, 60s Max, max 5 Retries) (NFR-I3)
5. **Given** die cTrader-API Rate-Limits, **When** ein 429-Fehler auftritt, **Then** wartet das System den Backoff ab und versucht erneut

## Tasks / Subtasks

- [ ] Task 1: Migration 012_agent_id_column.sql (AC: 2)
  - [ ] ALTER TABLE trades ADD COLUMN agent_id TEXT
  - [ ] CREATE INDEX idx_trades_agent_id
- [ ] Task 2: cTrader-Client (AC: 1)
  - [ ] `app/clients/ctrader.py` mit `CTraderClient`
  - [ ] OpenApiPy Protobuf/SSL
  - [ ] OAuth2 Authentication
  - [ ] Environment: `CTRADER_CLIENT_ID`, `CTRADER_SECRET`, `CTRADER_ACCOUNT_ID`
- [ ] Task 3: Order-Execution-Service (AC: 1, 3)
  - [ ] `app/services/bot_execution.py` — `execute_proposal(proposal)`
  - [ ] Client-Order-ID generieren: `f"proposal-{proposal.id}-{uuid4().hex[:8]}"`
  - [ ] Order-Params aus Proposal: symbol, side, quantity, entry, stop, target
- [ ] Task 4: Idempotenz via Client-Order-ID (AC: 3)
  - [ ] Speichere Client-Order-ID in proposals-Tabelle (neue Column `client_order_id TEXT UNIQUE`)
  - [ ] Migration 013_proposal_client_order_id.sql
  - [ ] Bei Retry: check ob Order mit ID existiert → skip
- [ ] Task 5: Exponential Backoff (AC: 4, 5)
  - [ ] `tenacity` oder eigenes Retry-Decorator
  - [ ] Delays: 1, 2, 4, 8, 16, 32, 60 (cap)
  - [ ] Max 5 Retries
- [ ] Task 6: Trigger von Approve-Flow (Story 7.4)
  - [ ] Bei Approve → `asyncio.create_task(execute_proposal(proposal))`
  - [ ] Fire-and-forget, aber mit structlog tracking
- [ ] Task 7: Tests mit Mock-cTrader
  - [ ] Test: Successful execution
  - [ ] Test: Rate limit → backoff → retry → success
  - [ ] Test: Double-execute → idempotent (no duplicate)

## Dev Notes

**OpenApiPy-Pattern:**
```python
from openapipy import OpenApi

class CTraderClient:
    def __init__(self, host, port, client_id, secret, account_id):
        self.client = OpenApi(host, port)
        # OAuth2 flow to get access_token
        self.access_token = await self._oauth()
        self.account_id = account_id

    async def place_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        order_type: str = "LIMIT",
        limit_price: float = None,
        stop_price: float = None,
        client_order_id: str = None,
    ):
        # Protobuf request
        request = ProtoOANewOrderReq(
            ctidTraderAccountId=self.account_id,
            symbolId=symbol_id,
            orderType=order_type,
            tradeSide=side,
            volume=int(volume * 100),  # cTrader units
            limitPrice=limit_price,
            stopPrice=stop_price,
            clientOrderId=client_order_id,  # Idempotency key
        )
        response = await self.client.send(request)
        return response
```

**Idempotenz-Check:**
```python
async def execute_proposal(proposal: Proposal, ctrader: CTraderClient):
    client_order_id = proposal.client_order_id or f"proposal-{proposal.id}-{uuid4().hex[:8]}"

    # Save before sending
    await db_pool.execute(
        "UPDATE proposals SET client_order_id = $1 WHERE id = $2 AND client_order_id IS NULL",
        client_order_id, proposal.id
    )

    # Check if already executed
    if await _order_exists(ctrader, client_order_id):
        logger.info("proposal_already_executed", proposal_id=proposal.id)
        return

    # Place order with retry
    response = await _place_with_retry(ctrader, proposal, client_order_id)
    return response
```

**Retry-Decorator:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=1, max=60),
    retry=retry_if_exception_type((ConnectionError, RateLimitError)),
)
async def _place_with_retry(ctrader, proposal, client_order_id):
    return await ctrader.place_order(...)
```

**Wichtig:** cTrader-Integration ist komplex. **Nach 1-Tages-Spike-Timebox** entscheiden, ob partielle Wiederverwendung aus `/home/cneise/Project/ALT/ctrader2` moeglich ist (per CLAUDE.md).

**File Structure:**
```
migrations/
├── 012_agent_id_column.sql          # NEW
└── 013_proposal_client_order_id.sql  # NEW
app/
├── clients/
│   └── ctrader.py                    # NEW
└── services/
    └── bot_execution.py              # NEW
```

### References

- PRD: FR6, NFR-R3, NFR-I3
- Architecture: "cTrader Integration", "Dual-Source-Reconciliation"
- CLAUDE.md: "Locked Technical Decisions" — OpenApiPy + 1-Tages-Spike
- Issue M1: agent_id hier (nicht in Story 2.1)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
