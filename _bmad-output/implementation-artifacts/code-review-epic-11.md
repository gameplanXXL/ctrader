---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: 36ca371
stories_reviewed:
  - 11-1-scheduled-jobs-framework
  - 11-2-health-widget
  - 11-3-daily-postgres-backups
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 1  # D232 IB Flex Nightly descope
  patch_high: 13
  patch_medium: 5
  patch_low: 0
  defer: 18
  dismiss: 0
status: tranche-a-applied
---

# Code Review — Epic 11 (Stories 11.1–11.3)

Adversarial multi-layer review of the System-Health & Scheduled Operations block. Three reviewers surfaced **~58 findings** total — Auditor: 8 ACs MET + 3 partial + 2 NOT MET + 0 deferred; Blind Hunter: 25 diff-based findings with 6 HIGH-severity production safety bugs (credential leak, OOM, race windows, hung jobs); Edge Case Hunter: 23 interaction findings with 8 HIGH (Epic-9 transaction-discipline bypass, Gordon silent-success, AC gaps on top-bar/polling, unwired rotation). Tranche A applies 18 patches (13 HIGH + 5 MEDIUM) plus a Migration 017 for the `cancelled` status vocabulary. **454/454 tests green** (447 pre-existing + 7 new scheduler patches), ruff clean, live smoke probe verified including a `ps aux` check that confirms the password no longer leaks to the process table.

## Chef decision required: D232 — IB Flex Nightly

Story 11.1 AC #2 lists **5** cron jobs; only 4 are registered. `ib_flex_import::import_flex_xml` takes an XML string parameter — it's not self-contained. Three options:
1. **Add a filesystem watcher** that picks up XML drops in `data/ib-flex-inbox/`.
2. **Add an IB Flex Web Service API caller** that downloads the XML directly (requires `ib_flex_token` + `ib_flex_query_id` in `settings`).
3. **Officially descope to Phase 2** and update Story 11.1 AC #2.

Option 2 is the cleanest because Chef already has `IB_FLEX_TOKEN` in his env. The other jobs are wired; IB Flex is the only outstanding cron. **Flagged as D232, not fixed in this Tranche A.**

## Patches Applied — Tranche A (18)

### 🔴 HIGH (13)

- **H1 BH-1 — pg_dump DSN password leak to `ps aux`.** The DSN was passed as a CLI argument, making `postgresql://ctrader:SECRET@...` visible in `/proc/<pid>/cmdline` to every user on the host (NFR-S5 violation). Fix: new `_pg_env_from_dsn()` helper parses the URL into `PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE` env vars; pg_dump gets only `--dbname=ctrader` on argv. Live smoke probe verified via `/proc/<pid>/cmdline` inspection — the new cmdline is `pg_dump --format=plain --no-owner --no-acl --dbname=ctrader` with NO password.

- **H2 BH-2 / EC-9 — OOM via buffered `proc.communicate()`.** The previous version buffered the entire SQL dump into Python memory before the gzip write — a 500 MB DB would push 1 GB RSS plus a second gzip copy. Fix: stream `proc.stdout` in 64KB chunks into `gzip.GzipFile` via `asyncio.to_thread(gz.write, chunk)`. Memory footprint stays flat regardless of dump size.

- **H3 BH-3 / EC-10 — `chmod(0o600)` race window + partial file corruption.** The previous `gzip.open(path, "wb")` created the file with default umask (0o644 = world-readable) until the post-write chmod. On an OOM mid-write, the partial file with default permissions stayed on disk. Fix: `os.open(..., O_WRONLY|O_CREAT|O_EXCL, 0o600)` so the file is 0o600 from the first byte AND writes land in `*.sql.gz.part` with atomic rename only on success. The `get_backup_info` glob only matches `ctrader-*.sql.gz` (no `.part`) so a crashed run leaves an ignored temp file.

- **H4 BH-4 — `logged_job` pool-acquire hang.** Three separate acquires per job fire (insert + job body + update) without timeouts. Under pool exhaustion (concurrent user request + scheduler fire), the update hung forever. Fix: wrap every acquire in `async with asyncio.timeout(10)` so a dead pool fails fast and the wrapper logs a warning instead of deadlocking.

- **H5 BH-5 — `await fn()` had no timeout.** A stuck pg_dump, hung MCP call, or wedged Gordon fetch blocked the APScheduler slot forever; `max_instances=1` then silently dropped every subsequent daily fire. Fix: `async with asyncio.timeout(600)` (10-minute per-job cap) + distinct `TimeoutError` branch that writes `status='failure'` with a `"timeout after 600s"` message.

- **H6 BH-6 — nested failure-update could hang.** The previous version's `except Exception` handler re-acquired the pool without a timeout. If the job failed because the pool was exhausted, the failure update ALSO hung and the `job_executions` row stayed in `running` forever. Fix: new `_update_job_row` helper has its own bounded acquire timeout; failures inside are logged at WARNING and swallowed.

