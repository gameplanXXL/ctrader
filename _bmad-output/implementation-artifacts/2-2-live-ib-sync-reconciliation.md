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

- [x] Task 1: ib_async Client Setup (AC: 1, 3)
  - [x] `app/clients/ib.py` mit `IBClient` Klasse
  - [x] Verbindung zu TWS/Gateway via ib_async
  - [x] Environment: `IB_HOST`, `IB_PORT`, `IB_CLIENT_ID`
  - [x] Connection-Lifecycle im FastAPI Lifespan
- [x] Task 2: Live-Execution-Listener (AC: 1)
  - [x] `ib.execDetailsEvent` subscribe
  - [x] On-execution: INSERT in trades mit ON CONFLICT DO NOTHING
  - [x] Logging jedes Events via structlog
- [x] Task 3: Auto-Reconnect (AC: 3)
  - [x] `ib.connectedEvent` / `ib.disconnectedEvent` handlers
  - [x] Retry-Loop mit Exponential Backoff (1s, 2s, 4s, 8s, max 60s)
  - [x] Bei Disconnect: Missing-Trades-Backfill via reqExecutions() bei Reconnect
- [x] Task 4: Scheduled Reconciliation (AC: 2, 4)
  - [x] APScheduler-Job "ib_nightly_reconcile"
  - [x] Laeuft taeglich um 02:00 UTC (nach Market-Close)
  - [x] Flex-Query-Download via IB Flex Web Service API
  - [x] UPSERT: Flex-Daten ueberschreiben Live-Sync-Daten bei Konflikten
- [x] Task 5: Integration-Test mit Mock-IB (AC: 1, 2, 3)
  - [x] Mock ib_async mit pytest-asyncio
  - [x] Test: Execution-Event triggert INSERT
  - [x] Test: Disconnect + Reconnect funktioniert
  - [x] Test: Reconciliation ueberschreibt bei Diskrepanz

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
