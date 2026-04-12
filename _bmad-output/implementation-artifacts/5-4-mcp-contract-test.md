# Story 5.4: Taeglicher MCP-Contract-Test

Status: ready-for-dev

## Story

As a Chef,
I want daily verification that the MCP API contract hasn't changed,
so that I'm warned early about breaking changes in the fundamental server.

## Acceptance Criteria

1. **Given** der Contract-Snapshot aus Woche 0 existiert, **When** der taegliche Contract-Test laeuft, **Then** vergleicht er die aktuelle Tool-Schema-Liste gegen den Snapshot (FR24)
2. **Given** ein Drift wird erkannt, **When** der Test abgeschlossen ist, **Then** erscheint ein UI-Warning-Banner innerhalb von 24h ohne den Trade-Flow zu blockieren (FR24, NFR-R4)
3. **Given** der Contract-Test, **When** das Ergebnis PASS ist, **Then** wird das Ergebnis im Health-Widget angezeigt mit Timestamp
4. **Given** der MCP-Server ist nicht erreichbar fuer den Test, **When** der Test ausgefuehrt wird, **Then** wird der Fehler geloggt und beim naechsten Lauf erneut versucht (keine Silent Failure)

## Tasks / Subtasks

- [ ] Task 1: Migration 007_mcp_contract_test_results.sql
  - [ ] Tabelle `mcp_contract_tests`: id, run_at, status (pass/fail/error), drift_details JSONB, snapshot_version TEXT
- [ ] Task 2: Contract-Test-Service (AC: 1, 4)
  - [ ] `app/services/mcp_contract_test.py`
  - [ ] Load current Tools via MCP
  - [ ] Compare gegen Snapshot-JSON aus `data/mcp-snapshots/week0-*.json`
  - [ ] Diff: added, removed, changed tools
- [ ] Task 3: APScheduler-Job (AC: 1, 2)
  - [ ] Taeglicher Job um 05:00 UTC
  - [ ] `app/jobs/mcp_contract_test.py`
  - [ ] Schreibt Ergebnis in mcp_contract_tests-Tabelle
- [ ] Task 4: Drift-Banner im UI (AC: 2)
  - [ ] base.html zeigt Banner wenn letzter Test FAIL
  - [ ] Nicht-blockierend (Banner, kein Modal)
- [ ] Task 5: Health-Widget-Integration (AC: 3)
  - [ ] Health-Widget (aus Story 12.2) zeigt: last_contract_test, status
- [ ] Task 6: Tests
  - [ ] Mock: MCP liefert zusaetzliches Tool → FAIL mit Diff
  - [ ] Mock: MCP nicht erreichbar → ERROR-Status
  - [ ] Mock: Identisch zu Snapshot → PASS

## Dev Notes

**Diff-Logic:**
```python
def diff_contracts(snapshot: dict, current: dict) -> dict:
    snap_tools = {t['name'] for t in snapshot['tools']}
    curr_tools = {t['name'] for t in current['tools']}

    return {
        'added': sorted(curr_tools - snap_tools),
        'removed': sorted(snap_tools - curr_tools),
        'changed': [
            name for name in (snap_tools & curr_tools)
            if find_tool(snapshot, name) != find_tool(current, name)
        ],
    }
```

**mcp_contract_tests Schema:**
```sql
CREATE TABLE mcp_contract_tests (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL,  -- 'pass', 'fail', 'error'
    drift_details JSONB,
    snapshot_version TEXT NOT NULL
);
CREATE INDEX idx_mcp_contract_tests_run_at ON mcp_contract_tests(run_at DESC);
```

**Drift-Banner-Pattern:**
```jinja2
{% if latest_contract_test.status == 'fail' %}
  <div role="alert" class="bg-[var(--color-yellow)] text-black p-2">
    ⚠ MCP Contract Drift detected in {{ latest_contract_test.run_at | format_time }}:
    {{ latest_contract_test.drift_details.summary }}
    <a href="/settings#contract-drift">Details ansehen</a>
  </div>
{% endif %}
```

**APScheduler-Job:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

def register_contract_test_job(scheduler, db_pool, mcp_client):
    scheduler.add_job(
        run_contract_test,
        CronTrigger(hour=5, minute=0),
        kwargs={'db_pool': db_pool, 'mcp_client': mcp_client},
        id='mcp_contract_test',
        replace_existing=True,
    )

async def run_contract_test(db_pool, mcp_client):
    try:
        snapshot = load_snapshot()
        current = await mcp_client.list_tools()
        diff = diff_contracts(snapshot, current)
        status = 'pass' if not any(diff.values()) else 'fail'
        await db_pool.execute("""
            INSERT INTO mcp_contract_tests (status, drift_details, snapshot_version)
            VALUES ($1, $2, $3)
        """, status, diff, snapshot['version'])
        logger.info("mcp_contract_test", status=status, diff=diff)
    except Exception as e:
        await db_pool.execute("""
            INSERT INTO mcp_contract_tests (status, drift_details, snapshot_version)
            VALUES ('error', $1, $2)
        """, {'error': str(e)}, 'unknown')
        logger.error("mcp_contract_test_failed", error=str(e))
```

**File Structure:**
```
migrations/
└── 007_mcp_contract_test_results.sql  # NEW
app/
├── services/
│   └── mcp_contract_test.py           # NEW - diff logic
├── jobs/
│   └── mcp_contract_test.py           # NEW - APScheduler job
└── templates/
    └── _drift_banner.html             # NEW (or inline in base.html)
```

### References

- PRD: FR24, NFR-R4, NFR-I5
- Architecture: "Week-0 Critical Deliverables" (Contract-Snapshot Freeze)
- Dependency: Story 1.6 (MCP-Client + Snapshot), Story 12.1 (APScheduler), Story 12.2 (Health-Widget)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
