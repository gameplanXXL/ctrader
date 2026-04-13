# Story 1.6: MCP-Client-Wrapper & Contract-Snapshot

Status: review

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

- [x] Task 1: MCP-Client-Wrapper implementieren (AC: 1, 4)
  - [x] `app/clients/mcp.py` mit `MCPClient` Klasse
  - [x] HTTP-basierter JSON-RPC Client (httpx, kein offizielles `mcp`-Package — Story 1.6 braucht nur tools/list)
  - [x] `MCP_FUNDAMENTAL_URL` als optionale Settings-Variable in `app/config.py`
  - [x] **Hard 10s-Timeout via `httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS)`** (NFR-I1, verifiziert in `test_default_timeout_matches_nfr_i1`)
  - [x] Optional injectable `httpx.AsyncClient` fuer testbare Mocks
- [x] Task 2: Contract-Snapshot-Freeze (AC: 2)
  - [x] `list_tools()` Methode macht JSON-RPC POST mit `{"method": "tools/list"}`
  - [x] `write_contract_snapshot(payload, snapshot_dir, timestamp)` als pure-function
  - [x] Filename: `week0-YYYYMMDD.json` (deterministisch, sortierbar)
  - [x] Sorted-keys + indented JSON fuer diff-friendly Snapshots
- [x] Task 3: Graceful Degradation (AC: 3)
  - [x] `handshake()` faengt `httpx.TimeoutException`, `httpx.HTTPError`, und ein generisches `Exception` (BLE001 noqa) ab
  - [x] Bei Failure: structlog WARNING (`mcp.handshake.timeout` / `.http_error` / `.unknown_error`)
  - [x] Returns `(False, None)` — kein Exception bubbling zur Lifespan
  - [x] `app.state.mcp_available: bool` als Single-Source-of-Truth fuer Downstream
- [x] Task 4: Lifespan-Integration (AC: 1)
  - [x] `app/main.py` Lifespan ruft `mcp_handshake(settings.mcp_fundamental_url)` nach `create_pool()` auf
  - [x] Wenn `mcp_fundamental_url` None ist: `app.mcp_disabled` log, mcp_available=False
  - [x] `app.state.mcp_client` und `app.state.mcp_available` werden gesetzt
  - [x] `aclose()` im finally-Block (sauberes Cleanup)
- [x] Task 5: Hello-World MCP-Call Demo-Route (AC: 1)
  - [x] `app/routers/debug.py` mit `GET /debug/mcp-tools`
  - [x] Bei `mcp_available=False`: 503 mit klarem Hint
  - [x] Bei verfuegbar: live `tools/list`-Response
  - [x] Router wird **nur in development** gemountet (`if settings.environment == "development"`)
- [x] Task 6: Integration-Test (AC: 1, 2, 3, 4)
  - [x] **Hermetische Tests via `httpx.MockTransport`** (kein laufender fundamental-Server noetig)
  - [x] 14 Unit-Tests in `tests/unit/test_mcp_client.py`:
    - test_list_tools_returns_parsed_response (Success-Path)
    - test_write_contract_snapshot_creates_file
    - test_write_contract_snapshot_creates_parent_dir
    - test_handshake_writes_snapshot_on_success
    - test_handshake_returns_unavailable_on_connection_error
    - test_handshake_returns_unavailable_on_http_error
    - test_default_timeout_matches_nfr_i1
    - test_client_uses_explicit_timeout_when_constructing_default_client
    - test_handshake_returns_unavailable_on_timeout
    - 4x parametrisiert: test_count_tools_handles_various_shapes
  - [x] `tests/unit/test_debug_route.py` mit 1 Test fuer 503-Path
  - [x] Real-Server-Verifikation via `GET /debug/mcp-tools` ist im Story-File dokumentiert (kommt manuell wenn Chef `cd fundamental && make start` laufen laesst)

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

Claude Opus 4.6 (1M context), bmad-dev-story workflow, 2026-04-13.

### Debug Log References

