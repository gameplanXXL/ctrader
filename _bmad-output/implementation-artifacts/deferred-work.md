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
