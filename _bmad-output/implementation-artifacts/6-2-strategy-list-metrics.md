# Story 6.2: Strategy-Liste mit Metriken & Gruppierung

Status: ready-for-dev

## Story

As a Chef,
I want a strategy list with aggregated performance metrics,
so that I can compare strategies at a glance and identify winners and losers.

## Acceptance Criteria

1. **Given** die Strategies-Seite, **When** geladen, **Then** zeigt die linke Pane (320px) eine Liste aller Strategien mit: Anzahl Trades (total + diese Woche), Expectancy, R-Multiple-Verteilung, Drawdown, aktueller Status-Badge (FR34, UX-DR26)
2. **Given** die Strategy-Liste, **When** der Horizon-Grouping-Toggle aktiviert wird, **Then** werden Strategien nach Horizon gruppiert (intraday / swing / position) (FR35)
3. **Given** die Strategy-Liste, **When** ein Spalten-Header geklickt wird, **Then** wird nach dieser Metrik sortiert (FR35)
4. **Given** den Zwei-Pane-Split, **When** eine Strategie in der Liste geklickt wird, **Then** zeigt die rechte Pane (min 800px) die Strategie-Detailansicht (UX-DR26)

## Tasks / Subtasks

- [ ] Task 1: Strategy-Metrics-Service (AC: 1)
  - [ ] `app/services/strategy_metrics.py`
  - [ ] Query: JOIN strategies + trades, GROUP BY strategy_id
  - [ ] Metriken: trade_count, trade_count_week, expectancy, drawdown
- [ ] Task 2: Zwei-Pane-Layout (AC: 4)
  - [ ] `app/templates/pages/strategies.html`
  - [ ] Linke Pane 320px fix, rechte Pane flex min-800px
  - [ ] HTMX: Click in Liste → Detail-Fragment in rechte Pane
- [ ] Task 3: Strategy-List-Fragment (AC: 1, 2, 3)
  - [ ] `app/templates/fragments/strategy_list.html`
  - [ ] Tabelle mit Sort-Headers
  - [ ] Group-Toggle (Checkbox): Horizon-Grouping
- [ ] Task 4: Sortierung (AC: 3)
  - [ ] URL-Param `?sort=expectancy&order=desc`
  - [ ] HTMX auf Column-Header
- [ ] Task 5: Horizon-Grouping (AC: 2)
  - [ ] Wenn grouping aktiv, SQL: ORDER BY horizon, expectancy DESC
  - [ ] Jinja2 groupby filter in Template
- [ ] Task 6: Performance-Check (NFR-P1 Vergleichbar)
  - [ ] Liste laden <= 1.5s bei typischer Anzahl (10–50 Strategien, 2000 Trades)

## Dev Notes

**Strategy-Metrics SQL:**
```sql
SELECT
    s.id,
    s.name,
    s.horizon,
    s.status,
    COUNT(t.id) as trade_count,
    COUNT(t.id) FILTER (WHERE t.opened_at >= NOW() - INTERVAL '7 days') as trade_count_week,
    AVG(r_multiple_calc(t)) as expectancy,
    MIN(cumulative_r_multiple(t)) as drawdown
FROM strategies s
LEFT JOIN trades t ON t.strategy_id = s.id
GROUP BY s.id, s.name, s.horizon, s.status
ORDER BY
    {% if group_by_horizon %}s.horizon,{% endif %}
    {{ sort_column }} {{ sort_order }};
```

**Zwei-Pane-Layout:**
```html
<div class="flex gap-4 h-[calc(100vh-56px)]">
  <aside class="w-[320px] flex-shrink-0 overflow-y-auto border-r border-[var(--bg-surface)]">
    {% include "fragments/strategy_list.html" %}
  </aside>
  <main id="strategy-detail" class="flex-1 overflow-y-auto min-w-[800px]">
    {% if selected_strategy %}
      {% include "fragments/strategy_detail.html" %}
    {% else %}
      <div class="p-8 text-[var(--text-muted)]">Strategy waehlen...</div>
    {% endif %}
  </main>
</div>
```

**Strategy-List-Row:**
```
Name              Horizon    Trades  Week  Exp    DD     Status
─────────────────────────────────────────────────────────────
Mean Reversion    swing      234    12    +0.23  -1.2R  ● active
Momentum Crypto   intraday   156    8     +0.45  -0.8R  ● active
News Breakout     intraday   42     0     -0.12  -2.1R  ● paused
```

**Horizon-Grouping-Ansicht:**
```
▼ INTRADAY (3 Strategien)
  Momentum Crypto   ...
  News Breakout     ...
  Scalping Setup    ...

▼ SWING (2 Strategien)
  Mean Reversion    ...
  Multi-Day Trend   ...

▼ POSITION (1 Strategie)
  Long-term Growth  ...
```

**File Structure:**
```
app/
├── services/
│   └── strategy_metrics.py       # NEW
├── routers/
│   └── strategies.py             # UPDATE - list + metrics
└── templates/
    ├── pages/
    │   └── strategies.html       # UPDATE (replaces placeholder)
    └── fragments/
        └── strategy_list.html    # NEW
```

### References

- PRD: FR34, FR35
- UX-Spec: UX-DR26 (Two-Pane Layout)
- Dependency: Story 6.1 (strategies-Tabelle + strategy_id in trades), Story 4.2 (aggregation helpers)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
