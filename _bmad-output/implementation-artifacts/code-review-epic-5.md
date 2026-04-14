---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: f027d38
stories_reviewed:
  - 5-1-mcp-fundamental-cache
  - 5-2-fundamental-trade-drilldown
  - 5-3-graceful-degradation-staleness
  - 5-4-mcp-contract-test
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 8
  patch_medium: 10
  patch_low: 0
  defer: 40
  dismiss: 3
status: tranche-a-applied
---

# Code Review — Epic 5 (Stories 5.1–5.4)

Adversarial multi-layer review of the fundamental-integration block. Acceptance Auditor reported **all four stories ready-for-done** on the AC level; Blind Hunter + Edge Case Hunter surfaced 84 implementation findings. Tranche A applies 18 patches (8 HIGH + 10 MEDIUM) + tests + live smoke.

## Patches Applied — Tranche A (18)

### 🔴 HIGH (8)

- **H1** **`_render()` was sync and never called `_base_context()`** (BH-1, EC-29). Five secondary pages (strategies/approvals/trends/regime/settings) silently lost the contract-drift banner. Fix: make `_render` async and `await _base_context(request)`. All five page-route `return _render(...)` calls switched to `return await _render(...)`. *(app/routers/pages.py)*

- **H2** **`is_stale=True` was never set** (EC-1, EC-4). Every stale-fallback return handed back the cached result untouched, so the drilldown stale-badge (`fundamental-grid__stale-badge`) was dead code and Story 5.1 AC #4 was unmet. Fix: new `_as_stale()` helper reconstructs the `FundamentalResult` with `is_stale=True` at all three fallback points (MCP disabled, timeout, generic exception). *(app/services/fundamental.py)*

- **H3** **Parse functions violated the "never raise" contract** (EC-2, EC-3, EC-25, EC-27). `_parse_mcp_response` and `_extract_tools` crashed on `{"result": "string"}`, `{"result": None}`, top-level non-dict, and malformed snapshot JSON. Fix: defensive `isinstance(..., dict)` checks at every level, new `_first_present()` helper, forward-compat rating/confidence/thesis key triples (adds `verdict`/`opinion`/`rationale`). Also handles content-as-dict shape, filters MCP metadata keys from `extra`. *(app/services/fundamental.py, app/services/mcp_contract_test.py)*

- **H4** **Fire-and-forget snapshot task held no strong reference** (BH-13, EC-17). `asyncio.create_task(...)` without a reference can be GC'd mid-run per the asyncio docs. Fix: module-level `_background_tasks: set[asyncio.Task]`, `add()` on schedule, `add_done_callback(discard)` on completion. *(app/services/ib_live_sync.py)*

- **H5** **`_persist_report` silently swallowed DB write failures** (BH-18, EC-22). A drift detection that failed to persist returned `status=pass` to the API caller while the banner on the next page load reflected the *previous* run. Fix: `DriftReport.persisted: bool` field, `_persist_report` flips it on success and appends a suffix to the error string on failure. `/api/mcp-contract-test` returns 500 when `persisted=False` so Chef knows the audit trail is broken. *(app/services/mcp_contract_test.py, app/routers/api.py)*

- **H6** **`load_snapshot` picked lexicographically-latest, vulnerable to off-spec filenames** (BH-20, EC-24). A rogue `week0-final.json` would silently become the drift baseline. Fix: compile `_SNAPSHOT_FILENAME_RE = re.compile(r"^week0-\d{8}\.json$")` and filter. Also handle `null` JSON and non-dict-JSON as error returns. *(app/services/mcp_contract_test.py)*

- **H7** **`_parse_confidence` accepted `bool` and `NaN`** (BH-4, BH-5). `True/False` coerce via `float()` to `1.0/0.0`, silently passing as fake confidence values. `NaN` would crash the `FundamentalAssessment` Pydantic validator. Fix: explicit `isinstance(raw, bool)` rejection and `value != value` NaN check. *(app/services/fundamental.py)*

- **H8** **`format_staleness` / `severity_for_staleness` treated future timestamps as "gerade eben" / "ok"** (BH-7, BH-8). Clock skew or tz bugs silently mapped a future `cached_at` to a healthy state. Fix: 5-second tolerance, anything beyond returns `"in der Zukunft (?)"` phrasing and `red` severity so the banner screams until the root cause is fixed. *(app/services/staleness.py)*

### 🟡 MEDIUM (10)

- **M1** **Double-timeout** — `asyncio.wait_for` wrapping `call_tool` which already has its own httpx timeout (BH-3). Fix: drop the outer wait_for, catch both `httpx.TimeoutException` and builtin `TimeoutError` in the except clause. Removes the `timeout` kwarg from `get_fundamental`. *(app/services/fundamental.py)*

