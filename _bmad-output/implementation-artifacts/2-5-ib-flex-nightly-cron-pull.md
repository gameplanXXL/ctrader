# Story 2.5: IB Flex Nightly Cron + CLI-Pull-Flag

Status: review

## Story

As a Chef,
I want the IB Flex Query to pull and import automatically every morning (and to be triggerable on-demand for initial backfill),
so that my historical and daily IB trades appear in ctrader without manual XML-Uploads — und verpasste Tage werden automatisch nachgeholt.

## Kontext (Warum diese Story existiert)

Der IB-Flex-Import läuft heute **nur manuell** via `python -m app.cli.ib_flex_import <xml-file>`. Der Downloader-Client (`download_flex_xml`) und der Reconciliation-Orchestrator (`run_nightly_reconcile`) **existieren bereits** in `app/services/ib_reconcile.py:61-267` — aus Story 2.2. Auch die Config-Settings (`ib_flex_token`, `ib_flex_query_id`) sind in `app/config.py:95-102` vorbereitet. Was fehlt: die **Verdrahtung im APScheduler** (Story 11.1 hat diesen Job bewusst als `D232` offen gelassen, weil die Cron-Konfiguration eine Chef-Entscheidung brauchte).

**Chef-Entscheidung D232 (2026-04-21):**
- **Cron-Slot:** täglich 07:00 UTC (nach NYSE-Close)
- **Window-Strategie:** Sliding-Window — Chef konfiguriert in IB Account Management genau **eine** Activity Flex Query mit Period `Last 90 Days`. Ein einziger erfolgreicher Run deckt damit bis zu 90 Tage Ausfall ab. Idempotenz über `UNIQUE(broker, perm_id)` macht Re-Imports zu No-Ops — kein Gap-Tracking, keine Replay-Logik nötig.
- **Backfill-Pfad:** Für den initialen 12-Monats-Import setzt Chef die Query in IB temporär auf `Last 365 Days` und triggert einmalig via neuem CLI-Flag `--pull`, dann zurück auf `Last 90 Days`.

## Acceptance Criteria

1. **Given** `IB_FLEX_TOKEN` und `IB_FLEX_QUERY_ID` sind in `.env` gesetzt, **When** `setup_scheduler()` aufgerufen wird, **Then** ist ein Job mit ID `ib_flex_nightly` und `CronTrigger(hour=7, minute=0)` (UTC, APScheduler-Default-TZ) registriert (FR49, D232)

2. **Given** der Job `ib_flex_nightly` feuert, **When** der Job-Body läuft, **Then** wird `run_nightly_reconcile(conn, token, query_id)` aus `app/services/ib_reconcile.py` aufgerufen und das Ergebnis (`counts`-Dict) als strukturiertes `logger.info("ib_flex_nightly.ok", ...)` geloggt; neue Trades landen über den bestehenden Upsert-Pfad in der `trades`-Tabelle (FR1, FR2, FR4)

3. **Given** `run_nightly_reconcile()` gibt `None` zurück (Download-Failure), **When** der Job-Body das erkennt, **Then** raised er `RuntimeError("ib_flex_nightly: download failed — see ib_flex_download.* warnings")`, damit der `logged_job`-Wrapper die `job_executions`-Zeile auf `status='failure'` setzt (Pattern analog zu `gordon_weekly_job`, `app/services/scheduler.py:293-299`)

4. **Given** `IB_FLEX_TOKEN` ODER `IB_FLEX_QUERY_ID` ist **nicht** gesetzt (None/leer), **When** `setup_scheduler()` läuft, **Then** wird der Job **nicht** registriert und ein `logger.info("ib_flex_nightly.disabled_unconfigured")` geschrieben; die übrigen vier Jobs registrieren sich unverändert (Graceful Degradation — analog zu `ctrader_host` / `mcp_fundamental_url`)

5. **Given** `python -m app.cli.ib_flex_import --pull`, **When** Token + Query-ID konfiguriert sind und der Download erfolgreich ist, **Then** wird die XML via `download_flex_xml()` geholt und via `import_flex_xml(conn, xml_text)` in die DB importiert; Exit-Code `0`; Summary-Log wie beim File-Import

6. **Given** `python -m app.cli.ib_flex_import --pull` **ohne** konfigurierten `IB_FLEX_TOKEN` oder `IB_FLEX_QUERY_ID`, **When** ausgeführt, **Then** Exit-Code `4`, stderr enthält `"IB_FLEX_TOKEN and IB_FLEX_QUERY_ID must be set in .env"`; keine DB-Verbindung wird geöffnet