- **H7 EC-1 / EC-2 / EC-3 — Scheduler regime path bypassed Epic-9 transaction discipline.** Epic-9 Tranche A H4 explicitly wrapped the regime snapshot + kill-switch in a single connection + transaction to prevent half-commits. The new scheduler-side `regime_snapshot_job` used TWO separate acquires (`create_regime_snapshot` → its own, then `evaluate_kill_switch` → another). Fix: inlined the scheduler path to mirror `post_regime_snapshot`: single connection + `async with conn.transaction()` around the INSERT, kill-switch eval runs after the transaction so an eval failure doesn't roll back the snapshot itself but still surfaces as a job failure.

- **H8 EC-4 / BH-11 — `rotate_backups` never called.** Defined, unit-tested, completely unwired. Backups would have accumulated forever until the disk filled and pg_dump silently failed. Fix: `db_backup_job` now calls `rotate_backups(keep=7)` after every successful create. Live smoke probe verified.

- **H9 EC-5 / Auditor 11.2 #2 — Top-bar status dots.** `_topbar.html` still had the Week-0 placeholder (`health-dot--muted`) dots. Story 11.2 AC #2 explicitly asks for LIVE integration dots. Fix: new `fragments/topbar_health_dots.html` — a self-contained 3-dot unit with its own `hx-get="/api/health/dots" hx-trigger="load, every 5s" hx-swap="outerHTML"` wrapper. `_topbar.html` `{% include %}`s it; the fragment falls back to muted dots when `health` is not in the rendering context.

- **H10 EC-6 / Auditor 11.2 #3 — 5-second HTMX polling.** The `/api/health` endpoint existed but no template polled it. Fix: new `/api/health/dots` endpoint returns just the 3-dot fragment (<1KB payload) — used by the `load, every 5s` trigger in `topbar_health_dots.html`. The existing `/api/health` still returns the full widget for settings-page rendering.