- **M2** **MCP content parsing** — `content` as a dict instead of a list was silently ignored; MCP envelope metadata (`content`, `isError`, `_meta`, `jsonrpc`) leaked into the stored `extra` bag (BH-9, BH-11). Fix: Shape 1b handles dict-shaped content, `_MCP_METADATA_KEYS` frozenset excludes transport fields from `extra`. *(app/services/fundamental.py)*

- **M3** **Hardcoded `rating/signal/recommendation` field triple** (EC-6). A future MCP schema drift using `verdict` or `opinion` would silently map every assessment to `UNKNOWN`. Fix: `_RATING_FIELDS = ("rating", "signal", "recommendation", "verdict", "opinion")`, `_THESIS_FIELDS` and `_CONFIDENCE_FIELDS` similarly extended. *(app/services/fundamental.py)*

- **M4** **`capture_fundamental_snapshot` persisted vacuous snapshots** (EC-15). A `{rating=UNKNOWN, thesis=""}` result (often an MCP preamble parse miss) was written as a real "damals" row. Fix: skip persist when rating is UNKNOWN AND thesis is empty, log a `skipped_vacuous` event. *(app/services/fundamental_snapshot.py)*

- **M5** **`_fresh_cache_for` bypassed normalization** (EC-10). Trailing whitespace on `asset_class` silently disabled the cache. Fix: strip + lower inside `_fresh_cache_for` to match `_cache_key`. *(app/services/fundamental.py)*

- **M7** **`<span>` → `<div>` HTMX swap** for the staleness banner empty state (BH-23). OuterHTML span-to-div swaps can orphan listener state. Fix: use a `<div>` in both branches. *(app/templates/components/staleness_banner.html)*

- **M8** **`worst_severity` KeyError on unknown severity tokens** (BH-25, BH-33). A future `degraded` or `unknown` token would crash the banner. Fix: `order.get(agent.severity, 0)` default. *(app/services/mcp_health.py)*

- **M10** **Dead expression in test** — `clear_caches.__wrapped__ if hasattr(...)` (BH-28, EC-34). Abandoned refactoring leftover. Removed + added `is_stale=True` assertion for the now-patched fallback path. *(tests/unit/test_fundamental.py)*

- **M12** **Jinja `drift_details.get()` crashed on non-mapping** (BH-16). A malformed DB row or codec bypass could hand the template a list/str. Fix: `{% set drift_details_safe = ... if mapping else {} %}`. *(app/templates/base.html)*

- **M13** **`handle_execution` kwargs wiring for Story 12.1** (EC-5). The signature change was invisible to future subscribers. Fix: docstring explicitly demands `functools.partial(handle_execution, conn=..., mcp_client=..., db_pool=...)` at subscribe time. *(app/services/ib_live_sync.py)*

### Dismissed (3)

- **BH-2 Stale-cache prune race** — single-process asyncio, no `await` between length check and mutation. Single-User-Localhost-acceptable.
- **BH-26 / EC-38 / EC-48 Sources-of-truth duplication** (`_KNOWN_AGENTS`, `DEFAULT_SNAPSHOT_DIR`, `_FACET_KEYS`) — cosmetic drift risk, defer.
- **CSRF / auth** across Epic 5 endpoints — Single-User-Localhost, NFR-S2 binds to 127.0.0.1.

## Test Results

- **319 / 319 passing** (was 298; +21 new tests across `test_fundamental_defensive.py` and `test_mcp_contract_test_defensive.py`)
- New tests cover: parse-on-non-dict-raw, MCP metadata exclusion, content-as-dict shape, verdict forward-compat, bool/NaN rejection, `is_stale=True` on stale fallback, future-timestamp phrasing, snapshot regex filter (rejects `week0-final.json` / `week0-legacy.json`), null-JSON and non-dict-JSON snapshot rejection
- `ruff check` + `ruff format` clean

## Live Smoke Verification

- **H1**: All 5 secondary pages (`/strategies`, `/approvals`, `/trends`, `/regime`, `/settings`) render the staleness banner (10 class matches each)
- **H5**: `POST /api/mcp-contract-test` now returns `"persisted": true` in the JSON body
- **H6**: Broker allowlist (Epic 4 carry-over) still healthy
- Graceful degradation paths (no MCP server, no snapshot file) all exercised without exceptions

## Deferred (40)

Catalogued in `deferred-work.md` as D103–D142 covering LOW findings, Single-User-Localhost-acceptable edge cases, and follow-ups (scheduler wiring for Story 12.1, health-widget consumer for Story 12.2, Alpine modal UX drift, agent-name duplication).

## Story status after Tranche A

| Story | Status |
|---|---|
| 5.1 MCP Fundamental Cache + TTL | **done** |
| 5.2 Fundamental Trade Drilldown | **done** |
| 5.3 Graceful Degradation + Staleness Banner | **done** |
| 5.4 MCP Contract Test | **review** — scheduler wiring moves to Story 12.1, health-widget consumer to Story 12.2 |
