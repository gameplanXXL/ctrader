# Deferred Work

Findings, refactorings, and ideas that were deliberately postponed during code review or implementation. Each entry has a source (review session or story) and ideally a target story to pick it up.

This file is append-only — never delete entries, only mark them done.

---

## Deferred from: code review of Epic 1 (Stories 1.1–1.6) — 2026-04-13

- **D1** Story 1.1 AC2 spec text drift (`/` returns 302 to `/journal`, original AC said 200). Update spec text on next PRD touch. *Source: acceptance-auditor*
- **D2** Story 1.4 fonts deferred without tracking ticket. Pixel-perfect Inter / JetBrains Mono `.woff2` files under `app/static/fonts/` when typography becomes load-bearing. *Source: acceptance-auditor*
- **D3** Ruff CI gate not enforced — `pyproject.toml` has the config but no GitHub Actions / pre-commit step asserts `ruff check .` stays green. → Story 12 (Ops). *Source: acceptance-auditor*
- **D4** Integration tests are opt-out via `pytest -m "not integration"`. CI must explicitly enable them or AC3/AC4 of Story 1.2 become untested in the pipeline. → Story 12. *Source: acceptance-auditor*
- **D5** structlog cached logger race in tests. Partially mitigated by P2/P7 (cache_logger_on_first_use=False) but specific test isolation around bound-logger reuse still possible. *Source: blind-hunter*
- **D6** `test_debug_mcp_tools` happy path missing — when MCP is available, the route's success branch is never tested in unit tests. → Epic 5 when a real MCP server is available in CI. *Source: blind-hunter*
- **D7** Migration runner has no `pg_advisory_lock` to guard against concurrent app starts racing into the same migration. NFR-M6 says single-process so this is currently impossible, but document as known limitation if scaling out ever happens. *Source: blind+edge*
- **D8** `test_topbar_has_no_hamburger` is brittle — checks free-text substrings, will regress if any page legitimately mentions "drawer". Replace with HTML/class structural check when convenient. *Source: blind-hunter*
- **D9** `test_active_nav_link_marked` uses whitespace-exact multi-line string match. Will break on any Jinja template reformatting. Replace with HTML parser when convenient. *Source: blind-hunter*
- **D10** Docker `restart: unless-stopped` has no backoff. If migrations fail at startup the container will hammer Postgres in a tight restart loop. → Epic 12 (Ops): switch to `on-failure:5` or add a sleep guard. *Source: blind-hunter*
- **D11** Inline `<style>` blocks duplicated across 6 page templates (page-title / page-placeholder rules). Extract to design-tokens.css when Journal needs real styles. *Source: blind-hunter*
- **D12** `DEFAULT_TAXONOMY_PATH`, `DEFAULT_MIGRATIONS_DIR`, `DEFAULT_SNAPSHOT_DIR` use `Path(__file__).resolve().parents[N]`. Works as long as ctrader runs from the repo, breaks if ever packaged as a wheel/zipapp. Move to settings then. *Source: blind-hunter*
- **D13** `test_first_run_applies_001` mutates session-scoped `pg_container` state — a future test in the same module that assumes a clean DB will silently see an already-migrated DB. Add a `_drop_schema` fixture when more migration tests land. *Source: blind-hunter*
- **D14** Migration partial-script failure on `CREATE INDEX CONCURRENTLY` — that statement cannot run inside a transaction, so a future migration containing it will raise `ActiveSQLTransactionError` from `conn.transaction()`. Document the "no CONCURRENTLY in migrations" contract or detect-and-special-case. *Source: edge-case-hunter*
- **D15** Migration runner doesn't strip UTF-8 BOM. A SQL file saved with BOM will fail with an opaque `syntax error at or near ""`. Switch to `encoding="utf-8-sig"` if it ever bites. *Source: edge-case-hunter*
- **D16** MCP snapshot filename uses UTC date — at midnight in UTC+2 (Berlin) the filename "today" doesn't match Chef's wall clock. Document the UTC-day semantics or accept the confusion. *Source: edge-case-hunter*
- **D17** Taxonomy YAML with `null` section produces a generic Pydantic ValidationError. Pre-normalize or improve error message when seen in practice. *Source: edge-case-hunter*
- **D18** Empty `taxonomy.yaml` file produces "did not parse to a mapping" which is technically true but misleading ("parsed to None" would be more accurate). Distinguish empty-file from non-mapping in the error text. *Source: edge-case-hunter*
- **D19** Debug route (`/debug/mcp-tools`) shutdown race partially mitigated by P18 (catches `RuntimeError`), but a request-in-flight during `aclose()` still sees inconsistent state. Single-User-Localhost edge case, accept for now. *Source: edge-case-hunter*
- **D20** Conftest pool fixture uses bare `AsyncMock(name="asyncpg.Pool")` without `spec=asyncpg.Pool`. Future tests using `acquire_connection()` will get AsyncMock returns that silently look "successful" and may mask bugs. Add `spec=` when first such test lands. *Source: edge-case-hunter*