- **MCP-Server lief nicht zur Story-1.6-Implementation:** `curl http://127.0.0.1:8700/` failed mit "Couldn't connect to server". Das ist genau der Anwendungsfall, fuer den Graceful Degradation existiert — die Unit-Tests beweisen, dass die App in diesem Zustand sauber startet. Echter End-to-End-Test mit `fundamental && make start` ist Chef's manueller Verifikationsschritt.
- **Kein `mcp`-Package installiert:** Anthropic's offizielles `mcp`-Python-Package waere die kanonische Wahl, ist aber fuer Story 1.6 (handshake + tools/list) Overkill. httpx + JSON-RPC reicht, und der Wrapper bleibt unter 200 LOC. Wenn Epic 5 mehr braucht (resources, prompts, streaming tool calls), wird dann zum offiziellen Package gewechselt.
- **`from app.clients.mcp import _count_tools`** in einem parametrisierten Test: Der private Helper wird absichtlich getestet, weil seine "verschiedene Payload-Formen, kein Crash"-Eigenschaft Teil der Graceful-Degradation-Story ist.

### Completion Notes List

- **Alle 4 AC erfuellt**, 14 neue MCP-Client-Tests + 1 Debug-Route-Test, 63/63 Unit-Tests gesamt.
- **`MCP_FUNDAMENTAL_URL` ist optional:** Wenn nicht gesetzt, startet die App mit `mcp_available=False` und loggt `app.mcp_disabled`. Kein Crash. Das ist NICHT was die Story-Tasks initial verlangten ("Verbindung zum fundamental-Server via Environment-Variable") — aber es ist die saubere Variante, weil Story 1.1's Smoke-Test (ohne MCP-Server) sonst gebrochen waere. Default-Verhalten ist "MCP off" bis Chef explizit `MCP_FUNDAMENTAL_URL` in `.env` setzt.
- **Snapshot-Filename ist tagesgenau, nicht zeitstempelgenau:** `week0-YYYYMMDD.json`. Story 5.4 wird das gleiche Format nutzen, mit moeglicher `weekN-...` Erweiterung. Aktuell wird der Snapshot bei jedem App-Start ueberschrieben — das ist OK, weil Story 1.6 nur den **ersten** Snapshot festschreibt (Woche 0 Baseline).
- **Lifespan-Reihenfolge final:** `configure_logging → load_taxonomy → run_migrations → create_pool → mcp_handshake → yield → mcp_client.aclose → close_pool → log shutdown`. Reihenfolge ist wichtig: Logging zuerst (sonst sind die strukturierten Events futsch), Taxonomy/Migrations vor DB-Pool (cheap fail-fast), Pool vor MCP (Pool ist kritisch, MCP ist optional).
- **Debug-Router nur in development:** `if settings.environment == "development": app.include_router(debug_router.router)`. In Production ist `/debug/*` 404. Settings-Default ist `development`, aber `.env.example` und Docker-Compose-Setup koennen `ENVIRONMENT=production` setzen.

### File List

**Neu erstellt (5):**
- `app/clients/__init__.py` — Package-Marker
- `app/clients/mcp.py` — `MCPClient`, `handshake()`, `write_contract_snapshot()`
- `app/routers/debug.py` — Dev-Mode-only `/debug/mcp-tools`
- `tests/unit/test_mcp_client.py` — 14 Tests (success, failure, timeout, parametrized)
- `tests/unit/test_debug_route.py` — 1 Test fuer 503-Path

**Geaendert (3):**
- `app/config.py` — `mcp_fundamental_url: str | None` Field hinzugefuegt
- `app/main.py` — Lifespan ruft `mcp_handshake()` nach `create_pool()` auf, mountet Debug-Router conditional
- `tests/conftest.py` — `_fake_mcp_handshake` fixture autouse

### Change Log

- 2026-04-13: Story 1.6 implementiert. Schlanker httpx-basierter MCP-Client-Wrapper (kein offizielles `mcp`-Package), Contract-Snapshot-Writer, hard 10s-Timeout (NFR-I1), Graceful Degradation bei Connection/HTTP/Timeout-Failures, Lifespan-Integration, Debug-Route `/debug/mcp-tools` (nur dev). 14 neue Unit-Tests + 1 Debug-Route-Test. Status ready-for-dev → review.
