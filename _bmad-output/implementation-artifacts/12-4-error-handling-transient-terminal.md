# Story 12.4: Fehler-Handling — Transient vs Terminal (inkl. TWS/Gateway-Offline)

Status: ready-for-dev

<!-- Created 2026-04-14 after PM-scope-update. Supersedes the old Story 11.4. New scope: TWS/Gateway-Offline-Check + Option-spezifische Fehlercodes + Margin-Error-Sonderbehandlung. -->

## Story

As a Chef,
I want a clear distinction between retryable and fatal order errors so that I know when to wait versus when I need to act — and I want specific IB error codes for option-specific failures (invalid strike, expired option, insufficient margin) so I can fix the root cause.

## Acceptance Criteria

1. **Given** ein transienter Fehler (Netzausfall, TWS-Reconnect, Gateway-Restart), **When** die Order-Submission fehlschlaegt, **Then** wird automatisch ein Retry ausgefuehrt (max 3x, mit Exponential Backoff, 1s → 60s cap) (FR58).

2. **Given** ein terminaler Fehler (Margin-Fehler, ungueltiges Symbol, Markt geschlossen, Option nicht mehr handelbar, nicht genuegend Buying Power, Strike/Expiry nicht in Chain), **When** die Order-Submission fehlschlaegt, **Then** sieht Chef eine klare Fehlermeldung als **persistierender Error-Toast** (rot, manuell zu schliessen) mit **spezifischem Grund und — bei Options — dem IB-Error-Code** (FR58, UX-DR52).

3. **Given** einen transienten Fehler waehrend des Retry, **When** der Retry erfolgreich ist, **Then** wird ein Success-Toast angezeigt und der Order-Status normal weiterverfolgt (FR58).

4. **Given** TWS oder IB Gateway ist **nicht erreichbar** (kein heartbeat), **When** Chef den Submit-Button druckt, **Then** erscheint sofort ein persistierender Error-Toast "IB TWS/Gateway nicht verbunden — Start TWS oder Gateway auf Port 7497/4002" (FR58).

5. **Given** eine Option-Order, **When** ein Option-spezifischer IB-Error Code zurueckkommt (z.B. 200 "No security definition", 201 "Order rejected", 10148 "OrderId X that needs to be cancelled is not found"), **Then** wird der Fehler gemappt auf eine lesbare deutsche Meldung mit IB-Error-Code in Klammern: "Strike/Expiry-Kombination nicht handelbar (IB 200)".

## Tasks / Subtasks

- [ ] Task 1: Retry-Decorator oder -Helper (AC: 1, 3)
  - [ ] `app/services/order_service.py` → `submit_with_retry(fn, *args, max_attempts=3, initial_delay=1.0, max_delay=60.0)`
  - [ ] Home-grown async-Retry (wie in bot_execution.py von Story 8.1)
  - [ ] Transient-Exceptions: `ConnectionError`, `asyncio.TimeoutError`, `IBConnectionLost` (custom)
  - [ ] Backoff-Sequenz: 1s → 2s → 4s → 8s → ... → 60s cap
  - [ ] structlog-Event pro Retry mit attempt, next_delay, error

- [ ] Task 2: IB-Error-Code-Mapping (AC: 2, 5)
  - [ ] `app/services/ib_error_map.py` (NEW) mit `IB_ERROR_MESSAGES: dict[int, str]`
  - [ ] Mindestens abgedeckte Codes: 200 (No security definition), 201 (Order rejected), 202 (Order cancelled), 321 (Validation error), 501 (Already connected), 1100 (Connectivity lost), 1102 (Connectivity restored), 10148 (OrderId not found), 10197 (No trading permissions)
  - [ ] Funktion `classify(error_code: int) -> tuple[Literal["transient", "terminal"], str]` — returns (category, german_message)
  - [ ] Unknown codes → default to `("terminal", f"Unbekannter IB-Fehler (IB {error_code})")`

- [ ] Task 3: Transient/Terminal-Distinktion im order_service
  - [ ] `submit_stock_bracket` und `submit_option_bracket` fangen `ib_async`-Exceptions ab und werfen eine normalisierte Exception
  - [ ] Custom Exceptions: `IBTransientError`, `IBTerminalError` mit `error_code: int | None` und `ib_message: str`
  - [ ] Retry-Helper fängt nur `IBTransientError` (+ generische ConnectionError)

