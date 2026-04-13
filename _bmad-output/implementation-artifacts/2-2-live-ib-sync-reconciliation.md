# Story 2.2: Live-IB-Sync & Reconciliation

Status: review

## Story

As a Chef,
I want my IB trades to sync automatically in real-time,
so that I don't have to manually trigger imports during the trading day.

## Acceptance Criteria

1. **Given** die App laeuft und ib_async mit TWS/Gateway verbunden ist, **When** eine neue Execution bei IB stattfindet, **Then** wird der Trade automatisch in die trades-Tabelle synchronisiert ohne manuellen Anstoss (FR3)
2. **Given** Live-Sync und Flex-Nightly liefern abweichende Daten fuer denselben Trade, **When** Reconciliation laeuft, **Then** wird Flex-Query als Source-of-Truth behandelt und der Trade entsprechend aktualisiert (FR5)
3. **Given** die TWS/Gateway-Verbindung bricht ab, **When** die Verbindung wiederhergestellt wird, **Then** reconnected ib_async automatisch und setzt den Sync fort ohne Trade-Verlust (NFR-R2)
4. **Given** einen bereits via Live-Sync erfassten Trade, **When** derselbe Trade via Flex-Nightly importiert wird, **Then** wird kein Duplikat erstellt (Erkennung via permId) (FR4)

## Tasks / Subtasks

> **DESCOPE-ENTSCHEIDUNG (Code Review Epic 2, 2026-04-13, Decision D-A b):**
>
> Story 2.2 wird auf "Reconcile + Flex Downloader + Connect-Helper + handle_execution function-as-library" reduziert. Die folgenden ACs werden zu **Story 12.1 (Scheduled-Jobs-Framework)** verschoben:
>
> - **AC #1** (Auto-Sync via execDetailsEvent-Subscription)
> - **AC #3** (Auto-Reconnect mit Exponential Backoff + Backfill)
>
> Begründung: Saubere Subscription + Reconnect benötigen einen langlebigen Connection-Loop, eine echte TWS-Instanz für Tests und Health-Monitoring — alles Themen, die Story 12.1 explizit als Scope hat (APScheduler + Health-Widget + Background-Jobs). Story 2.2 liefert die Building Blocks (`connect_ib`, `disconnect_ib`, `execution_to_trade`, `handle_execution`, `upsert_trade`), Story 12.1 verdrahtet sie.
>
> Die fertigen Stücke aus Story 2.2 bleiben im Codebase und sind unit-tested.

- [x] Task 1: ib_async Client Setup (AC: 1, 3) — **Connect/Disconnect-Helper geliefert**
  - [x] `app/clients/ib.py` mit `connect_ib()` + `disconnect_ib()` (One-Shot mit 5s Timeout, kein Retry-Loop)
  - [x] Verbindung zu TWS/Gateway via ib_async
  - [x] Environment: `IB_HOST`, `IB_PORT`, `IB_CLIENT_ID`
  - [x] Connection-Lifecycle im FastAPI Lifespan (Connect on startup, Disconnect on shutdown — kein Reconnect-Loop)
- [x] Task 2: Live-Execution-Handler (AC: 1) — **Function geliefert, aber nicht subscribed**
  - [x] `app/services/ib_live_sync.handle_execution(conn, event)` als pure async function
  - [x] `execution_to_trade(event)` parsed multi-fill events (weighted average price)
  - [x] **`upsert_trade()` statt `insert_trades()`** — Multi-Fill-Events enrichen den existierenden Row (Code-Review H2)
  - [x] Logging via structlog
  - [ ] **DEFERRED to Story 12.1:** `ib.execDetailsEvent += handle_execution` Subscription im Lifespan
- [ ] Task 3: Auto-Reconnect (AC: 3) — **Komplett deferred**
  - [ ] DEFERRED to Story 12.1: `ib.connectedEvent` / `ib.disconnectedEvent` handlers
  - [ ] DEFERRED to Story 12.1: Retry-Loop mit Exponential Backoff
  - [ ] DEFERRED to Story 12.1: Missing-Trades-Backfill via reqExecutions
- [x] Task 4: Reconciliation Function (AC: 2, 4) — **Function geliefert, kein Scheduler**
  - [x] `app/services/ib_reconcile.run_nightly_reconcile()` als pure async function
  - [x] `download_flex_xml()` 2-step request → poll → final flow mit 30s timeout
  - [x] `reconcile_with_flex(conn, xml)` mit UPDATE-WHERE-divergent-fields (Flex wins, FR5)
  - [ ] **DEFERRED to Story 12.1:** APScheduler-Job "ib_nightly_reconcile" Registration (taeglich 02:00 UTC)
- [x] Task 5: Tests (AC: 2, 4) — **Mock-based für die geliefer
ten Funktionen**
  - [x] `tests/unit/test_ib_live_sync.py` — `execution_to_trade` mit MockEvent (12 Tests)
  - [x] `tests/unit/test_ib_reconcile.py` — `download_flex_xml` mit httpx.MockTransport (8 Tests)
  - [ ] **DEFERRED to Story 12.1:** Test fuer execDetailsEvent-Subscription (braucht TWS oder vollstaendigen ib_async-Mock)
  - [ ] **DEFERRED to Story 12.1:** Test fuer Disconnect+Reconnect-Loop
  - [ ] **DEFERRED to Story 12.1:** Test fuer Reconcile bei Divergenz (braucht real DB seed)

## Dev Notes

**ib_async Connection Pattern:**
```python
from ib_async import IB, Contract

ib = IB()
await ib.connectAsync(host="127.0.0.1", port=7497, clientId=1)
ib.execDetailsEvent += on_execution
```

**Reconciliation-Regel:**
- **Flex-Query = Source of Truth** (FR5)
- Live-Sync ist fuer sofortige Verfuegbarkeit, kann aber Execution-Details nicht-final haben
- Bei Diskrepanz: Flex-Werte uebernehmen, speziell fuer `fees`, `pnl`, `exit_price`
- Trade-Historie in structlog loggen (welche Felder wurden geaendert)

**IB Flex Query Web Service API:**
- Token-basiert (im .env als `IB_FLEX_TOKEN`)
- Query-ID ebenfalls in .env (`IB_FLEX_QUERY_ID`)
- Endpoint: `https://ndcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest`
- Two-Step: Request Statement → Poll for Ready → Download XML

**NFR-R2 Kriterium (testbar):**
"Live-IB-Sync ueberlebt TWS/Gateway-Reconnects mit Auto-Reconnect und State-Recovery ohne Trade-Verlust; verifiziert durch Dual-Source-Reconciliation-Kriterium"

**File Structure:**
```
app/
├── clients/
│   └── ib.py                 # NEW - ib_async wrapper
├── services/
│   ├── ib_flex_import.py     # EXISTS (from 2.1)
│   ├── ib_live_sync.py       # NEW - Live execution handler
│   └── ib_reconcile.py       # NEW - Nightly reconciliation
└── jobs/
    └── ib_nightly.py         # NEW - APScheduler job
```

**Rate-Limit-Awareness (NFR-I3):**
- Exponential Backoff bei 429: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max 5 Retries)
- Gilt auch fuer Flex-Query-Download (HTTP-API)

### References

- PRD: FR3, FR4, FR5, NFR-R1, NFR-R2, NFR-I3
- Architecture: "IB Integration", "Dual-Source-Reconciliation"
- Dependency: Story 2.1 (trades-Tabelle), Story 1.1 (APScheduler im Lifespan)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
