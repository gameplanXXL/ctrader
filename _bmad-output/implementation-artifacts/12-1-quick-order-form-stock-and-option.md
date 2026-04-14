# Story 12.1: Quick-Order-Formular — Asset-Class-Toggle (Stock | Option)

Status: ready-for-dev

<!-- Created 2026-04-14 after PM-scope-update. Supersedes the old Story 11.1 (Aktien-only + Trailing-Stop) — new scope: Aktien + Single-Leg-Optionen (Long/Short Call/Put) mit festem Stop-Loss. Epic 12 ans Ende der Pipeline verschoben. -->

## Story

As a Chef,
I want a quick order form with an asset class toggle so that I can place stock orders *and* single-leg option orders (especially Short Call/Put for premium-selling swing trades) without switching to Trader Workstation.

## Acceptance Criteria

1. **Given** das Journal, eine Watchlist oder ein Trade-Drilldown, **When** Chef "Quick Order" waehlt, **Then** oeffnet sich ein Formular mit **Asset-Class-Toggle Stock | Option** (Tab-UI, Keyboard `S`/`O`). (FR53)

2. **Given** den Stock-Modus, **When** das Formular inspiziert wird, **Then** enthaelt es: Symbol (vorausgefuellt aus Kontext, readonly), Side (Buy/Sell, Radio), Quantity (Number), Limit-Preis (Number, optional mit Current-Price-Hint), **fester Stop-Loss** (Number, absolut $ oder prozentual vom Limit via Unit-Toggle) — <= 6 Felder, Auto-Focus, Tab-Navigation, Inline-Validierung on Blur. (FR53, UX-DR58, UX-DR59, UX-DR62)

3. **Given** den Option-Modus, **When** das Formular inspiziert wird, **Then** enthaelt es: Underlying (vorausgefuellt, readonly), **Side (Buy-To-Open / Sell-To-Open)** als Radio, **Expiry** (Dropdown aus IB-Option-Chain, min. 5 DTE), **Strike** (Dropdown aus Chain), **Right** (Call/Put als Radio), Contracts (Quantity, int), Limit pro Contract (Number), **fester Stop-Loss auf den Option-Preis** (Number + Unit-Toggle $ / %) — <= 8 Felder. (FR53)

4. **Given** den Option-Modus, **When** Expiry oder Strike veraendert wird, **Then** werden die Werte gegen die IB-Option-Chain validiert via `ib_async.reqContractDetails()`; ungueltige Kombinationen zeigen roter Rahmen + Inline-Fehlermeldung. (UX-DR59)

5. **Given** eine Short-Option (Side = Sell-To-Open), **When** das Formular aktiv ist, **Then** erscheint ein **persistenter roter Warn-Banner** ueber dem Formular: "SHORT OPTION — Margin-Anforderung & Assignment-Risk". Nicht schliessbar bis Asset-Class oder Side geaendert wird. (FR53)

6. **Given** eine ungueltige Eingabe (negativer Preis, Stop-Level auf der falschen Seite des Limits, Expiry < 5 DTE, Contracts = 0, nicht-handelbare Strike/Expiry-Kombination), **When** das Feld den Fokus verliert, **Then** erscheint ein roter Rahmen + Fehlertext unterhalb. (UX-DR59)

7. **Given** TWS oder IB Gateway ist nicht verbunden (kein heartbeat via `ib_async.isConnected()`), **When** Chef das Quick-Order-Formular oeffnet, **Then** erscheint ein Banner "IB TWS/Gateway nicht verbunden — Start TWS oder Gateway auf Port 7497/4002" und **der "Weiter"-Button ist disabled**. (FR58)

## Tasks / Subtasks

- [ ] Task 1: Asset-Class-Toggle & Base-Template (AC: 1)
  - [ ] `app/templates/components/quick_order_form.html` — Tab-UI oben
  - [ ] Alpine.js `x-data="{ mode: 'stock' }"` state management
  - [ ] Keyboard-Listener: `S` → stock, `O` → option
  - [ ] Conditionally-rendered field groups per mode

- [ ] Task 2: Stock-Modus-Felder (AC: 2)
  - [ ] Felder: Symbol (readonly), Side-Toggle (Buy/Sell), Quantity (int), Limit-Preis (decimal), Fester Stop-Loss (decimal) + Unit-Toggle $/%
  - [ ] Auto-focus erstes editierbares Feld, Tab-Navigation

- [ ] Task 3: Option-Modus-Felder (AC: 3)
  - [ ] Felder: Underlying (readonly), Side (Buy-To-Open/Sell-To-Open), Expiry (Dropdown), Strike (Dropdown), Right (Call/Put), Contracts (int), Limit/Contract (decimal), Fester Stop auf Option-Preis (decimal) + Unit-Toggle $/%
  - [ ] HTMX `hx-get="/trades/quick-order/options-chain?symbol={symbol}"` um Chain zu laden
  - [ ] Expiry-Dropdown populates Strike-Dropdown via `hx-trigger="change"`

- [ ] Task 4: Options-Chain-Loader (AC: 3, 4)
  - [ ] Neuer Endpoint `GET /trades/quick-order/options-chain?symbol={symbol}` unter `app/routers/trades.py`
  - [ ] `app/services/ib_options_chain.py` (NEW) mit `fetch_option_chain(ib, symbol)` → returns sorted list of (expiry, strike, right) tupels via `reqContractDetails`
  - [ ] TTL-Cache (15 min) fuer Chain-Results pro Underlying
  - [ ] Filter auf min. 5 DTE