- [ ] Task 4: TWS/Gateway-Heartbeat-Check (AC: 4)
  - [ ] Vor dem Submit-Versuch: `ib.isConnected()` pruefen
  - [ ] Wenn false: sofort `IBTerminalError("ib_not_connected", code=None)` werfen, kein Retry
  - [ ] Router-Handler in `trades.py` faengt diese ab und returnt HTMX-Swap mit Error-Toast

- [ ] Task 5: Error-Toast-Template (AC: 2, 4, 5)
  - [ ] `app/templates/fragments/error_toast.html` (NEW)
  - [ ] Rot, `role="alert"`, manuell zu schliessen via Button
  - [ ] Text-Template: `{{ german_message }}{% if ib_code %} (IB {{ ib_code }}){% endif %}`
  - [ ] HTMX-Response: `HX-Retarget` auf den Toast-Container, `HX-Reswap="beforeend"`

- [ ] Task 6: Success-Toast bei Retry-Recovery (AC: 3)
  - [ ] Nach erfolgreichem Retry: structlog `bot_execution.retry.recovered` + Success-Toast im bestehenden Story-7.4-Toast-Pattern
  - [ ] Nutzt `HX-Trigger` mit `showToast` Event wie in approvals.py

- [ ] Task 7: Tests
  - [ ] Unit test: submit_with_retry retries N times then succeeds
  - [ ] Unit test: submit_with_retry max-attempts raises final error
  - [ ] Unit test: submit_with_retry short-circuits on terminal error
  - [ ] Unit test: ib_error_map classifies 200 as terminal with "No security definition" de-message
  - [ ] Unit test: ib_error_map classifies 1100 as transient
  - [ ] Unit test: ib_error_map unknown code falls back to terminal
  - [ ] Unit test: submit with not-connected IB raises IBTerminalError without retry
  - [ ] Unit test: error toast fragment renders correct message + ib_code

## Dev Notes

**Exception-Hierarchie:**
```python
class IBOrderError(Exception):
    def __init__(self, message: str, *, error_code: int | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.german_message = message

class IBTransientError(IBOrderError):
    """Network / reconnect / rate-limit — retry with backoff."""

class IBTerminalError(IBOrderError):
    """Margin / invalid symbol / market closed — propagate to operator."""
```

**Retry-Pattern (borrowed from bot_execution.py):**
```python
async def submit_with_retry(
    fn, *args,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    sleep=asyncio.sleep,
):
    delay = initial_delay
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args)
        except IBTerminalError:
            raise
        except (IBTransientError, ConnectionError, asyncio.TimeoutError) as exc:
            if attempt >= max_attempts:
                raise
            logger.warning("order.retry", attempt=attempt, next_delay=delay, err=str(exc))
            await sleep(delay)
            delay = min(delay * 2, max_delay)
```

**IB-Error-Map-Auszug (nicht vollstaendig):**
```python
IB_ERROR_MESSAGES: dict[int, tuple[Literal["transient", "terminal"], str]] = {
    200: ("terminal", "Strike/Expiry-Kombination nicht handelbar"),
    201: ("terminal", "Order abgelehnt"),
    202: ("terminal", "Order storniert"),
    321: ("terminal", "Ungültige Order-Parameter"),
    1100: ("transient", "Verbindung zur IB Gateway verloren"),
    1102: ("transient", "Verbindung wiederhergestellt"),
    10148: ("terminal", "Order-Referenz nicht gefunden"),
    10197: ("terminal", "Keine Handelsberechtigung für dieses Symbol"),
    # Weitere Codes nach Bedarf einpflegen.
}
```

**TWS-Offline-Check:**
```python
async def submit_quick_order(ib: IB, ...):
    if not ib.isConnected():
        raise IBTerminalError(
            "IB TWS/Gateway nicht verbunden — Start TWS oder Gateway auf Port 7497/4002",
            error_code=None,
        )
    ...
```

**File Structure:**
```
app/
├── services/
│   ├── order_service.py   # UPDATE — submit_with_retry + Exception hierarchy
│   └── ib_error_map.py    # NEW
└── templates/
    └── fragments/
        └── error_toast.html  # NEW
```

### References

- PRD: FR58, UX-DR52
- epics.md: Epic 12 Story 12.4
- UX-Spec: Journey 6 Error-Path, Component `error_toast`
- Dependency: Story 12.2 (order_service + quick_orders), Story 2.2 (IB connection state), Story 7.4 (Toast-Framework)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
