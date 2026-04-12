# Story 10.1: Gordon-Weekly-Fetch & Snapshot-Speicherung

Status: ready-for-dev

## Story

As a Chef,
I want weekly Gordon trend radar data fetched automatically,
so that I start each trading week with current market intelligence.

## Acceptance Criteria

1. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die `gordon_snapshots`-Tabelle erstellt mit: id, snapshot_data (JSONB), hot_picks (JSONB), created_at
2. **Given** Montag morgen (06:00 UTC), **When** der Gordon-Weekly-Job laeuft, **Then** wird der aktuelle Trend-Radar via MCP (Gordon-Agent) abgerufen und als Snapshot gespeichert (FR46, NFR-I4)
3. **Given** der Gordon-Job, **When** der MCP-Call fehlschlaegt, **Then** wird der Fehler geloggt und eine Staleness-Warnung im UI angezeigt

## Tasks / Subtasks

- [ ] Task 1: Migration 017_gordon_snapshots.sql
- [ ] Task 2: Gordon-Service
  - [ ] `app/services/gordon.py` — `fetch_gordon_trend_radar()`
  - [ ] MCP-Call mit tool="trend_radar", agent="gordon"
- [ ] Task 3: Job
  - [ ] `app/jobs/gordon_weekly.py`
  - [ ] APScheduler Cron: `day_of_week='mon', hour=6, minute=0, timezone='UTC'`
- [ ] Task 4: Snapshot-Speicherung
  - [ ] INSERT gordon_snapshots (snapshot_data, hot_picks)
- [ ] Task 5: Staleness-Tracking
  - [ ] Latest snapshot-Age anzeigen im UI (Story 10.2)
  - [ ] Warning wenn > 7 Tage alt

## Dev Notes

**gordon_snapshots Schema:**
```sql
CREATE TABLE gordon_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_data JSONB NOT NULL,  -- Full MCP response
    hot_picks JSONB NOT NULL,       -- Extracted array of HOT picks
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_gordon_snapshots_created_at ON gordon_snapshots(created_at DESC);
```

**hot_picks JSONB-Format (aus fundamental/Gordon):**
```json
[
  {
    "symbol": "NVDA",
    "rank": 1,
    "horizon": "swing",
    "confidence": 0.85,
    "thesis": "AI-Nachfrage weiter stark, Quartalszahlen voraus",
    "entry_zone": [890, 920],
    "target": 1050
  },
  {
    "symbol": "BTCUSD",
    "rank": 2,
    ...
  }
]
```

**APScheduler-Cron (NFR-I4):**
```python
scheduler.add_job(
    gordon_weekly_job,
    CronTrigger(day_of_week='mon', hour=6, minute=0, timezone='UTC'),
    id='gordon_weekly',
)
```

**Success-Rate (NFR-I4):**
> "Woechentlicher Gordon-Trend-Loop (Montag 06:00 UTC) mit 8/8 Wochen Erfolgsrate im MVP"

Monitoring: job_executions-Tabelle aus Story 12.1 trackt Erfolg/Misserfolg jeder Ausfuehrung.

**File Structure:**
```
migrations/
└── 017_gordon_snapshots.sql       # NEW
app/
├── services/
│   └── gordon.py                   # NEW
└── jobs/
    └── gordon_weekly.py            # NEW
```

### References

- PRD: FR46, NFR-I4
- Dependency: Story 1.6 (MCP-Client), Story 12.1 (APScheduler + job_executions)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