7. **Given** `python -m app.cli.ib_flex_import --pull` mit konfigurierten Secrets, **When** `download_flex_xml()` `None` zurückgibt, **Then** Exit-Code `3`, stderr enthält `"Flex download failed — see logs"`

8. **Given** `python -m app.cli.ib_flex_import --pull /pfad/zur/xml` (beide Modi gleichzeitig angegeben), **When** ausgeführt, **Then** Exit-Code `2` mit argparse-Fehlermeldung (`--pull` und XML-File sind mutually exclusive)

9. **Given** der Job `ib_flex_nightly` ist in `JOB_NAMES` eingetragen, **When** das Health-Widget rendert (`GET /fragments/health_widget`), **Then** erscheint die Zeile `IB Flex Nightly` mit aktuellem Status (`success` / `failure` / `cancelled` / `never_run`) und Zeitstempel der letzten Ausführung — **ohne** zusätzlichen Template- oder Service-Code (rein Daten-getrieben über `get_last_job_runs`, `app/services/scheduler.py:375-412`)

10. **Given** der tägliche Cron-Run fällt einmal aus (App nicht gelaufen, Netzproblem, Flex-Service down), **When** der nächste erfolgreiche Run feuert mit einer in IB als `Last 90 Days` konfigurierten Query, **Then** werden alle verpassten Tage automatisch nachimportiert ohne Duplikate (Lückenschluss-Garantie durch Sliding-Window × Idempotenz — testbar durch Seed von Teil-Daten + zweiten Import-Run ohne erneute Duplikate)

## Tasks / Subtasks

> **WIEDERVERWENDUNGS-HINWEIS (NICHT IGNORIEREN):**
>
> - `download_flex_xml()` **existiert** in `app/services/ib_reconcile.py:61-138` — **NICHT** neu implementieren
> - `run_nightly_reconcile()` **existiert** in `app/services/ib_reconcile.py:250-267` — Orchestrator, ruft Downloader + Reconciler
> - `import_flex_xml()` **existiert** in `app/services/ib_flex_import.py` — XML-Upsert-Pfad, liefert `ImportResult`
> - `_extract_xml_value()`, `FLEX_REQUEST_URL`, `FLEX_DOWNLOAD_URL`, `POLL_INTERVAL_SECONDS`, `MAX_POLL_ATTEMPTS`, ErrorCode-Handling (1019 = "Statement generation in progress") sind alle in `ib_reconcile.py` gelöst
>
> Diese Story ist **reine Verdrahtung** — geschätzter Netto-Diff: 80–120 LOC Produktions-Code + Tests.

---

- [x] **Task 1: Scheduler-Job `ib_flex_nightly`** (AC: 1, 2, 3, 4)
  - [x] 1.1 `JOB_NAMES` in `app/services/scheduler.py:89` um `"ib_flex_nightly": "IB Flex Nightly"` erweitern
  - [x] 1.2 Neuen Job-Body `ib_flex_nightly_job()` in `setup_scheduler()` anlegen (Pattern aus `gordon_weekly_job`, `scheduler.py:293-299`):
    ```python
    async def ib_flex_nightly_job() -> None:
        async with db_pool.acquire() as conn:
            counts = await run_nightly_reconcile(
                conn,
                settings.ib_flex_token,
                settings.ib_flex_query_id,
            )
        if counts is None:
            raise RuntimeError(
                "ib_flex_nightly: download failed — see ib_flex_download.* warnings"
            )
        logger.info("ib_flex_nightly.ok", **counts)
    ```
  - [x] 1.3 **Conditional registration** — Job nur anhängen, wenn `settings.ib_flex_token and settings.ib_flex_query_id`:
    ```python
    if settings.ib_flex_token and settings.ib_flex_query_id:
        scheduler.add_job(
            logged_job("ib_flex_nightly", ib_flex_nightly_job, db_pool),
            CronTrigger(hour=7, minute=0),
            id="ib_flex_nightly",
            replace_existing=True,
        )
    else:
        logger.info("ib_flex_nightly.disabled_unconfigured")
    ```
  - [x] 1.4 Import-Statement in `setup_scheduler()` ergänzen: `from app.services.ib_reconcile import run_nightly_reconcile`
  - [x] 1.5 Import `settings` — bereits verfügbar via `from app.config import settings` (NICHT doppelt importieren)

