---
review_date: 2026-04-13
review_type: adversarial-multi-layer
diff_range: 9ed1248..f8dd1e7
files_changed: 73
lines: '+4514 / -169 (effective +3518 ohne uv.lock)'
stories_reviewed:
  - 1-1-fastapi-scaffolding
  - 1-2-migrations-framework
  - 1-3-taxonomy-loader
  - 1-4-design-tokens-tailwind
  - 1-5-base-layout-navigation
  - 1-6-mcp-client-wrapper
reviewers:
  - acceptance-auditor (general-purpose subagent)
  - blind-hunter (general-purpose subagent, no project context)
  - edge-case-hunter (general-purpose subagent, project read access)
findings_summary:
  decision_needed: 0
  patch_high: 4
  patch_medium: 13
  patch_low: 1
  defer: 20
  dismiss: 6
status: all-patches-applied
---

# Code Review — Epic 1 (Stories 1.1–1.6)

**Adversarial multi-layer review** of the entire Epic 1 implementation block (FastAPI scaffolding, migrations, taxonomy loader, design tokens, base layout, MCP client). Run by John (PM agent) coordinating three parallel reviewer personas via subagents.

## Reviewer Layers

| Layer | Inputs | Findings raised |
|---|---|---|
| **Acceptance Auditor** | diff + 6 story files + PRD + architecture | Cross-spec contradictions, AC coverage matrix |
| **Blind Hunter** | diff only (NO project context) | 28 findings, adversarial prose |
| **Edge Case Hunter** | diff + project read access | 22 findings, branching/boundary analysis |

## Triage Result

- **0 decision_needed** — alle Trade-offs sind in den Stories bereits dokumentiert
- **18 patches** — alle batch-applied am 2026-04-13
- **20 deferred** — pre-existing, NFR-M6-rationalisiert oder kosmetisch
- **6 dismissed** — intentional design / acknowledged scope reductions

## Patches Applied (18)

### 🔴 HIGH (4)

- [x] **P1** — Lifespan shutdown crashes mit AttributeError bei partial startup failure (`app/main.py:42-83`) — `getattr(...)` + null-checks im finally-Block, Default-State `app.state.* = None` vor try
- [x] **P2** — RotatingFileHandler leaked auf jedem `configure_logging()`-Call (`app/logging.py:60-67`) — neue `_close_existing_handlers()` Funktion + `contextlib.suppress`-Pattern
- [x] **P3** — Tests schreiben in hardcoded `data/logs/ctrader.log` (`tests/unit/test_logging.py`) — autouse `_isolated_log_path` fixture redirected `settings.log_file` auf tmp_path
- [x] **P4** — `horizon_type` ENUM mismatch zwischen Migration 001 und taxonomy.yaml (`migrations/001_initial_schema.sql:55-72`) — Migration erweitert auf alle 4 Werte (`intraday`, `swing_short`, `swing_long`, `position`) + Doku-Kommentar zur Sync-Pflicht

### 🟠 MEDIUM (13)

- [x] **P5** — `_count_tools` miscount bei String-Payload (`app/clients/mcp.py:97-103`) — explizites `isinstance(tools, list)` statt `Iterable`
- [x] **P6** — Migration version sort lexikographisch (`app/db/migrate.py:69`) — `key=lambda m: int(m.version)`
- [x] **P7** — uvicorn-Loggers bypassen structlog JSON-Pipeline (NFR-M4) (`app/logging.py:28-37`, `103-108`) — `_PROPAGATING_LOGGERS`-Liste mit uvicorn/asyncpg/fastapi/httpx, deren Handler werden gestrippt und auf root propagiert
- [x] **P8** — `DEFAULT_TIMEOUT_SECONDS` ignoriert wenn `client` injected (`app/clients/mcp.py:80-83`) — explizites `timeout=self.timeout` auf jedem `post()`-Call
- [x] **P9** — Migration version-collision nicht detected (`app/db/migrate.py:50-69`) — `discover_migrations` nutzt jetzt ein dict + `raise ValueError` bei Duplikat
- [x] **P10** — `.sql`-Files mit non-matching names werden silently skipped (`app/db/migrate.py:55-65`) — `logger.warning("migrate.malformed_filename", ...)` für nicht-passende `.sql`-Files
- [x] **P11** — MCP-Snapshot-write-error markiert MCP komplett als unavailable (`app/clients/mcp.py:140-194`) — Phase 1 (handshake) und Phase 2 (snapshot write) sind getrennt; Snapshot-Failure ist non-fatal mit explizitem `OSError`-catch
- [x] **P12** — MCPClient nicht-JSON Response crashed Handshake (`app/clients/mcp.py:153-159`) — explizites `except json.JSONDecodeError` mit klarem hint
- [x] **P13** — Taxonomy-Singleton leaked across tests (`tests/conftest.py:55-65`) — neue autouse `_clear_taxonomy_cache` fixture clears die `lru_cache` vor UND nach jedem Test
- [x] **P14** — Logging-Pfad CWD-relativ (`app/logging.py:21-23`, `42-53`) — `_PROJECT_ROOT = Path(__file__).resolve().parents[1]` + `_resolve_log_path()` anchor-Funktion
- [x] **P15** — `test_pool_is_attached_to_app_state` asserts nothing meaningful (`tests/unit/test_main.py:42-55`) — neue assertion via `_fake_db_pool`-Fixture-Return: `assert app.state.db_pool is _fake_db_pool` (Identity-Check statt truthy-Check)
- [x] **P16** — `test_get_logger_returns_bound_logger` ist Tautologie (`tests/unit/test_logging.py:113-122`) — `or hasattr(...)` Fallback entfernt, strikter `isinstance(structlog.types.BindableLogger | structlog.stdlib.BoundLogger)` Check
- [x] **P17** — `_fake_mcp_handshake` in conftest ist dead code (`tests/conftest.py:32-49`) — entfernt (war nie erreicht weil `mcp_fundamental_url=None` in Tests)

