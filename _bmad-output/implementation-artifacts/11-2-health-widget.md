# Story 11.2: Health-Widget & System-Status-Anzeige

Status: ready-for-dev

<!-- Renumbered 2026-04-14 from 12.2 → 11.2 per PM-scope-update (Epic 11 ↔ 12 swap, Chef request). Content unchanged. -->


## Story

As a Chef,
I want a health dashboard showing system status at a glance,
so that I can quickly verify all integrations and background processes are working.

## Acceptance Criteria

1. **Given** die Settings-Seite oder den Health-Bereich, **When** geladen, **Then** zeigt das Health-Widget: IB-Verbindungsstatus (Dot: green/yellow/red), cTrader-Verbindungsstatus (Dot), MCP-Status (Dot), Zeitstempel der letzten erfolgreichen Ausfuehrung jedes Scheduled Jobs, aktuelles MCP-Contract-Test-Ergebnis (FR50, UX-DR79)
2. **Given** die Health-Status-Dots im Top-Bar, **When** mit Hover inspiziert, **Then** zeigt ein Tooltip "Statusname: Statusmeldung" (UX-DR79)
3. **Given** das Health-Widget, **When** aktualisiert, **Then** zeigt es Daten mit <= 5s Refresh-Latenz (NFR-M3)
4. **Given** die Settings-Seite, **When** geladen, **Then** zeigt sie ausserdem: Taxonomie-Editor, MCP-Konfigurations-Uebersicht, Audit-Log-Ansicht, DB-Backup-Download-Link (UX-DR80)

## Tasks / Subtasks

- [ ] Task 1: Health-Check-Service
  - [ ] `app/services/health.py`
  - [ ] `check_ib_status()` — check ib_async connection
  - [ ] `check_ctrader_status()` — check OpenApiPy connection
  - [ ] `check_mcp_status()` — reuse Story 5.3 mcp_health
  - [ ] `get_last_job_runs()` — query job_executions-Tabelle
- [ ] Task 2: Health-Widget Template
  - [ ] `app/templates/fragments/health_widget.html`
  - [ ] Dots + Text-Status
  - [ ] Job-Timestamps
  - [ ] Contract-Test-Ergebnis
- [ ] Task 3: Top-Bar Status-Dots (AC: 2)
  - [ ] Story 1.5 Top-Bar Update
  - [ ] 3 Dots: IB, cTrader, MCP
  - [ ] Hover-Tooltip via `title="..."` Attribut
- [ ] Task 4: Settings-Page (AC: 4)
  - [ ] `app/templates/pages/settings.html` (ersetzt placeholder)
  - [ ] Sections: Health, Taxonomy-Editor, MCP-Config, Audit-Log-View, DB-Backup-Download
- [ ] Task 5: Refresh-Mechanismus (AC: 3)
  - [ ] HTMX `hx-get="/api/health" hx-trigger="every 5s"`
  - [ ] Nur fuer Top-Bar-Dots (Settings-Widget on-demand)
- [ ] Task 6: Taxonomie-Editor (AC: 4)
  - [ ] Read-only Anzeige der taxonomy.yaml Eintraege
  - [ ] Edit-Phase 2 (nur Preview in MVP)
- [ ] Task 7: Audit-Log-Ansicht (AC: 4)
  - [ ] Read-only Liste der audit_log Eintraege
  - [ ] Filter by event_type
  - [ ] Pagination

## Dev Notes

**Health-Widget-Layout:**
```
┌─ SYSTEM HEALTH ──────────────────────────────────┐
│                                                    │
│  IB         cTrader      MCP         Contract     │
│  ● OK       ● OK         🟡 Stale    ✓ PASS      │
│  connected  connected    15min ago   2026-04-12   │
│                                                    │
│  Last Jobs:                                        │
│   IB Flex Nightly        2026-04-12 02:00  ✓     │
│   Regime Snapshot        2026-04-12 01:00  ✓     │
│   Gordon Weekly          2026-04-08 06:00  ✓     │
│   MCP Contract Test      2026-04-12 05:00  ✓     │
│   DB Backup              2026-04-12 04:00  ✓     │
└────────────────────────────────────────────────────┘
```

**Top-Bar-Dots-Pattern:**
```html
<div class="flex gap-2 ml-auto">
  <span title="IB: connected" class="status-dot bg-[var(--color-green)]"></span>
  <span title="cTrader: connected" class="status-dot bg-[var(--color-green)]"></span>
  <span title="MCP: stale (15min)" class="status-dot bg-[var(--color-yellow)]"></span>
</div>
```

**Health-API-Endpoint:**
```python
@router.get("/api/health")
async def get_health(db_pool, ib_client, ctrader_client, mcp_client):
    return {
        'ib': await check_ib_status(ib_client),
        'ctrader': await check_ctrader_status(ctrader_client),
        'mcp': await check_mcp_status(mcp_client),
        'last_jobs': await get_last_job_runs(db_pool),
        'contract_test': await get_latest_contract_test(db_pool),
    }
```

**Settings-Page Sections:**
1. **Health Widget** (embed from fragment)
2. **Taxonomie-Editor** (read-only, maybe edit Phase 2)
3. **MCP Configuration** (URL, connection status)
4. **Audit Log** (filterable list)
5. **Database Backup** (download link, last backup timestamp)

**File Structure:**
```
app/
├── services/
│   └── health.py                # NEW
├── routers/
│   ├── api.py                   # UPDATE - /api/health
│   └── pages.py                 # UPDATE - /settings
└── templates/
    ├── fragments/
    │   └── health_widget.html   # NEW
    ├── pages/
    │   └── settings.html        # UPDATE
    └── _topbar.html             # UPDATE - dots
```

### References

- PRD: FR50, NFR-M3
- UX-Spec: UX-DR79 (Health-Indicator), UX-DR80 (Settings-Layout)
- Dependency: Story 1.5 (Top-Bar), Story 5.3 (MCP Health), Story 12.1 (Job-Executions), Story 5.4 (Contract-Test)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
