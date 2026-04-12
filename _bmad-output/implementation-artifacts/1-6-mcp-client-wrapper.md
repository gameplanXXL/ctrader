# Story 1.6: MCP-Client-Wrapper & Contract-Snapshot

Status: ready-for-dev

## Story

As a Chef,
I want a verified connection to the fundamental MCP server,
so that I know the AI integration works before building features on top of it.

## Acceptance Criteria

1. **Given** der fundamental MCP-Server laeuft, **When** die App startet, **Then** wird eine HTTP/SSE-Verbindung hergestellt und eine Tools-Liste abgerufen
2. **Given** die MCP-Verbindung ist erfolgreich, **When** Tools gelistet werden, **Then** werden die verfuegbaren Tools als Contract-Snapshot-JSON in `data/mcp-snapshots/` gespeichert
3. **Given** der MCP-Server laeuft nicht, **When** die App startet, **Then** wird eine Warnung geloggt und die App faehrt fort (Graceful Degradation, kein Crash)
4. **Given** den MCP-Client-Wrapper, **When** ein beliebiger MCP-Call ausgefuehrt wird, **Then** erzwingt er einen 10-Sekunden-Timeout (NFR-I1)

## Tasks / Subtasks

- [ ] Task 1: MCP-Client-Wrapper implementieren (AC: 1, 4)
  - [ ] `app/clients/mcp.py` mit `MCPClient` Klasse
  - [ ] HTTP/SSE Streamable HTTP Transport
  - [ ] Verbindung zum fundamental-Server via Environment-Variable `MCP_FUNDAMENTAL_URL`
  - [ ] Timeout-Enforcement: 10s via asyncio.wait_for
- [ ] Task 2: Contract-Snapshot-Freeze (AC: 2)
  - [ ] `list_tools()` Methode auf MCPClient
  - [ ] Snapshot nach `data/mcp-snapshots/week0-YYYYMMDD.json` schreiben
  - [ ] Format: JSON mit Tool-Namen, Parameters, Return-Types
- [ ] Task 3: Graceful Degradation (AC: 3)
  - [ ] Bei Connection-Error: structlog WARNING, NICHT crashen
  - [ ] App-State: `mcp_available: bool` fuer spaetere Checks
- [ ] Task 4: Lifespan-Integration (AC: 1)
  - [ ] In FastAPI Lifespan: MCP-Handshake beim Start
  - [ ] Client-Instance in `app.state.mcp_client`
- [ ] Task 5: Hello-World MCP-Call Demo-Route (AC: 1)
  - [ ] GET `/debug/mcp-tools` listet verfuegbare Tools (nur in Dev-Mode)
  - [ ] Bestaetigt end-to-end Funktionalitaet
- [ ] Task 6: Integration-Test (AC: 1, 2, 3, 4)
  - [ ] Test mit laufendem fundamental-Server: Tools werden gelistet
  - [ ] Test mit gestopptem Server: App faehrt fort, Warnung geloggt
  - [ ] Test Timeout: Simulierter 15s-Delay fuehrt zu asyncio.TimeoutError

## Dev Notes

**MCP-Architektur:**
- `fundamental` MCP-Server laeuft als unabhaengiger Prozess ausserhalb Docker Compose
- Start: `cd /home/cneise/Project/fundamental && make start`
- ctrader verbindet als MCP-Client via Streamable HTTP Transport (HTTP/SSE)

**Verfuegbare MCP-Tools (zur Referenz, NICHT in dieser Story zu nutzen):**
- `fundamentals` — Stock/Crypto fundamental analysis
- `price` — Price data
- `news` — News search
- `search` — General search
- `crypto` — Crypto-specific

**Agents im fundamental-Server:**
- **Viktor** (SFA) — Aktien Analyst
- **Rita** (SFA) — Aktien Risk Manager
- **Satoshi** (CFA) — Crypto Analyst
- **Cassandra** (CFA) — Crypto Risk Manager
- **Gordon** — Daytrading Trend Radar (wöchentlich)

**Contract-Snapshot-Purpose:**
Der Snapshot vom 2026-04-xx (Woche 0) wird in Story 5.4 als Baseline fuer den taeglichen MCP-Contract-Test genutzt. Drift-Erkennung basiert auf diesem eingefrorenen Zustand.

**File Structure:**
```
app/
├── clients/
│   ├── __init__.py
│   └── mcp.py               # NEW - MCPClient wrapper
└── routers/
    └── debug.py             # NEW (Dev-Mode only)

data/
└── mcp-snapshots/
    └── week0-YYYYMMDD.json  # Contract-Snapshot
```

**Unified Pattern (Vorlage fuer spaetere MCP-Calls):**
```python
class MCPClient:
    async def call(self, tool: str, **kwargs) -> dict:
        try:
            return await asyncio.wait_for(
                self._transport.call(tool, **kwargs),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("mcp_timeout", tool=tool)
            raise
        except ConnectionError:
            logger.error("mcp_unavailable", tool=tool)
            raise
```

### References

- PRD: NFR-I1 (Timeout), FR24 (Contract-Test)
- Architecture: "External Dependencies", "MCP Integration", "Week-0 Critical Deliverables"
- CLAUDE.md: "Harte Dependency: fundamental" Abschnitt
- Dependency-Server: `/home/cneise/Project/fundamental`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
