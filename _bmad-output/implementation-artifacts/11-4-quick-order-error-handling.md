# Story 11.4: Fehler-Handling — Transient vs Terminal

Status: ready-for-dev

## Story

As a Chef,
I want clear distinction between retryable and fatal order errors,
so that I know when to wait and when to act.

## Acceptance Criteria

1. **Given** ein transienter Fehler (Netzausfall, TWS-Reconnect), **When** die Order-Submission fehlschlaegt, **Then** wird automatisch ein Retry ausgefuehrt (max 3x, mit Exponential Backoff) (FR58)
2. **Given** ein terminaler Fehler (Margin-Fehler, ungueltiges Symbol, Markt geschlossen), **When** die Order-Submission fehlschlaegt, **Then** sieht Chef eine klare Fehlermeldung als persistierender Error-Toast (rot, manuell zu schliessen) mit spezifischem Grund (FR58, UX-DR52)
3. **Given** einen transienten Fehler waehrend des Retry, **When** der Retry erfolgreich ist, **Then** wird ein Success-Toast angezeigt und der Order-Status normal weiterverfolgt

## Tasks / Subtasks

- [ ] Task 1: Error-Classification
  - [ ] `app/services/error_classifier.py` — `classify_ib_error(error_code, error_msg) -> Literal["transient", "terminal"]`
  - [ ] Transient: 1100 (Connectivity lost), 1101 (Data farm disconnected), 2104/2106 (connection OK), network errors
  - [ ] Terminal: 201 (Order rejected), 202 (Margin), 110 (Invalid symbol), 200 (Security not found), etc.
- [ ] Task 2: Retry-Logic (AC: 1)
  - [ ] In `app/services/ib_order.py` — `place_bracket_order` mit Retry-Decorator
  - [ ] Max 3 Retries, Exponential Backoff 1s/2s/4s
  - [ ] Nur bei transient errors
- [ ] Task 3: Terminal-Error-UI (AC: 2)
  - [ ] Error-Toast via HX-Trigger
  - [ ] Toast-Variant: error (persistent, nicht auto-dismiss)
  - [ ] Message zeigt IB-Error-Code + human-readable Erklaerung
- [ ] Task 4: Success-Toast nach Retry-Erfolg (AC: 3)
  - [ ] Success-Toast mit "Order platziert nach N Retries"
  - [ ] Weiter normaler Status-Flow
- [ ] Task 5: Error-Logging
  - [ ] structlog: jeder error mit classification, retry_count, final_outcome
- [ ] Task 6: Tests
  - [ ] Mock IB: Connectivity-Error → Retry → Success
  - [ ] Mock IB: Margin-Error → Terminal → Error-Toast
  - [ ] Mock IB: 3x transient → Give-up → Error-Toast

## Dev Notes

**IB-Error-Code-Classification:**
```python
TRANSIENT_CODES = {
    1100,  # Connectivity between IB and TWS has been lost
    1101,  # Connectivity restored, data lost
    2104,  # Market data farm connection OK
    2106,  # HMDS data farm connection OK
    2158,  # Sec-def data farm connection OK
}

TERMINAL_CODES = {
    200,   # No security definition
    201,   # Order rejected
    202,   # Order cancelled (user or system)
    110,   # Price doesn't conform to min variation
    161,   # Margin requirement violation
    # ... more
}

def classify_ib_error(error_code: int, error_msg: str) -> str:
    if error_code in TRANSIENT_CODES:
        return "transient"
    if error_code in TERMINAL_CODES:
        return "terminal"
    # Fallback: unknown → treat as terminal (safer)
    return "terminal"
```

**Retry-Pattern:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

def is_transient(exception):
    if isinstance(exception, IBError):
        return classify_ib_error(exception.code, exception.msg) == "transient"
    return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=8),
    retry=retry_if_exception(is_transient),
    reraise=True,
)
async def place_bracket_order_with_retry(...):
    return await place_bracket_order(...)
```

**Error-Toast-Messages (Beispiele):**
| Error | Toast |
|-------|-------|
| Margin violation | "Order abgelehnt: Unzureichendes Margin" |
| Invalid symbol | "Order abgelehnt: Symbol 'XYZ' nicht gefunden" |
| Market closed | "Order abgelehnt: Markt geschlossen (NYSE)" |
| Connectivity lost (after 3 retries) | "Verbindung zu IB verloren. Bitte spaeter erneut versuchen." |

**UI-Pattern:**
- Error-Toast: persistent, red, X-Button zum Schliessen
- Success-Toast: auto-dismiss 3s, gruen
- Beide via toast-macro aus Story 3.1

**File Structure:**
```
app/
├── services/
│   ├── error_classifier.py     # NEW
│   └── ib_order.py             # UPDATE - retry wrapper
└── templates/
    └── components/
        └── toast.html          # EXISTS (Story 3.1)
```

### References

- PRD: FR58
- UX-Spec: UX-DR52 (Error Toast), UX-DR51 (Success Toast)
- Dependency: Story 11.2 (Bracket-Order), Story 3.1 (Toast-Component)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