- **H11 EC-7 — Gordon silent-success.** `fetch_and_persist` returns cleanly even when the MCP call fails (it persists a row with `source_error` — Story 10.1 AC #3 "never drop a day"). The scheduler wrapper then wrote `status='success'` for the Gordon job EVERY Monday despite the weekly backend being permanently broken (D214: `trend_radar` tool doesn't exist on fundamental MCP). Fix: scheduler's `gordon_weekly_job` now explicitly checks `snapshot.source_error` after `fetch_and_persist` and raises `RuntimeError`, so `logged_job` surfaces it as `failure` in the Health-Widget. Chef will now see a red pill every Monday until D214 is resolved.

- **H12 EC-8 — Health-Widget fragment was structurally smaller than settings page.** `health_widget.html` rendered only 3 integration dots + job runs table. `contract_test` and `backup` were rendered INLINE in `settings.html` separately. This meant `/api/health` returned a smaller fragment than what was visible on the settings page — any future HTMX swap would wipe the contract-test + backup sections. Fix: added `contract_test` + `backup` rendering to the fragment (as `health-widget__meta` rows), so `/api/health` is now self-contained.

- **H13 Auditor 11.2 #4 — Audit-Log-Ansicht + Taxonomie-Editor.** Story 11.2 AC #4 lists four settings sections: Health Widget ✓, MCP-Config ✓, Backup Download ✓, AND Taxonomie-Editor + Audit-Log-Ansicht. The latter two were missing. Fix:
  - **Taxonomy** (read-only, Phase-2 edit deferred per Task 6): `settings_page` now passes `taxonomy=get_taxonomy()` into the template. `settings.html` renders each category (Horizons / Trigger-Types / Exit-Reasons / Regime-Tags / Strategy-Categories / Mistake-Tags) as a `<ul>` of `id / label` pairs.
  - **Audit log** (read-only, latest 50): `settings_page` fetches `SELECT ... FROM audit_log ORDER BY created_at DESC LIMIT 50` via the pool and passes as `audit_entries`. `settings.html` renders a simple table (Zeit / Event / Actor / Proposal-or-Strategy / Notiz). Filter + pagination are deferred as **D242** per Task 7 explicit descope.

### 🟡 MEDIUM (5)

- **M1 BH-8 / EC-12 — Stranded `running` rows + `cancelled` status.** On process kill mid-job, the `job_executions` row stayed `running` forever (no startup sweep). AND `CancelledError` during a clean shutdown was written as `status='failure'`, poisoning the Health-Widget with a red pill after every normal restart. Fix:
  - New Migration 017 adds `'cancelled'` to the CHECK vocabulary.
  - New `sweep_stranded_jobs(conn)` function flips every `running` row to `failure` with `error_message='stranded on restart ...'`. Called from `app/main.py` lifespan BEFORE `setup_scheduler` starts.
  - `logged_job`'s `CancelledError` branch now writes `status='cancelled'` via `_UPDATE_CANCELLED_SQL` + `'cancelled on shutdown'` note.

- **M2 BH-10 — Same-day backup overwrite.** Timestamp was `%Y-%m-%d` only, so two backups on the same calendar day clobbered each other. Fix: `%Y-%m-%dTHHMMSSZ` (ISO8601 with UTC time).

- **M3 BH-14 — `pg_dump` stderr silent on success.** Warnings (role mismatch, version hints) were swallowed whenever returncode was 0. Fix: log stderr as `db_backup.pg_dump_stderr` WARNING whenever it's non-empty, regardless of returncode.

- **M4 EC-13 / EC-14 / EC-15 — `docs/recovery.md` step 3 was broken.** The doc told operators to run `psql "$DATABASE_URL" -c "DROP DATABASE ctrader"` — but (a) `@postgres:5432` doesn't resolve from the host shell, (b) PostgreSQL refuses `DROP DATABASE` while connected to the DB being dropped, (c) the `psql -f ...` restore had no `ON_ERROR_STOP=1` so a partial restore was possible. Fix: rewrote the recovery procedure to use `docker compose exec postgres psql -U ctrader -d postgres -c "DROP DATABASE ..."`, added `pg_terminate_backend` pre-flight for stuck connections, and `psql -v ON_ERROR_STOP=1 -f /tmp/restore.sql` for the restore. Added an ⚠ callout explaining ON_ERROR_STOP's criticality.

- **M5 EC-19 — `StubCTraderClient` detection via string match.** `class_name == "StubCTraderClient"` would silently flip the dot from yellow to green if the class was ever renamed. Fix: `isinstance(ctrader_client, StubCTraderClient)` with a local import.

Plus two minor follow-ups: EC-11/BH-23 force-chmod the backup dir on every `_resolve_backup_dir` call (handles bind-mount host-umask case), and new `test_resolve_backup_dir_tightens_preexisting_perms` locks it in.

## Live Smoke-Probe Results

Against Docker Compose stack:

| Probe | Outcome |
|---|---|
| Migration 017 applied | `{"version":"017","event":"migrate.applied"}` |
| Scheduler startup | 4 jobs registered (regime_snapshot, db_backup, mcp_contract_test, gordon_weekly) |
| Stranded sweep | clean on fresh DB |
| `POST /api/health/dots` | returns `<div class="ctrader-health" hx-get="/api/health/dots" hx-trigger="load, every 5s" ...>` with 3 real-state dots |
| `GET /journal` top-bar | includes `hx-get="/api/health/dots"` wrapper — HTMX will poll on load |
| `GET /settings` | Health Widget + MCP Config + Backup section + Taxonomie (6 categories, full read-only list) + Audit Log section (empty state) |
| Backup via scheduler path | **40698 uncompressed bytes → 7056 gzip**, filename `ctrader-2026-04-14T155437Z.sql.gz` with UTC timestamp, `rotate_backups` returned 0 (only one file), atomic rename verified |
| `/proc/<pid>/cmdline` during pg_dump | **`pg_dump --format=plain --no-owner --no-acl --dbname=ctrader`** — NO password visible. Password correctly passed via `PGPASSWORD` env var |

## Deferred (LOW + decisions) — 18 items

All added to `deferred-work.md` as **D232–D249**. Summary:
- **D232 CHEF DECISION**: IB Flex Nightly not wired (AC 11.1 #2 gap)
- **D234–D236**: db_backup robustness (partial-file cleanup, glob sort, pg_dump version probe)
- **D237–D239**: Scheduler robustness (timeout config, APScheduler jobstore persistence, closure invalidation)
- **D240–D243**: Health/observability (fragment size, taxonomy editor Phase 2, audit filter/pagination, sync IO in async health)
- **D244–D245**: Recovery doc polish + NFR-R5 test-recovery reminder
- **D246–D249**: Integration test gaps (setup_scheduler roundtrip, dots endpoint, streaming backup, cleanup on OOM)

## Status

- **Tranche A applied:** 18 patches (13 HIGH + 5 MEDIUM) + Migration 017
- **Tests:** 454/454 green (447 pre-existing + 7 new scheduler + 0 regressions)
- **Ruff:** clean
- **Smoke probe:** end-to-end verified — scheduler startup, password-not-in-cmdline, streaming backup with rotate, settings page with all 5 sections, top-bar HTMX polling wired
- **Deferred:** D232–D249 in deferred-work.md
- **Ready for:** Epic 12 (IB Swing-Order) Yolo-mode, with one prerequisite — Chef decides on D232 (IB Flex Nightly cron: build, scrape, or descope)