### 🟢 LOW (1)

- [x] **P18** — `debug_mcp_tools` hat kein try/except (`app/routers/debug.py:35-50`) — wrap in `try/except (httpx.HTTPError, RuntimeError)`, Return 503 statt 500-Traceback

## Deferred (20)

Diese Findings sind real, aber nicht blockend für Sprint-Start. Werden in `deferred-work.md` getrackt und bei passenden Stories aufgegriffen.

- **D1** — Story 1.1 AC2 Spec-Text-Drift (302 redirect) — `auditor`. Spec-Text-Update beim nächsten PRD-Touch.
- **D2** — Story 1.4 fonts deferred ohne tracking ticket — `auditor`. Pixel-perfect typography wenn Chef es will.
- **D3** — Ruff CI gate nicht enforced — `auditor`. → Story 12 (CI/Health Operations).
- **D4** — Integration-Tests opt-out documentation — `auditor`. → Story 12.
- **D5** — structlog cached logger race in tests — `blind`. Mit `cache_logger_on_first_use=False` (P2/P7) jetzt teilweise mitigated.
- **D6** — `test_debug_mcp_tools` happy path missing — `blind`. → Epic 5 wenn echter MCP-Server da ist.
- **D7** — Migration runner concurrent starts race (kein `pg_advisory_lock`) — `blind+edge`. NFR-M6 sagt single-process — dokumentiert als known limitation.
- **D8** — `test_topbar_has_no_hamburger` brittle — `blind`. Funktioniert für jetzt.
- **D9** — `test_active_nav_link_marked` whitespace-exact — `blind`. Funktioniert für jetzt.
- **D10** — Docker restart loop ohne backoff — `blind`. → Epic 12.
- **D11** — Inline `<style>` blocks duplicated in 6 page templates — `blind`. → Epic 2 wenn Journal echte Styles braucht.
- **D12** — `DEFAULT_*_PATH` via `parents[N]` — `blind`. Funktioniert solange ctrader nicht packaged ausgeliefert wird.
- **D13** — `test_first_run_applies_001` mutates session-scoped pg_container — `blind`. → Epic 2 wenn mehr Migration-Tests dazukommen.
- **D14** — Migration partial-script failure (CONCURRENTLY) — `edge`. Aktuell triggert keine Migration das.
- **D15** — Migration UTF-8 BOM — `edge`. Wenn Bedarf, `encoding="utf-8-sig"`.
- **D16** — MCP timezone boundary — `edge`. UTC by design, dokumentiert.
- **D17** — Taxonomy YAML `null` section error message — `edge`. Pydantic-Default ist gut genug.
- **D18** — Taxonomy empty YAML file error message — `edge`. Edge case, nicht beobachtet.
- **D19** — Debug route shutdown race — `edge`. Mit P18 (try/except) jetzt teilweise mitigated, restliche Race ist ein Single-User-Localhost-Edge-Case.
- **D20** — Conftest pool shutdown AsyncMock spec — `edge`. → Wenn Mock-Probleme auftreten.

## Dismissed (6)

- **dis1** — MCP_FUNDAMENTAL_URL optional — `auditor`. **Intentional**: Single-User-Localhost-Convenience, Story 1.6 Dev-Notes erklären es.
- **dis2** — Kein offizielles `mcp`-Package — `auditor`. **Intentional**: Week-0-Scope, in Epic 5 evtl. wechseln.
- **dis3** — Tailwind v4 vs v3 — `auditor`. **Intentional**: pytailwindcss lädt latest, semantisch äquivalent.
- **dis4** — `app.migrations_applied` log duplicate — `blind`. Kosmetisch.
- **dis5** — Default DB password `ctrader:ctrader` — `blind`. **Intentional**: Single-User-Localhost-Convenience, NFR-S1 spricht von API-Credentials nicht DB-Defaults.
- **dis6** — MCP daily snapshot overwrite — `edge`. **Intentional**: Story 1.6 ist "Woche-0-Baseline", nicht "alle Snapshots aufbewahren".

## Verification After Patches

- `uv run pytest` → **68 passed in 2.21s** (64 unit + 4 integration)
  - Davon **1 neuer Test**: `test_configure_logging_closes_old_handlers_on_reconfigure`
- `uv run ruff check .` → All checks passed
- `uv run ruff format --check .` → 31 files already formatted

## Files Changed by This Patch Round

**Geändert (10):**
- `app/main.py` — P1 (lifespan finally guard)
- `app/logging.py` — P2/P3/P7/P14 (handler close, propagating loggers, project-root anchor)
- `app/config.py` — P14 (log_file docstring)
- `app/clients/mcp.py` — P5/P8/P11/P12 (count_tools, timeout, snapshot phases, JSON decode)
- `app/db/migrate.py` — P6/P9/P10 (numerische Sort, version collision, malformed warn)
- `app/routers/debug.py` — P18 (try/except)
- `migrations/001_initial_schema.sql` — P4 (horizon_type ENUM)
- `tests/conftest.py` — P13/P17 (taxonomy cache clear, dead fake removed)
- `tests/unit/test_logging.py` — P3/P16 + 1 neuer Test
- `tests/unit/test_main.py` — P15 (meaningful pool assertion)

**Neu (1):**
- `_bmad-output/implementation-artifacts/code-review-epic-1.md` (this file)