- [x] **Task 2: CLI-Flag `--pull`** (AC: 5, 6, 7, 8)
  - [x] 2.1 `app/cli/ib_flex_import.py`: `argparse` erweitern — mutually exclusive Group:
    ```python
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("xml_file", nargs="?", type=Path, ...)
    group.add_argument("--pull", action="store_true", help="Download via IB Flex Web Service")
    ```
    (argparse gibt Exit-Code 2 automatisch bei konflikt-Args — das deckt AC 8 ab)
  - [x] 2.2 In `_run()` Pfad unterscheiden:
    - Wenn `args.pull`: `settings.ib_flex_token`/`ib_flex_query_id` Check → sonst `print("IB_FLEX_TOKEN and IB_FLEX_QUERY_ID must be set in .env", file=sys.stderr); return 4`
    - Dann `xml_text = await download_flex_xml(token, query_id)` → `if xml_text is None: return 3` mit stderr
    - Dann `result = await import_flex_xml(conn, xml_text)` (existiert in `ib_flex_import.py`)
  - [x] 2.3 Wenn File-Modus: bestehender Code-Pfad bleibt unverändert
  - [x] 2.4 Exit-Codes am Dateianfang als Docstring dokumentieren (0/2/3/4)

- [x] **Task 3: `.env.example` aktualisieren** (AC: 1, 4)
  - [x] 3.1 Kommentarblock ergänzen, dass Token + Query-ID Pflicht sind, wenn der Nightly-Job laufen soll; explizit `Last 90 Days` als empfohlene Period-Einstellung der IB-Query erwähnen

- [x] **Task 4: Unit-Tests für Scheduler-Job** (AC: 1, 2, 3, 4)
  - [x] 4.1 Neue Datei `tests/unit/test_scheduler_ib_flex.py`
  - [x] 4.2 Test: `setup_scheduler` mit gesetzten Secrets registriert `ib_flex_nightly` (Assert `scheduler.get_job("ib_flex_nightly") is not None`) + prüft CronTrigger(hour=7)
  - [x] 4.3 Test: `setup_scheduler` ohne `ib_flex_token` → Job nicht registriert, andere 4 Jobs bleiben
  - [x] 4.4 Test: `setup_scheduler` ohne `ib_flex_query_id` → selbes Verhalten wie 4.3
  - [x] 4.5 Test: Job-Body ruft `run_nightly_reconcile` mit korrekten Args (Token + Query-ID aus Settings) — über `job.func()` + Scheduler-Introspection
  - [x] 4.6 Test: Body mit `run_nightly_reconcile` → `None` raised `RuntimeError("download failed ...")` (direkte Body-Rekonstruktion, umgeht den swallowing `logged_job`-Wrapper)

- [x] **Task 5: Unit-Tests für CLI `--pull`** (AC: 5, 6, 7, 8)
  - [x] 5.1 Neue Datei `tests/unit/test_cli_flex_pull.py`
  - [x] 5.2 Test: `--pull` ohne Token → Exit `4`, stderr enthält `IB_FLEX_TOKEN and IB_FLEX_QUERY_ID must be set in .env`
  - [x] 5.3 Test: `--pull` ohne Query-ID → Exit `4`, stderr `must be set in .env`
  - [x] 5.4 Test: `--pull` mit Secrets, mocked `download_flex_xml` → `None` → Exit `3`, stderr `Flex download failed`
  - [x] 5.5 Test: Happy-Path — Download liefert XML → `import_flex_xml` wird mit exakt dieser XML aufgerufen → Exit `0`
  - [x] 5.6 Test: `--pull` UND `xml_file` gleichzeitig → argparse `SystemExit(2)`
  - [x] 5.7 Zusätzlicher Test: Kein Argument → argparse `SystemExit(2)` (required-one)
  - [x] 5.8 Regression-Guard: File-Modus (`xml_file` only) ruft `import_flex_file` unverändert → Exit `0`

- [x] **Task 6: Idempotenz-Integration-Test** (AC: 10)
  - [x] 6.1 Test existiert bereits (`test_reimport_is_idempotent` in `tests/integration/test_flex_import.py:172`) aus Story 2.1 AC 5
  - [x] 6.2 Kommentar über dem Test ergänzt, der die Story-2.5-AC-10-Sliding-Window-Garantie verlinkt — nicht dupliziert

