# Story 9.1: Regime-Snapshot-Datenmodell & Taegliche Erfassung

Status: ready-for-dev

## Story

As a Chef,
I want daily regime snapshots capturing market conditions,
so that I have a historical record of the market environment around my trades.

## Acceptance Criteria

1. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die `regime_snapshots`-Tabelle erstellt mit: id, fear_greed_index, vix, per_broker_pnl (JSONB), created_at (FR41)
2. **Given** der taegliche Scheduled Job, **When** ausgefuehrt, **Then** wird ein Regime-Snapshot erstellt mit aktuellem Fear & Greed Index, VIX-Level und Per-Broker-P&L (FR41)
3. **Given** der Snapshot-Job, **When** er ausfaellt (z.B. Datenquelle nicht erreichbar), **Then** wird der Fehler geloggt und beim naechsten Durchlauf erneut versucht (kein Silent Failure)

## Tasks / Subtasks

- [ ] Task 1: Migration 015_regime_snapshots.sql
  - [ ] Tabelle mit Schema unten
- [ ] Task 2: F&G-Fetcher
  - [ ] `app/services/fear_greed.py` — `fetch_fear_greed()`
  - [ ] Reuse: fundamental/fear-greed-client.ts via MCP-Tool
  - [ ] Fallback: Direct API call zu alternative.me/fng
- [ ] Task 3: VIX-Fetcher
  - [ ] `app/services/vix.py` — `fetch_vix()`
  - [ ] Source: Yahoo Finance oder IB Historical (ib_async)
- [ ] Task 4: Per-Broker-P&L-Calculator
  - [ ] `app/services/broker_pnl.py` — `compute_per_broker_pnl()`
  - [ ] SQL: GROUP BY broker, SUM(pnl) WHERE closed_at between today-30d and now
- [ ] Task 5: Regime-Snapshot-Job
  - [ ] APScheduler Cron: daily at 01:00 UTC
  - [ ] `app/jobs/regime_snapshot.py`
  - [ ] Fail-Logging + Retry beim naechsten Run
- [ ] Task 6: Tests
  - [ ] Mock F&G/VIX Sources
  - [ ] Assert: Snapshot wird erstellt mit allen Feldern
  - [ ] Test: Bei Fehler wird nicht gecrasht, aber geloggt

## Dev Notes

**regime_snapshots Schema:**
```sql
CREATE TABLE regime_snapshots (
    id SERIAL PRIMARY KEY,
    fear_greed_index INT NOT NULL,  -- 0-100
    vix NUMERIC(5, 2) NOT NULL,
    per_broker_pnl JSONB NOT NULL,  -- {"ib": 1234.56, "ctrader": -345.67}
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_regime_snapshots_created_at ON regime_snapshots(created_at DESC);
```

**Data Sources:**
- **Fear & Greed Index**: alternative.me/fng (free, no auth)
- **VIX**: Yahoo Finance `^VIX` via ib_async oder direkte yfinance-Nutzung
- **Per-Broker-P&L**: SQL aggregation aus trades-Tabelle (letzte 30 Tage)

**Per-Broker-P&L-SQL:**
```sql
SELECT
    jsonb_object_agg(broker::text, total_pnl) as per_broker_pnl
FROM (
    SELECT broker, SUM(pnl) as total_pnl
    FROM trades
    WHERE closed_at >= NOW() - INTERVAL '30 days'
    GROUP BY broker
) x;
```

**APScheduler-Registration:**
```python
def register_regime_snapshot_job(scheduler, db_pool):
    scheduler.add_job(
        create_regime_snapshot,
        CronTrigger(hour=1, minute=0),
        kwargs={'db_pool': db_pool},
        id='regime_snapshot',
        replace_existing=True,
    )
```

**File Structure:**
```
migrations/
└── 015_regime_snapshots.sql       # NEW
app/
├── services/
│   ├── fear_greed.py               # NEW
│   ├── vix.py                      # NEW
│   └── broker_pnl.py               # NEW
└── jobs/
    └── regime_snapshot.py          # NEW
```

### References

- PRD: FR41
- Architecture: "Scheduled Jobs"
- Dependency: Story 1.6 (MCP-Client fuer F&G fallback), Story 2.1 (trades fuer P&L), Story 12.1 (Scheduled Jobs Framework)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