- [ ] Task 5: Short-Option-Warn-Banner (AC: 5)
  - [ ] Persistent red banner above the form in Option mode when side=sell-to-open
  - [ ] CSS: `--color-loss` background, weisser Text, role="alert"
  - [ ] Banner bleibt sichtbar bis Asset-Class → Stock ODER Side → Buy-To-Open

- [ ] Task 6: Inline-Validation (AC: 6)
  - [ ] Alpine.js on-blur validation per Feld
  - [ ] Stop-Loss-Regel: Bei Buy/Long muss stop < limit, bei Sell/Short stop > limit
  - [ ] Expiry-Regel: min. 5 DTE (nutze JavaScript-Date-Vergleich)
  - [ ] Contracts: int > 0
  - [ ] Chain-Validation: Strike + Expiry muessen in der geladenen Chain-Liste liegen

- [ ] Task 7: IB-Connection-Check (AC: 7)
  - [ ] Lifespan-State `request.app.state.ib_available` via `getattr`
  - [ ] Template render-time branch: wenn nicht available → Banner + disabled submit
  - [ ] Banner-Text: "IB TWS/Gateway nicht verbunden — Start TWS oder Gateway auf Port 7497/4002"

- [ ] Task 8: Router-Hook (AC: 1)
  - [ ] `GET /trades/quick-order/form?symbol={symbol}&asset_class={stock|option}` in `app/routers/trades.py`
  - [ ] Prefill asset_class from query param (default=stock)
  - [ ] Return `quick_order_form.html` fragment

- [ ] Task 9: Tests
  - [ ] Unit test: form renders with stock mode default
  - [ ] Unit test: option mode shows Chain fields
  - [ ] Unit test: short-option banner appears conditionally
  - [ ] Unit test: IB-disconnected state disables submit
  - [ ] Unit test: options-chain endpoint returns sorted (expiry, strike) tupels
  - [ ] Mock `ib_async.reqContractDetails` via `unittest.mock.patch`

## Dev Notes

**Form-Layout (Stock):**
```
┌─ QUICK ORDER — AAPL ──── [Stock] [Option] ─┐
│ SIDE      [ Buy ] [ Sell ]                  │
│ QUANTITY  [ 100       ]                     │
│ LIMIT     [ 185.00    ]                     │
│ STOP      [ 180.00    ] [$] [%]             │
│                                              │
│                        [Weiter →]           │
└──────────────────────────────────────────────┘
```

**Form-Layout (Option, Short):**
```
┌─ QUICK ORDER — AAPL ──── [Stock] [Option] ─┐
│ ⚠ SHORT OPTION — Margin & Assignment-Risk  │  ← persistent red banner
│ SIDE    [ BTO ] [ STO ]                    │
│ EXPIRY  [ 2026-05-16  ▾]                   │  ← Dropdown from chain
│ STRIKE  [ 180         ▾]                   │  ← Dropdown from chain
│ RIGHT   [ Call ] [ Put ]                   │
│ CONTRACTS [ 5         ]                    │
│ LIMIT/C   [ 3.20      ]                    │
│ STOP $/C  [ 1.60      ] [$] [%]            │  ← on the option price, not underlying
│                                             │
│                       [Weiter →]            │
└─────────────────────────────────────────────┘
```

**Options-Chain-Endpoint-Shape:**
```python
# GET /trades/quick-order/options-chain?symbol=AAPL
# returns:
{
    "symbol": "AAPL",
    "expiries": ["2026-05-16", "2026-06-20", "2026-07-18"],
    "strikes_by_expiry": {
        "2026-05-16": [170, 175, 180, 185, 190, 195, 200],
        ...
    }
}
```

**IB-Chain-Fetch-Pattern:**
```python
from ib_async import Option

async def fetch_option_chain(ib, symbol: str) -> list[tuple[str, Decimal, str]]:
    # First qualify the underlying to get conId
    underlying = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(underlying)

    # Then fetch option parameters
    params = await ib.reqSecDefOptParamsAsync(
        underlyingSymbol=symbol,
        futFopExchange='',
        underlyingSecType='STK',
        underlyingConId=underlying.conId,
    )
    # params[0].expirations, params[0].strikes — filter min 5 DTE here
    ...
```

**Kill-Switch-Exemption:** FR42 / Architecture Decision #9 — manuelle Quick-Orders sind vom Regime-Kill-Switch **ausgenommen**. Bei F&G < 20 zeigt das Formular einen **gelben informativen Warnbanner** oberhalb ("⚠ Aktuelles Regime: F&G = 18, Bot-Strategien pausiert — Swing-Order ist manuell und nicht blockiert"), aber der Submit bleibt aktiv. **Kein Block.**

**File Structure:**
```
app/
├── routers/
│   └── trades.py              # UPDATE — new endpoints
├── services/
│   └── ib_options_chain.py    # NEW — chain fetch + cache
└── templates/
    └── components/
        └── quick_order_form.html  # NEW — stock + option modes
```

### References

- PRD: FR53, FR58, FR42 (Kill-Switch-Exemption)
- Architecture: Decision #9 (IB Swing-Order), order_service.py, Decision B2 (Router unter trades.py)
- UX-Spec: Journey 6, Component `quick_order_form` (Stock + Option modes)
- epics.md: Epic 12 Story 12.1
- Dependency: Story 2.4 (Trade-Drilldown mit Button), Story 9.1 (Regime-Snapshot), IB-Connection-State aus Story 2.2

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
