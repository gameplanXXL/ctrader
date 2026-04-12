# Story 6.3: Strategy-Detailansicht & Expectancy-Analyse

Status: ready-for-dev

## Story

As a Chef,
I want a detailed strategy view with expectancy curves and trade breakdown,
so that I can evaluate strategy effectiveness over time and against AI recommendations.

## Acceptance Criteria

1. **Given** eine Strategie im Detail, **When** angezeigt, **Then** zeigt die rechte Pane: Hero-Aggregation-Block (Expectancy, Winrate, Drawdown, Trade Count), darunter die vollstaendige Trade-Liste dieser Strategie (FR36)
2. **Given** die Strategy-Detailansicht, **When** die Expectancy-Kurve angezeigt wird, **Then** zeigt sie den Expectancy-Verlauf ueber Zeit als Chart (FR36)
3. **Given** die Strategy-Detailansicht, **When** der Gefolgt-vs-Ueberstimmt-Breakdown angezeigt wird, **Then** zeigt er die Performance-Aufteilung: Trades wo Chef dem Agent folgte vs. wo er ueberstimmte (FR36)
4. **Given** die Strategies-Seite, **When** Expectancy pro Horizon angezeigt wird, **Then** werden Aggregationen ueber alle Strategien pro Horizon (intraday/swing/position) sichtbar (FR40)

## Tasks / Subtasks

- [ ] Task 1: Strategy-Detail-Query (AC: 1)
  - [ ] `app/services/strategy_detail.py` — `get_strategy_detail(strategy_id)`
  - [ ] JOIN strategies + trades WHERE strategy_id = X
  - [ ] Reuse aggregation-service aus Story 4.2
- [ ] Task 2: Expectancy-Zeitreihe (AC: 2)
  - [ ] `get_expectancy_timeseries(strategy_id)` → [(date, cumulative_expectancy)]
  - [ ] Rollender Durchschnitt oder cumulative
- [ ] Task 3: Expectancy-Kurve rendern (AC: 2)
  - [ ] lightweight-charts als Line-Chart (aus Story 4.5)
  - [ ] Oder einfacher: Server-side SVG (sparkline-aehnlich, groesser)
- [ ] Task 4: Followed-vs-Override-Breakdown (AC: 3)
  - [ ] SQL: GROUP BY trigger_spec->>'followed'
  - [ ] Anzeige: 2 Stat-Cards (Followed-Expectancy | Override-Expectancy)
- [ ] Task 5: Horizon-Aggregation (AC: 4)
  - [ ] `app/services/strategy_metrics.py` — `get_horizon_aggregation()`
  - [ ] Gruppiert ueber alle Strategien nach horizon
  - [ ] Anzeige im Footer der Strategies-Liste oder dedizierter Section
- [ ] Task 6: Strategy-Detail-Template (AC: 1)
  - [ ] `app/templates/fragments/strategy_detail.html`
  - [ ] Hero-Block + Expectancy-Kurve + Followed-vs-Override + Trade-Liste

## Dev Notes

**Expectancy-Timeseries-SQL:**
```sql
SELECT
    DATE(closed_at) as date,
    AVG(r_multiple) OVER (ORDER BY closed_at ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as rolling_expectancy
FROM trades
WHERE strategy_id = $1 AND closed_at IS NOT NULL
ORDER BY closed_at;
```

**Followed-vs-Override-SQL:**
```sql
SELECT
    (trigger_spec->>'followed')::bool as followed,
    COUNT(*) as trade_count,
    AVG(r_multiple) as expectancy,
    SUM(pnl) as total_pnl
FROM trades
WHERE strategy_id = $1
  AND trigger_spec IS NOT NULL
GROUP BY followed;
```

**Horizon-Aggregation-SQL (FR40):**
```sql
SELECT
    s.horizon,
    COUNT(t.id) as trade_count,
    AVG(r_multiple) as expectancy,
    MIN(cum_r) as drawdown
FROM strategies s
JOIN trades t ON t.strategy_id = s.id
WHERE t.closed_at IS NOT NULL
GROUP BY s.horizon
ORDER BY s.horizon;
```

**Strategy-Detail-Layout:**
```
┌─ Mean Reversion Crypto ─────────────────────────┐
│                                                  │
│ ┌─ Metrics ─────────────────────────────────┐   │
│ │ TRADES  EXPECTANCY  WINRATE  DRAWDOWN    │   │
│ │  234     +0.23R      58%     -1.2R       │   │
│ └───────────────────────────────────────────┘   │
│                                                  │
│ ┌─ Expectancy Over Time ────────────────────┐   │
│ │   ^                                        │   │
│ │   | ╱╲╱╲__╱╲                               │   │
│ │   └──────────────>                         │   │
│ └───────────────────────────────────────────┘   │
│                                                  │
│ ┌─ Followed vs Override ────────────────────┐   │
│ │ Followed:   180 trades  +0.31R           │   │
│ │ Override:    54 trades  -0.02R           │   │
│ └───────────────────────────────────────────┘   │
│                                                  │
│ ┌─ Trades (234) ────────────────────────────┐   │
│ │ [Trade List with facet filter]            │   │
│ └───────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

**File Structure:**
```
app/
├── services/
│   ├── strategy_detail.py        # NEW
│   └── strategy_metrics.py       # UPDATE - horizon_aggregation
└── templates/
    └── fragments/
        └── strategy_detail.html  # NEW
```

### References

- PRD: FR36, FR40
- UX-Spec: UX-DR26 (Two-Pane)
- Dependency: Story 6.1 (strategies), Story 6.2 (List), Story 4.2 (Aggregation), Story 4.5 (Charts)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
