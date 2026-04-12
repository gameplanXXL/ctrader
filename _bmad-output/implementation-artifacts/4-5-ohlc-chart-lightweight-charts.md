# Story 4.5: Interaktiver OHLC-Chart mit lightweight-charts

Status: ready-for-dev

## Story

As a Chef,
I want an interactive OHLC chart with entry/exit markers in the trade drilldown,
so that I can visually analyze the price action around my trades.

## Acceptance Criteria

1. **Given** einen Trade im Drilldown, **When** der Chart-Bereich geladen wird, **Then** wird ein interaktiver OHLC-Chart via lightweight-charts gerendert mit Candlestick-Daten fuer den Trade-Zeitraum (FR13c)
2. **Given** den OHLC-Chart, **When** gerendert, **Then** sind Entry- und Exit-Zeitpunkte als Marker auf dem Chart sichtbar
3. **Given** den Chart-Daten-Endpoint `GET /trades/{id}/chart_data`, **When** aufgerufen, **Then** liefert er JSON mit OHLC-Daten, Entry/Exit-Markern und optionalen Indikatoren
4. **Given** die Candle-Daten sind nicht verfuegbar, **When** der Chart geladen wird, **Then** wird ein Platzhalter mit "Chart-Daten nicht verfuegbar" in --text-muted angezeigt (UX-DR55)

## Tasks / Subtasks

- [ ] Task 1: lightweight-charts Vendor einbinden (AC: 1)
  - [ ] Download `lightweight-charts.standalone.production.js` (35KB)
  - [ ] Ablegen in `app/static/js/vendor/`
  - [ ] Im base.html laden
- [ ] Task 2: Chart-Data-Endpoint (AC: 3)
  - [ ] GET `/trades/{id}/chart_data` in `app/routers/trades.py`
  - [ ] Query ohlc_candles-Tabelle (aus Story 4.3) fuer Trade-Zeitraum + Padding
  - [ ] Fallback: Live-Fetch via OHLC-Clients falls Cache-Miss
  - [ ] Response-Format:
    ```json
    {
      "candles": [{"time": "...", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}],
      "markers": [
        {"time": "entry_time", "position": "belowBar", "color": "#58a6ff", "shape": "arrowUp", "text": "Entry"},
        {"time": "exit_time", "position": "aboveBar", "color": "#f85149", "shape": "arrowDown", "text": "Exit"}
      ]
    }
    ```
- [ ] Task 3: Chart-Widget im Trade-Drilldown (AC: 1, 2)
  - [ ] `<div id="chart-{{ trade.id }}" class="chart-container"></div>`
  - [ ] JS: Fetch `/trades/{id}/chart_data` via HTMX trigger on expand
  - [ ] Initialize lightweight-charts: `createChart(div, { layout: { background: { color: '#0d1117' }, textColor: '#c9d1d9' } })`
  - [ ] Dark-Theme-Options
  - [ ] Add candlestick series, add markers
- [ ] Task 4: Empty-State (AC: 4)
  - [ ] Wenn chart_data.candles leer → Placeholder-HTML mit --text-muted
  - [ ] "Chart-Daten nicht verfuegbar"
- [ ] Task 5: Chart-Initialisierung on HTMX-Swap
  - [ ] HTMX `hx-on::after-swap` event → initialize chart
  - [ ] Oder Alpine.js Component mit x-init

## Dev Notes

**lightweight-charts (Locked Decision, 2026-04-12):**
- TradingView Open-Source Library, Apache 2.0 License
- Nur 35KB gzipped, kein externes TradingView Widget
- Keine externe Abhaengigkeit zu CDN — lokale Vendor-Copy
- Ersetzt urspruenglich geplanten Screenshot-Upload (FR13c pivot)

**Dark-Cockpit-Theme fuer Chart:**
```javascript
const chart = LightweightCharts.createChart(container, {
  layout: {
    background: { color: '#0d1117' },
    textColor: '#c9d1d9',
  },
  grid: {
    vertLines: { color: '#21262d' },
    horzLines: { color: '#21262d' },
  },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  timeScale: { timeVisible: true, secondsVisible: false },
});

const candlestickSeries = chart.addCandlestickSeries({
  upColor: '#3fb950',
  downColor: '#f85149',
  borderVisible: false,
  wickUpColor: '#3fb950',
  wickDownColor: '#f85149',
});

candlestickSeries.setData(chartData.candles);
candlestickSeries.setMarkers(chartData.markers);
```

**Chart-Container-Dimensionen:**
- Width: 100% (responsive bis max-width Trade-Drilldown)
- Height: 400px (fix fuer konsistenten Look)
- Padding um Trade-Zeitraum: ±15% der Trade-Dauer fuer Kontext

**Indikatoren (optional, Phase 1):**
- SMA(20), EMA(9) koennen in Story-Scope sein — aber nicht zwingend
- Kommen aus den OHLC-Daten (server-side berechnet oder client-side)

**File Structure:**
```
app/
├── static/
│   └── js/
│       └── vendor/
│           └── lightweight-charts.standalone.production.js  # NEW (35KB)
├── routers/
│   └── trades.py                    # UPDATE - /chart_data endpoint
└── templates/
    └── fragments/
        └── trade_detail.html        # UPDATE - chart container
```

### References

- PRD: FR13c (lightweight-charts Locked Decision 2026-04-12)
- UX-Spec: UX-DR55 (Empty-State)
- Architecture: "Chart-Rendering" Locked Decision
- Dependency: Story 4.3 (ohlc_candles Cache), Story 2.4 (Drilldown)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
