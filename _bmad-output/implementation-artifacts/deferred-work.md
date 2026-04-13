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
