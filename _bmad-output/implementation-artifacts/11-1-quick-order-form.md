# Story 11.1: Quick-Order-Formular & Validierung

Status: ready-for-dev

## Story

As a Chef,
I want a quick order form to place IB stock orders with trailing stops,
so that I can trade directly from ctrader without switching to TWS.

## Acceptance Criteria

1. **Given** das Journal oder eine Watchlist, **When** Chef "Quick Order" waehlt, **Then** oeffnet sich ein Formular mit: Symbol (vorausgefuellt aus Kontext), Side (Buy/Sell), Quantity, Limit-Preis, Trailing-Stop-Amount (absolut $ oder prozentual) (FR53)
2. **Given** das Quick-Order-Formular, **When** inspiziert, **Then** hat es <= 6 Felder mit Auto-Focus, Tab-Navigation und Inline-Validierung auf Blur (UX-DR58, UX-DR59, UX-DR62)
3. **Given** ein ungueltige Eingabe (z.B. negativer Preis), **When** das Feld den Fokus verliert, **Then** erscheint ein roter Rahmen + Fehlertext unterhalb (UX-DR59)

## Tasks / Subtasks

- [ ] Task 1: Quick-Order-Form Template
  - [ ] `app/templates/fragments/quick_order_form.html`
  - [ ] Felder: Symbol (readonly wenn prefilled), Side-Toggle (Buy/Sell), Quantity (int), Limit-Preis (decimal), Trailing-Stop-Amount + Unit-Toggle ($/%)
  - [ ] Auto-focus erstes Feld
- [ ] Task 2: Quick-Order-Trigger
  - [ ] Button in Trade-Drilldown und Journal-Zeile: "Quick Order"
  - [ ] Watchlist-Context noch Phase 2 (nur Journal fuer MVP)
- [ ] Task 3: Inline-Validation (AC: 3)
  - [ ] HTMX `hx-validate` oder Alpine.js
  - [ ] On-blur: check quantity > 0, limit_price > 0, trailing_stop > 0
  - [ ] Rote Border + Fehlertext unter Feld
- [ ] Task 4: Side-Toggle (AC: 1)
  - [ ] 2 Buttons: Buy / Sell
  - [ ] Visueller Toggle (accent bei active)
- [ ] Task 5: Unit-Toggle fuer Trailing-Stop (AC: 1)
  - [ ] Toggle zwischen $ und %
  - [ ] Preview des berechneten initialen Stop-Levels (fuer Bestaetigungs-UI Story 11.2)
- [ ] Task 6: Form-Submission → Bestaetigungs-Schritt (Story 11.2)
  - [ ] POST leitet zu Confirmation-Viewport weiter, nicht direkt Order-Platzierung

## Dev Notes

**Form-Layout:**
```
┌─ QUICK ORDER — AAPL ─────────────┐
│ SIDE                              │
│ [ Buy ] [ Sell ]                  │  ← toggle
│ QUANTITY                          │
│ [ 100        ]                    │
│ LIMIT PRICE                       │
│ [ 150.00     ]                    │
│ TRAILING STOP                     │
│ [ 2.50    ] [$] [%]               │  ← value + unit
│                                   │
│        [Continue →]               │
└───────────────────────────────────┘
```

**Validierungs-Regeln:**
- Symbol: required, vorausgefuellt aus Kontext
- Side: required, enum buy/sell
- Quantity: required, int > 0
- Limit-Price: required, decimal > 0
- Trailing-Stop: required, decimal > 0

**Prefill-Pattern:**
```
GET /journal/trades/42 → Trade-Drilldown mit "Quick Order"-Button
GET /trades/42/quick-order → Quick-Order-Form mit symbol=AAPL prefilled
```

**Inline-Validation-Pattern:**
```html
<div x-data="{ error: null }">
  <label>QUANTITY</label>
  <input type="number"
         @blur="error = $el.value <= 0 ? 'Muss positiv sein' : null"
         :class="{ 'border-red-500': error }">
  <p x-show="error" x-text="error" class="text-[var(--color-red)] text-sm"></p>
</div>
```

**File Structure:**
```
app/
├── routers/
│   └── quick_order.py          # NEW - /trades/{id}/quick-order, etc.
└── templates/
    └── fragments/
        └── quick_order_form.html  # NEW
```

### References

- PRD: FR53
- UX-Spec: UX-DR58, UX-DR59, UX-DR62
- Dependency: Story 2.4 (Trade-Drilldown mit Button)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