- [x] **Task 7: Full-Suite-Regression** (AC: alle)
  - [x] 7.1 `uv run pytest -m "not integration"` grün: **476 passed, 20 deselected** (integration braucht Live-DB)
  - [x] 7.2 `uv run ruff check .` clean
  - [x] 7.3 mypy nicht im Projekt konfiguriert — skip nach Story-Vorgabe
  - [x] 7.4 Defensive conftest-Fix: `configure_logging` wird in Unit-Tests gestubbt, weil `data/logs/ctrader.log` im Dev-Env nach `make start` von root owned ist und pytest's TestClient-Lifespan daran scheiterte. Stubbing ist defensiv — strukturierte Log-Processors von structlog bleiben unverändert. Netto 25 Tests (`test_pages.py`, `test_tagging_form.py`, `test_trade_detail_unit.py`, `test_debug_route.py`) wieder grün.

## Dev Notes

### Bestehende Codepfade — bitte referenzieren, nicht duplizieren

| Was brauche ich | Wo es ist | Signatur |
|-----------------|-----------|----------|
| Flex-Web-Service Download (2-Schritt + Polling) | `app/services/ib_reconcile.py:61` | `async download_flex_xml(token, query_id, *, client=None, timeout=30.0) -> str \| None` |
| Reconcile-Orchestrator (Download + Reconcile) | `app/services/ib_reconcile.py:250` | `async run_nightly_reconcile(conn, token, query_id) -> dict[str, int] \| None` |
| Reconcile gegen existierende Trades (Flex wins) | `app/services/ib_reconcile.py:179` | `async reconcile_with_flex(conn, xml_text) -> dict` |
| XML-Parser + Upsert (File-Pfad) | `app/services/ib_flex_import.py` | `async import_flex_xml(conn, xml_text) -> ImportResult` |
| XML-Parser + Upsert (File-on-Disk) | `app/services/ib_flex_import.py` | `async import_flex_file(conn, xml_path: Path) -> ImportResult` |
| Config-Settings | `app/config.py:95-102` | `settings.ib_flex_token`, `settings.ib_flex_query_id` (beide `str \| None`) |
| Scheduler-Framework + `logged_job`-Wrapper | `app/services/scheduler.py:127-198` | Behandelt Timeouts, Audit-Rows, CancelledError — nicht anfassen |
| Health-Widget-Datenquelle | `app/services/scheduler.py:375-412` | `get_last_job_runs(conn)` — iteriert über `JOB_NAMES` |

### Scheduler-Pattern (aus `scheduler.py:219-342` ableiten)

Der neue Job folgt exakt dem Pattern von `gordon_weekly_job` (Zeilen 293-306):
1. Async Closure innerhalb `setup_scheduler`
2. Acquire Conn aus `db_pool`
3. Eigentliche Arbeit aufrufen
4. Bei degradiertem Erfolg (`None`) explizit `raise RuntimeError` damit der `logged_job`-Wrapper `status='failure'` in `job_executions` schreibt (sonst wäre der Run grün obwohl nichts passiert ist)
5. `scheduler.add_job(logged_job(name, fn, db_pool), CronTrigger(...), id=..., replace_existing=True)`

### Warum 07:00 UTC und nicht 02:00?
NYSE-Close ist 21:00 UTC (Winterzeit) bzw. 20:00 UTC (Sommerzeit). IB finalisiert die Executions über Nacht — Flex-Queries sind typischerweise ab ~06:00 UTC für den Vortag vollständig. 07:00 UTC ist konservativ (09:00 Berlin, Chefs Frühstück). Nicht 02:00, weil da Flex-Queries häufig noch "Statement generation in progress" (ErrorCode 1019) liefern und wir die 10 Poll-Attempts à 3s (= 30s max) nicht ausreizen wollen.

### Lückenschluss-Garantie — warum reicht das?

| Ausfallszenario | Warum Sliding-Window es heilt |
|-----------------|-------------------------------|
| App 1 Tag aus | Nächster Run zieht 90-Tage-Window, dedupt via `UNIQUE(broker, perm_id)`, neue Trades landen |
| App 1 Woche aus | Selbes Prinzip — 83 Tage Puffer |
| App 1 Monat aus | 60 Tage Puffer |
| App 3 Monate aus | **Grenzfall** — Health-Widget zeigt seit Woche 0 rote Pille, Chef wird vorher reagieren |
| Flex-Service down an genau einem Tag | Logged als `failure`, kein Datenverlust, nächster Run heilt |
| Einzel-Trade in IB nachträglich korrigiert | `reconcile_with_flex` updated divergente Felder (Flex wins, FR5) — deckt Task 4 aus Story 2.2 |