---

## Deferred from: code review of Epic 2 (Stories 2.1–2.4) — 2026-04-13

- **D21** Round-trip trade aggregation. Every Flex `<Trade>` is an execution — open and close land in separate rows with different `perm_id`s. Matching them into round-trip trades (with realized P&L, MAE/MFE, true `entry/exit`) belongs in Epic 4 or 6. Until then the journal shows "executions as trades" which Chef explicitly accepted. *Source: acceptance-auditor*
- **D22** Story 2.2 `execDetailsEvent` subscription + auto-reconnect descoped to Story 12.1 (scheduler framework). Delivered primitives: `upsert_trade()`, `reconcile_open_trades()`, `execution_to_trade()`. Story 12.1 wires the event handler, APScheduler job, and connection supervisor. *Source: chef-decision D-A (b)*
- **D23** Journal list query has no `WHERE broker = …` filter yet — all trades share one list. Multi-broker filtering (IB vs cTrader vs …) lands when Epic 8 goes live. *Source: edge-case-hunter*
- **D24** `pnl` column is persisted but never computed at write-time — `compute_pnl()` is called per-request in the drilldown. Fine for a single-user local app; revisit when strategy-aggregation queries hit latency. *Source: blind-hunter*
- **D25** Journal pagination uses `OFFSET`. Keyset pagination (`WHERE opened_at < $1 ORDER BY opened_at DESC`) is the standard move at ~10k trades. Not needed yet (current count ≪ 1k). *Source: edge-case-hunter*
- **D26** `get_trade_detail` returns a `dict`, not a validated Pydantic model. A schema mismatch (e.g., renamed column) would only surface in the template. Add a `TradeDetail` model when trade schema stabilizes. *Source: blind-hunter*
- **D27** HTMX drilldown request has no debounce / loading indicator. Double-clicks issue duplicate requests. Add `hx-indicator` + `hx-trigger="click once"` when Chef complains. *Source: edge-case-hunter*
- **D28** Inline `<script>` prefill block on the journal page uses `document.getElementById` — works fine but an extra MutationObserver on the row container would be cleaner if more expand-on-load features land. *Source: blind-hunter (D-B a patch)*
- **D29** `_parse_ib_datetime` silently returns `None` for unknown formats. A future Flex schema change could drop every trade as "invalid" with nothing but a single log line. Add a metric `ib_flex.parse_fail_total` when observability matures (Epic 12). *Source: edge-case-hunter*
- **D30** `format_pnl` catches `InvalidOperation` but not `ArithmeticError` — a `Decimal('Infinity')` slipping in would bubble. Tighten the except tuple when the formatter is shared across stories. *Source: blind-hunter*
- **D31** `import_flex_xml` holds a single `conn.transaction()` around all inserts. On a 5k-trade import a single bad row rolls back the whole batch. Split into per-row savepoints when historical reimports grow. *Source: edge-case-hunter*
- **D32** `TradeIn.trigger_spec` is typed `dict[str, Any] | None`. JSONB round-trip tests (insert then read) don't yet exist — we trust asyncpg's `::jsonb` cast. Add an integration test once Story 3.1 (tagging form) writes non-trivial specs. *Source: edge-case-hunter*

