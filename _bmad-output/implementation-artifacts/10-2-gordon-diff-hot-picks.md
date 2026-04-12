# Story 10.2: Wochen-Diff & HOT-Picks-Anzeige

Status: ready-for-dev

## Story

As a Chef,
I want to see what changed in the trend radar compared to last week,
so that I can quickly identify new opportunities and fading trends.

## Acceptance Criteria

1. **Given** aktuelle und vorherige Woche Snapshots existieren, **When** die Trends-Seite (/trends) geladen wird, **Then** zeigt sie: Hero-Block mit Weekly-Delta, F&G, VIX, Kill-Switch-Status, darunter HOT-Picks als kompakte Liste (FR47, UX-DR28)
2. **Given** die HOT-Picks-Liste, **When** angezeigt, **Then** sind Eintraege farblich kategorisiert: neu (gruen), weggefallen (rot), unveraendert (neutral) (FR47)
3. **Given** die Trends-Seite, **When** geladen, **Then** ist der initiale Scan in 2 Sekunden moeglich ohne Scrollen (UX-DR36)

## Tasks / Subtasks

- [ ] Task 1: Gordon-Diff-Service
  - [ ] `app/services/gordon_diff.py` — `compute_diff(current, previous) -> dict`
  - [ ] Output: { new: [...], dropped: [...], unchanged: [...] }
  - [ ] Vergleich via symbol
- [ ] Task 2: Trends-Page Template
  - [ ] `app/templates/pages/trends.html`
  - [ ] Hero-Block oben
  - [ ] HOT-Picks-Liste darunter
- [ ] Task 3: Color-Categorization (AC: 2)
  - [ ] `.new` → gruene Border/Left-Accent
  - [ ] `.dropped` → rote Border/Left-Accent
  - [ ] `.unchanged` → neutral
- [ ] Task 4: Hero-Block
  - [ ] Reuse stat_card-Macro
  - [ ] Metriken: Weekly-Delta (Anzahl neuer/gedroppter Picks), F&G, VIX, Kill-Switch-Status
- [ ] Task 5: Performance (AC: 3)
  - [ ] Seitengroesse klein halten
  - [ ] Kein Scrolling im Default-Viewport (UX-DR28, UX-DR36)

## Dev Notes

**Diff-Logic:**
```python
def compute_diff(current: list[dict], previous: list[dict]) -> dict:
    curr_symbols = {p['symbol'] for p in current}
    prev_symbols = {p['symbol'] for p in previous}

    return {
        'new': [p for p in current if p['symbol'] not in prev_symbols],
        'dropped': [p for p in previous if p['symbol'] not in curr_symbols],
        'unchanged': [p for p in current if p['symbol'] in prev_symbols],
    }
```

**Trends-Page-Layout:**
```
┌─ GORDON TREND RADAR (Woche 15) ──────────────────┐
│                                                    │
│  WEEKLY-DELTA  F&G   VIX   KILL-SWITCH            │
│  +3  -1        55    18    ● OFF                  │
│                                                    │
├────────────────────────────────────────────────────┤
│ ● NEU    (3)                                       │
│   NVDA   swing    AI demand persists              │
│   TSLA   swing    Autonomous driving progress     │
│   BTCUSD intraday Bull run above 70k              │
├────────────────────────────────────────────────────┤
│   UNCHANGED (5)                                    │
│   AAPL, MSFT, GOOGL, ETH, AVAX                    │
├────────────────────────────────────────────────────┤
│ ● WEGGEFALLEN (1)                                  │
│   META   swing    Ad-market uncertainty           │
└────────────────────────────────────────────────────┘
```

**Kompaktheit:** Die ganze Seite muss in den Default-Viewport (~850px) passen ohne Scroll (UX-DR36).

**File Structure:**
```
app/
├── services/
│   └── gordon_diff.py              # NEW
├── routers/
│   └── pages.py                    # UPDATE - /trends
└── templates/
    └── pages/
        └── trends.html             # UPDATE (replaces placeholder)
```

### References

- PRD: FR47
- UX-Spec: UX-DR28 (Layout), UX-DR36 (2s Scan)
- Dependency: Story 10.1 (gordon_snapshots), Story 9.1 (regime data fuer Hero)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