Kein Gap-Tracking nötig, kein "letzter erfolgreicher Run"-Cursor. Einfachheit schlägt Cleverness.

### Tests — warum so strikt

Die IB-Flex-Integration ist **nicht in CI testbar** (kein Live-Token). Jeder Code-Pfad muss daher via Mocks abgedeckt sein — sonst bricht sie lautlos in Produktion. Empfohlene Mocks:
- `download_flex_xml` → `unittest.mock.patch` auf Modul-Ebene (`app.cli.ib_flex_import.download_flex_xml` für CLI-Tests, `app.services.scheduler.run_nightly_reconcile` für Scheduler-Tests)
- HTTP-Schicht: `httpx.MockTransport` falls irgendwo ein echter Call durchsickern könnte

### Fehlerbehandlung — Graceful Degradation

Die App **muss** auch ohne `IB_FLEX_TOKEN` starten. Fehlender Secret ist kein Error, sondern "Feature ausgeschaltet" (Pattern aus `ctrader_host`, `mcp_fundamental_url`). Das erlaubt Chef, die App hochzufahren bevor er die IB-Query konfiguriert hat.

### Logging-Konvention (structlog)

Alle Log-Events mit Prefix `ib_flex_nightly.*`:
- `ib_flex_nightly.ok` — erfolgreicher Lauf, `counts`-Dict expanded
- `ib_flex_nightly.disabled_unconfigured` — Feature aus
- Indirekt bereits existierend: `ib_flex_download.*` aus `ib_reconcile.py`, `ib_reconcile.*` aus `ib_reconcile.py`

### Project Structure Notes

Kein neues File im `app/`-Tree. Nur Modifikationen:
- `app/services/scheduler.py` — JOB_NAMES + Job-Body + Registrierung
- `app/cli/ib_flex_import.py` — `--pull`-Flag + Mode-Split
- `.env.example` — Kommentar-Refresh

Neue Test-Files (erwartet):
- `tests/unit/test_scheduler_ib_flex.py`
- `tests/unit/test_cli_flex_pull.py`

### References

- PRD: FR1, FR2, FR3 (Flex deckt FR3 für Sliding-Window-Batches ab), FR4, FR5, FR49, FR50, NFR-R1, NFR-I3
- Epics: `_bmad-output/planning-artifacts/epics.md:760` (Epic 2), `epics.md:1725-1726` (Epic 11 AC2 — Nightly-Registrierung)
- Architecture: `_bmad-output/planning-artifacts/architecture.md` — "IB Integration" (ib_async + Flex), "APScheduler im FastAPI-Lifespan"
- Vorgänger-Stories:
  - Story 2.1 (done) — `ib_flex_import.py` Parser + Upsert
  - Story 2.2 (review, Rest-Descope) — `ib_reconcile.py` Downloader + Reconciler (Scheduler-Hook explizit auf Story 12.1 verschoben; Story 2.5 holt diesen Hook ohne Warten auf Epic 12 nach, weil er funktional zu Epic 2 gehört)
  - Story 11.1 (done) — Scheduler-Framework, `logged_job`, `JOB_NAMES`, `get_last_job_runs`, Migration 017 (`status='cancelled'`)