---

## Deferred from: code review of Epic 3 (Stories 3.1–3.4) — 2026-04-14

- **D33** Fuzzy-search for tagging-form dropdowns (Story 3.1 AC #5, UX-DR60). Alpine.js / datalist integration deferred to a Story 3.1.1 polish pass. *Source: acceptance-auditor*
- **D34** Per-field blur validation with red border + inline error (Story 3.1 AC #8, UX-DR59). Server-side 422 re-render lands correctly but client-side blur hooks are missing. Story 3.1.1. *Source: acceptance-auditor*
- **D35** Contract test of `TriggerSpec.to_jsonb()` against `fundamental/trigger-evaluator.ts` schema (Story 3.2 AC #4, Task 5). Fold into Story 5.4 (MCP-contract-test) when the MCP snapshot workflow lands. *Source: acceptance-auditor*
- **D36** Bot-proposal auto-population (Story 3.2 AC #2). `build_from_proposal` is an Epic 7 placeholder. Full wiring arrives with Story 7.x. *Source: acceptance-auditor*
- **D37** Mistake-report facet-filter integration (Story 3.4 AC #3). Deferred to Story 4.1 (Facet-Filter-System). *Source: acceptance-auditor*
- **D38** UX-DR74 spec-text: "20-30 patterns" → "one pattern per trigger_type + default". Update in next PRD/UX-Spec pass. *Source: acceptance-auditor*
- **D39** PRD FR18a mistake-tag naming: hyphen → underscore (match taxonomy). *Source: acceptance-auditor*
- **D40** PRD FR18a mistake-tag list: extend from 6 to 9 entries to match taxonomy. *Source: acceptance-auditor*
- **D41** architecture.md: document the JSONB codec in `app/db/pool.py::init_connection` under "JSONB Implementation". *Source: acceptance-auditor*
- **D42** CSRF protection on `POST /trades/{id}/tag`. Single-user-localhost acceptable; revisit when / if the app is exposed beyond localhost. *Source: blind-hunter BH-8*
- **D43** `datetime(2000, 1, 1)` sentinel for `window="all"` — cosmetic magic number. Replace with a more explicit "oldest-in-table" query when convenient. *Source: blind-hunter BH-36, edge-case EC-20*
- **D44** Inline `<style>` duplicated across fragment templates (tagging_form, mistakes_report). Move into compiled Tailwind layer when `pytailwindcss` output grows stable. *Source: edge-case EC-32, EC-36*
- **D45** `information_schema.tables` probe in `strategy_source` runs on every form render. Cache module-level once Epic 6 lands. *Source: blind-hunter BH-27, edge-case EC-49*
- **D46** `mistakes_report_page` catches all exceptions silently — consider `logger.exception` plus a degraded-state banner. *Source: blind-hunter BH-4*
- **D47** `SIDE_DE["short"] = "short-te"` is Denglish, not German. Replace with "ging short auf" or similar when Chef weighs in. *Source: blind-hunter BH-14*
- **D48** Umlaut-free transliteration (`ueberstimmte`, `Haeufigkeit`, …). Normalize to proper German with umlauts now that UTF-8 rendering is stable. *Source: blind-hunter BH-15*
- **D49** `_format_with_fallback` silently masks pattern-template typos as "Unbekannt". Add a strict mode or validator. *Source: blind-hunter BH-16*
- **D50** `AGENT_NAMES` lacks a test that all MVP agents (Viktor, Rita, Satoshi, Cassandra, Gordon) are present. Add when a new agent lands. *Source: edge-case EC-37*
- **D51** `HORIZON_LABELS` not locked to taxonomy by a test. Add assertion like the trigger-type coverage test. *Source: edge-case EC-39*
- **D52** `mistakes_report.top_n_mistakes` filters by `opened_at`; for `position` horizon trades closed long after open this is counter-intuitive. Consider a toggle "by-opened vs by-closed". *Source: edge-case EC-19*
- **D53** Raw SQL in `mistakes_report_page` route handler (the `total_trades` count). Move to `app/services/mistakes_report.py`. *Source: edge-case EC-24*
- **D54** Concurrent `UPDATE trades SET trigger_spec` vs `_UPSERT_SQL` live-sync race. Safe today because UPSERT skips trigger_spec, but worth documenting. *Source: edge-case EC-22*
- **D55** Missing integration test: end-to-end tagging POST → DB write → prose render. Exact bug class H7 / H8 addressed; an integration test would lock it. *Source: edge-case EC-50*
- **D56** Tagging form's `"Press Enter to save"` hint is misleading when a textarea has focus (Enter inserts newline). *Source: blind-hunter BH-37*
- **D57** `/journal/mistakes` sub-page has no top-nav affordance — discoverability handled in Epic 4. *Source: edge-case EC-46*
- **D58** `format_time` truncates seconds in the mistakes-report window-meta line. Cosmetic. *Source: edge-case EC-47*
- **D59** Duplicate globals registration on two Jinja envs (`pages.py` + `trades.py`). Extract `register_trigger_globals(env)` helper. *Source: blind-hunter BH-30*
- **D60** `_trigger_spec_json` round-trips via `json.loads(json.dumps(..., sort_keys=True))` — sort-key ordering is lost after the second encode. Cosmetic (JSONB is order-agnostic). *Source: edge-case EC-28*
- **D61** `list_strategies_for_dropdown` swallows `Exception`; an outer `logger.exception` would improve debug. *Source: edge-case EC-48*
- **D62** Story 3.1.1 follow-up — consolidated: submit-button spec reconciliation, fuzzy-search, blur validation, textarea-aware Enter hint. *Source: triage bundle*

---

## Deferred from: code review of Epic 4 (Stories 4.1–4.7) — 2026-04-14

### Facet framework
- **D63** `build_where_clause` placeholders hardcoded to start at `$1`. Future callers that prepend their own parameter would silently alias. Accept `placeholder_start` arg when needed. *Source: BH-1*
- **D64** `_FACET_KEYS` in `pages.py` duplicates registry names — two sources of truth. Build dynamically from `get_registry().names` when a new facet lands. *Source: EC-6*
- **D65** `render_facets` swallows per-facet `get_values` errors into empty lists without marking the facet "errored" in the UI. Worth a small "(error)" badge. *Source: BH-22*
- **D66** `test_build_where_clause_*` tests hardcode `$1` / `$2` placeholder numbers. Brittle on registry reordering. *Source: EC-7*
- **D67** Facet chip `hx-target="#journal-main"` fails silently on pages without that element (calendar). Fall back to `href` works but UX intent is wrong. *Source: BH-39*
- **D68** `_parse_facet_query` splits on `,` without URL-decoding. Values like `test%2Ckey` arrive already decoded, then get unintentionally split. *Source: EC-44*

### Aggregation / drawdown
- **D69** Expectancy is dollar-based, not R-multiple. Swap to R when Epic 11 persists `stop_price`. *Source: acceptance-auditor*
- **D70** Hero card labels don't distinguish `trade_count` (all) from `closed_count` (used for expectancy). Potential misread. Relabel or add a sub-count. *Source: BH-6*
- **D71** Opacity flash on facet-change (UX-DR42). Deferred — Single-User-Localhost. *Source: acceptance-auditor*
- **D72** Server-side aggregation cache with insert-based invalidation (UX-DR103). Deferred — dataset is tiny today. *Source: acceptance-auditor*
- **D73** `_ensure_pnl` behavior with partially-populated row (e.g., exit_price None but pnl NULL). Verify `compute_pnl` handles all permutations cleanly. *Source: EC-11*

### MAE/MFE / OHLC
- **D74** OHLC batch upsert does N round-trips. At 390 1m candles per trade, acceptable locally but not for backfill. `executemany` + `COPY` when needed. *Source: EC-30*
- **D75** Cache read SQL uses half-open `ts >= $3 AND ts < $4`. Exit-candle off-by-one for trades that close exactly on a minute boundary. *Source: EC-33*
- **D76** `asyncio.get_event_loop().time()` deprecated in 3.12+. Cosmetic. *Source: EC-32*
- **D77** `_get_candles` short-circuits on first TF match — if only M5 cache exists, the fresh-fetch path is taken instead of using M5. *Source: BH-11*
- **D78** Scalp trades with `closed_at == opened_at` get empty candle range → NULL MAE/MFE. No user hint. *Source: BH-8*
- **D79** Real IB/Binance/Kraken/MCP OHLC clients — Story 4.3 AC #3. Wire when a live data source lands. *Source: acceptance-auditor*
- **D80** lightweight-charts binary drop-in — Story 4.5. Chef provides the 35KB file when needed. *Source: acceptance-auditor*
- **D81** Chart markers can land outside the candle range (no bounds guard). Lightweight-charts handles it silently. *Source: EC-35*
- **D82** Multiple `<style>` blocks re-inject on every HTMX swap of `trade_detail.html`. Cosmetic DOM bloat. *Source: BH-33, EC-36*

### Calendar
- **D83** Month-boundary double-bucketing — a trade opened in March and closed in April shows on both months' calendars. Doc or split. *Source: EC-13*
- **D84** Calendar is UTC-bucketed; Chef in CET sees Monday early-morning trades on Sunday's cell. Locally-local day bucketing optional. *Source: BH-13*
- **D85** Calendar tint uses fixed 25% mix, not proportional to |pnl|. Minor spec drift (UX-DR72). *Source: acceptance-auditor*

### CSV export
- **D86** DB-error fallback returns `"\ufeff"` (BOM only) + HTTP 200. Should 5xx or include header row + error line. *Source: BH-19 / EC-18*
- **D87** `mistake_tags` CSV column reads from `trigger_spec->>'mistake_tags'` — correct post-Epic-3, flag if taxonomy ever moves them elsewhere. *Source: BH-43*
- **D88** Decimals like `Decimal("1E+1")` render as scientific notation in CSV. Normalize via quantize. *Source: BH-18*
- **D89** Computed pnl = `Decimal("0")` shows as empty string in CSV (`Decimal("0") or ""`). Could confuse downstream. *Source: EC-19*
- **D90** `StreamingResponse` for 2k+ row CSV instead of buffered body. Deferred. *Source: BH-38*

### Command palette
- **D91** `aria-activedescendant` on the listbox element itself, not just `aria-selected` per-item. UX-DR23 only partial. *Source: acceptance-auditor*
- **D92** Palette items cached forever — saving a new preset doesn't refresh the open palette. Refetch on `showToast` or refetch on reopen. *Source: EC-38*
- **D93** `evt.key === 'k'` breaks on CapsLock (sends `'K'`). Use `toLowerCase()`. *Source: EC-39*
- **D94** No input-element blacklist — Ctrl+K intercepts while typing in textareas / prompts. Guard on `evt.target.tagName`. *Source: EC-37*
- **D95** Chrome's Ctrl+K focuses the address bar in some locales. Document the collision. *Source: BH-28*
- **D96** Alpine.js spec vs vanilla-JS delivery. Update UX-Spec to allow vanilla. *Source: acceptance-auditor*
- **D97** Palette JSON route has no auth — matches the rest of the app. Single-User-Localhost. *Source: BH-25*

### Query presets / API
- **D98** `save_preset` ON CONFLICT preserves `created_at`. Re-saves stay in their original palette position. Expected but UX-surprising. *Source: BH-23 / EC-21*
- **D99** `window.prompt()` instead of styled Alpine modal. Spec drift. *Source: acceptance-auditor*
- **D100** Migration numbering: spec said `005_query_presets_table.sql`, shipped as `004_query_presets.sql`. Cosmetic. *Source: acceptance-auditor*

### Operational / perf
- **D101** 2000-trade performance test not run (AC 4.1/4.2 NFR-P3/P4). Revisit when dataset grows. *Source: acceptance-auditor*
- **D102** `savePreset` JS is redeclared on every HTMX swap of the journal fragment; CSS duplicates accumulate. Extract to base.html. *Source: BH-40*

---

## Deferred from: code review of Epic 5 (Stories 5.1–5.4) — 2026-04-14

### Fundamental service
- **D103** Concurrent duplicate-fetch race — two `get_fundamental` calls for the same key both miss + both fetch. Add in-flight dedup via `asyncio.Future` keyed on cache_key. *Source: EC-11*
- **D104** `_stale_cache` FIFO prune race — two coroutines could both trigger prune + double-drop. Single-user acceptable. *Source: EC-12*
- **D105** `_stale_cache` prune fires even when the incoming key already exists — wasted drops on re-refresh. *Source: EC-13*
- **D106** `_fresh_caches` is per-process — no cluster coherence. Acceptable for Single-User-Localhost. *Source: BH-2*
- **D107** `_parse_confidence` `&gt; 1.0` ambiguity — `1.5` interpreted as 150% → 0.015 rather than 1.5%. Acknowledge in docstring. *Source: BH-5*
- **D108** `_parse_mcp_response` no size guard on `json.loads(text)` — 10 MB rogue text would allocate freely. Add a size cap if MCP ever misbehaves. *Source: EC-8*
- **D109** `_parse_mcp_response` breaks on first valid JSON, ignoring subsequent content items — a preamble like `{"type":"text","text":"Analysis result:"}` could win over the real payload. *Source: BH-10*
- **D110** `text` as list-of-parts (streaming MCP) is dropped — need nested text-part concat when upstream streams. *Source: EC-9*

### Fundamental snapshots
- **D111** `capture_fundamental_snapshot` re-caches via `get_fundamental`, invalidating true "at-entry-time" semantics. "Damals" is actually "last MCP fetch for this symbol". Acknowledge in story notes. *Source: BH-29, EC-19*
- **D112** Fire-and-forget snapshot task not drained on shutdown — SIGTERM during a live trade loses the snapshot. Add a lifespan-shutdown drain. *Source: BH-14, EC-17*
- **D113** Fire-and-forget burst could saturate the asyncpg pool (max_size=10). Add a semaphore when burst patterns emerge. *Source: EC-18*
- **D114** `as_assessment` fallback swallows exceptions and returns `agent_id=""` — log the reason. *Source: EC-16, BH-37*
- **D115** `fundamental_snapshots.trade_id` has no UNIQUE — duplicate captures could stack on re-upsert. Add unique constraint when Epic 7/8 wiring lands. *Source: EC-49*
- **D116** `get_latest_snapshot` unreachable str-coerce branch — the JSONB codec always returns dict. Remove dead code or convert to assert. *Source: EC-41*

### MCP health + staleness
- **D117** `mcp_health._state` module-level mutable — test fixture scopes resets, but `test_fundamental.py` can pollute via `record_success` side effects. Add cross-module reset. *Source: BH-27, EC-35*
- **D118** `_KNOWN_AGENTS` duplicates `AGENT_NAMES` from `trigger_prose.py` — drift risk. Consolidate. *Source: BH-26*
- **D119** Typo'd agent names (`record_failure("vikto")`) persist forever in banner. Add a "forget unknown" cleanup. *Source: BH-33*
- **D120** `record_success / failure` increments not atomic — two coroutines could lose an increment. Single-User acceptable. *Source: EC-33*
- **D121** Case-sensitivity: `record_success("Viktor")` vs `"viktor"` produces two rows in the banner. Normalize. *Source: EC-30*
- **D122** `record_success/failure` never called on cache-hit path — health state can go stale if banner relies on it for "MCP last touched". Fine today. *Source: BH-32*

### Contract test
- **D123** `diff_contracts` uses strict dict equality — reordered keys / description strings / timestamp fields fire false "changed" alerts. Add a field whitelist or normalization. *Source: BH-22, EC-23*
- **D124** APScheduler wiring for 05:00 UTC daily run — **defers to Story 12.1**. Currently only the on-demand API endpoint exists. *Source: Auditor*
- **D125** Health-widget consumer for contract-test results — **defers to Story 12.2**. *Source: Auditor*
- **D126** `DEFAULT_SNAPSHOT_DIR` resolution fragile when `app/` is moved. Make configurable via settings. *Source: EC-38*
- **D127** `run_contract_test` exception branches catch then re-catch via generic `Exception`. Cosmetic. *Source: BH-17*
- **D128** `_persist_report` expects the JSONB codec; integration tests using raw asyncpg conn without the codec would `DataError`. Route through a helper. *Source: BH-19*
- **D129** Error message text in contract-test JSON response could leak internal exception details. Normalize for log hygiene. *Source: EC-44*
- **D130** `run_contract_test` masks "snapshot missing" vs "snapshot corrupt" under the same error string. *Source: BH-21*

### Drilldown / templates
- **D131** `live.rating.value | upper` renders `UNKNOWN` — confusing to Chef. Render as "—" or "keine Einschätzung". *Source: EC-31*
- **D132** Stale badge has no visual column-header affordance — Chef might miss the small badge. Add border-color accent. *Source: EC-32*
- **D133** Chart / drilldown inline `<style>` duplication on HTMX swap — extract to base.html. *Source: BH-38*
- **D134** HTMX swap of banner spans doesn't trigger screen-reader re-announcement. Low accessibility impact. *Source: EC-47*

### Base context wiring
- **D135** `_base_context` swallows DB probe failures to `contract_drift=None` — a partial DB outage silently hides drift banner. Log + surface degraded state. *Source: EC-28*
- **D136** `_render` and `_base_context` duplicate default dicts — drift risk on future banner additions. Consolidate. *Source: EC-48*

### Command palette + misc
- **D137** Command palette `Ctrl+K` on CapsLock sends `'K'` and misses. Use `.toLowerCase()` on `evt.key`. *Source: EC-39, BH-28*
- **D138** Banner polls every 60s regardless of state — even with all-ok. Log noise + wasted cycles. *Source: BH-24, BH-40*
- **D139** Staleness banner inline `<style>` injected on every 60s poll. Move to base.html. *Source: BH-38*
- **D140** `FundamentalAssessment.thesis` has no max_length — a rogue MCP could submit multi-MB text. Add a cap. *Source: EC-42*
- **D141** `FundamentalResult.model_config frozen=True` doesn't protect nested `extra` dict. Use `MappingProxyType` when freeze matters. *Source: EC-36*
- **D142** Future-dated `cached_at` &gt; 5s logs no warning — just returns the anomaly phrase. Add structlog line. *Source: BH-7 / H8 follow-up*

---

## Deferred from: code review of Epic 6 (Stories 6.1–6.5) — 2026-04-14

### Performance / scaling
- **D143** `list_strategies_with_metrics` loads every strategy-linked trade into Python (no LIMIT). At 50k+ trades it'll bite NFR-P1. Replace the Python aggregation with a SQL `GROUP BY strategy_id` returning sums/counts; pull individual trades only for the selected detail. *Source: BH-5 / EC-39*
- **D144** `strategies_page?selected=` triggers ~3 full-table scans (list, detail, horizon). Combine into a single fetch + Python re-grouping. *Source: BH-6 / EC-38*
- **D145** Per-strategy `_TRADES_BY_STRATEGY_SQL` lacks a `(strategy_id, opened_at)` composite index. *Source: BH-16*

### Accessibility
- **D146** `<tr role="button" tabindex="0">` rows have no Enter/Space keydown handler. *Source: BH-24, EC-29*

### Architectural follow-ups
- **D147** `StrategyFacet` (Epic 4 placeholder) still reads from `trigger_spec->>'strategy'` instead of joining the new `strategies` table. The H1 fix means the JSONB path still works, but the facet should switch to JOIN-and-name once the strategies table is canonical. *Source: EC-2*
- **D148** Migration 007 doesn't backfill existing trades — every pre-Epic-6 trade has `strategy_id = NULL`. Provide a backfill script that matches `trigger_spec->>'strategy'` to `strategies.name`. *Source: EC-3*
- **D149** `ON DELETE SET NULL` on `trades.strategy_id` silently orphans historical trades. *Source: EC-4*
- **D150** No reverse migration / DOWN script for 007. *Source: BH-31*
- **D151** `CREATE INDEX ... ON trades (strategy_id)` is not `CONCURRENTLY` — locks trades on rebuild. *Source: BH-32*
- **D152** `_LIST_SQL ORDER BY CASE status::text` brittle if a future enum label is added. *Source: BH-33*
- **D153** No `updated_at` trigger on strategies. *Source: EC-43*
- **D154** `ALTER TABLE trades ADD COLUMN strategy_id` doesn't validate the FK retroactively. *Source: EC-44*

### Aggregation / metrics
- **D155** Drawdown semantics document the peak-to-trough-from-first-cumulative convention from Epic 4 H3. *Source: BH-7, BH-8, EC-10*
- **D156** "0% winrate" vs "n/a" for all-open strategies — render em-dash. *Source: EC-9*
- **D157** `_followed_breakdown` silently drops trades where `trigger_spec.followed` is missing. No "unknown" bucket. *Source: BH-20, EC-11*
- **D158** `_aggregate_one` and `_followed_breakdown` re-normalize pnl twice per trade. *Source: EC-12*
- **D159** `horizon_aggregates` Python dict iteration relies on SQL sort stability. *Source: EC-14*

### Form / router
- **D160** Validation 422 doesn't re-render the form with values populated. *Source: EC-21*
- **D161** Trigger-sources field collected on create but never displayed in the detail fragment. *Source: EC-37*
- **D162** `typical_holding_period` collected but never displayed. *Source: EC-36*
- **D163** Raw enum strings rendered in templates (`swing_short`). Add taxonomy label lookup. *Source: EC-35*
- **D164** `Decimal → float` conversions in templates — precision loss on large values. *Source: BH-31, EC-31*

### Status badge / UI
- **D165** Retired strategy badge still rendered as a `<button>` — Chef can click but nothing happens. *Source: EC-7*
- **D166** Inline `<style>` blocks in macro files emit on import; HTMX swaps re-inject. Cross-epic CSS extraction follow-up. *Source: BH-25, BH-26, EC-32*
- **D167** Strategy detail trade table renders open trades with `pnl=0` styled as neutral — visually identical to closed-at-breakeven. *Source: BH-32, EC-33*

### Tests
- **D168** No integration tests for any strategy router endpoint. *Source: EC-45*
- **D169** No unit tests for `list_strategies_with_metrics`, `get_strategy_detail`, `_aggregate_one`, `_followed_breakdown`. *Source: EC-46*
- **D170** `is_strategy_active` has no unit test backed by a real DB cycle. *Source: EC-47, EC-50*
- **D171** No test exercising the empty-state path of `strategies.html`. *Source: EC-48*
- **D172** No test for duplicate-name 409 / invalid-status 422 / missing-field 422 unhappy paths. *Source: EC-49*