- Deferred: **löst D232** aus `_bmad-output/implementation-artifacts/deferred-work.md`. Beim Merge: D232 als erledigt markieren (append-only — nicht löschen, sondern `✅ RESOLVED by Story 2.5` anhängen)
- CLAUDE.md: "Datenbank-Änderungen NUR über Migrationen" — diese Story braucht **keine** Migration, alles läuft über existierende Tabellen (`trades`, `job_executions`)
- Locked Decision: `ib_async` (nicht `ib_insync`) — irrelevant für diese Story, weil Flex-Pfad rein HTTP (`httpx`), kein TWS-Contact

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`

### Debug Log References

- Erster Test-Run gegen `test_scheduler_ib_flex.py` schlug fehl: `scheduler.start()` in `setup_scheduler()` braucht einen laufenden Event-Loop. Fix: Tests async deklariert (pytest-asyncio mode=auto im Projekt aktiv).
- Zweiter Test-Run gegen `test_cli_flex_pull.py` schlug fehl: `PermissionError` auf `data/logs/ctrader.log` (owned by root nach `make start`). Fix: autouse fixture `_silence_configure_logging` in CLI-Testdatei, danach auch in `tests/conftest.py` generalisiert — deckt 25 weitere Tests ab, die über `TestClient` den Lifespan triggern.
- Ruff meldete 5 Import-Order-Issues in den neuen Test-Files; alle via `ruff --fix` behoben (unused `scheduler_mod`-Imports entfernt).

### Completion Notes List

- **Wire-Up-Strategy eingehalten:** Kein neuer Downloader gebaut. `download_flex_xml` aus `app/services/ib_reconcile.py:61` und `run_nightly_reconcile` aus `:250` werden vom Scheduler-Job und vom CLI-`--pull` direkt konsumiert.
- **Conditional registration** via `settings.ib_flex_token and settings.ib_flex_query_id`-Gate (Pattern aus `ctrader_host` / `mcp_fundamental_url`); kein Half-Configured-Zustand.
- **Failure-raise-Pattern:** `run_nightly_reconcile` returned `None` → `RuntimeError` damit `logged_job` das als `status='failure'` in `job_executions` persistiert. Mirror von `gordon_weekly_job:293-299`.
- **Health-Widget-Integration:** `JOB_NAMES["ib_flex_nightly"]` wird **unconditional** eingetragen. Bei disabled Feature zeigt der Widget `never_run` statt den Eintrag zu verschweigen — besseres Default für Chef.
- **Exit-Codes sind CLI-Kontrakt:** 0 / 2 (argparse) / 3 (download fail) / 4 (missing secrets). Alle Pfade testabgedeckt.
- **Defensiver conftest-Fix** (Task 7.4): `configure_logging` wird in Unit-Tests gestubbt. Das ist ein Test-Infrastructure-Fix, kein App-Code-Change, und fixt ein Environment-Problem (root-owned Log-Files durch Docker-Lifecycle), das unabhängig von Story 2.5 besteht.
- **D232 aufgelöst:** In `deferred-work.md` wird der Eintrag unten als `✅ RESOLVED by Story 2.5` annotiert (append-only).
- **476 Unit-Tests grün, ruff clean.** Integration-Tests (20 deselected) brauchen testcontainers-DB — der existierende `test_reimport_is_idempotent` deckt AC 10 ab, jetzt mit Story-2.5-Kommentar annotiert.

### File List

Modified:
- `app/services/scheduler.py` — `JOB_NAMES["ib_flex_nightly"]` + conditional `setup_scheduler` registration + `ib_flex_nightly_job` body + import von `run_nightly_reconcile` und `settings`
- `app/cli/ib_flex_import.py` — komplett umgebaut: mutually-exclusive `xml_file` vs `--pull`, zwei `_run_*`-Pfade, Exit-Codes dokumentiert
- `.env.example` — Kommentarblock für `IB_FLEX_TOKEN`/`IB_FLEX_QUERY_ID` mit IB-Query-Konfigurationshinweisen
- `tests/conftest.py` — autouse fixture `_stub_configure_logging` (fixt 25 Tests, die via TestClient-Lifespan scheiterten)
- `tests/integration/test_flex_import.py` — Kommentar über `test_reimport_is_idempotent` mit Story-2.5-AC-10-Verlinkung

Created:
- `tests/unit/test_scheduler_ib_flex.py` — 6 Tests: JOB_NAMES-Eintrag, conditional registration (×3), Job-Body-Args, Failure-Raise
- `tests/unit/test_cli_flex_pull.py` — 7 Tests: argparse-Validierung (×2), missing-secrets (×2), download-fail, happy-path, file-mode-regression

Test-Count: **+13 new tests**, 476/476 non-integration grün, ruff clean.

### Change Log

- **2026-04-21:** Story 2.5 implementiert. Wire-Up des APScheduler-Jobs `ib_flex_nightly` (07:00 UTC) + CLI-Flag `--pull`. Löst D232 aus `deferred-work.md`. Kein neuer Service-Code — nutzt existierenden Downloader aus Story 2.2. `+13` neue Tests, Full-Unit-Suite (476 Tests) grün, ruff clean.
