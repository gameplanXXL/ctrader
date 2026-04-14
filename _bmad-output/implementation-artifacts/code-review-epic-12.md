---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: f5b6e3a
stories_reviewed:
  - 12-1-quick-order-form-stock-and-option
  - 12-2-confirmation-bracket-order-fixed-stop
  - 12-3-order-status-tracking-near-assignment
  - 12-4-error-handling-transient-terminal
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 14
  patch_medium: 3
  patch_low: 0
  defer: 19
  dismiss: 0
status: tranche-a-applied
---

# Code Review — Epic 12 (IB Swing-Order, Stories 12.1–12.4)

Adversarial multi-layer review of the Quick-Order pipeline (stock + single-leg option) against commit `f5b6e3a`. Three reviewers surfaced **~73 findings** total:
- **Auditor**: 20 ACs — 11 MET, 3 PARTIALLY MET, 4 DEFERRED, 1 NOT MET. 3 BLOCKING.
- **Blind Hunter**: 25 findings, 6 HIGH (1 CRITICAL silent correctness bug).
- **Edge Case Hunter**: 28 findings, 10 HIGH.

Tranche A applies **17 patches** (14 HIGH + 3 MEDIUM) plus a taxonomy-yaml addition for the new `quick_order` trigger_type. **483/483 tests green** (479 pre-existing + 4 new Tranche A tests), ruff clean, end-to-end smoke probe verified including orphan-row sweep, wrong-side stop rejection, DTE floor enforcement, and the live Health-Widget dot for IB Quick-Order.

## Patches Applied — Tranche A (17)

### 🔴 HIGH (14)

- **H1 BH-5 (CRITICAL silent correctness) — Duplicate `name` attributes leaked stock values into option submissions.** The stock-mode and option-mode field groups shared `name="quantity" | limit_price | stop_price"`. Alpine's `x-show` only toggles `display:none`; hidden inputs still submit, and Starlette returns the FIRST match from the form dict — so every option submission silently carried the stock-mode values. Fix: bind `:disabled="mode !== 'stock'"` (resp. `'option'`) on every numeric + radio + select in the inactive section so the HTML-spec "don't submit disabled inputs" rule keeps exactly one section on the wire. `quick_order_form.html:58-127`.

- **H2 BH-3 + Auditor 12.1 #6 — Wrong-side Stop-Loss not rejected.** `_parse_form` only enforced `> 0` on stop_price. For BUY the stop must be BELOW limit (stop-out on downside); for SELL the stop must be ABOVE. Fix: added side-aware comparison with German operator messages. Live probe: `stop=210, limit=200, side=BUY` now returns the error fragment `"Stop-Loss muss unter dem Limit-Preis liegen (BUY)"`.

- **H3 BH-4 + Auditor 12.1 #6 — Missing minimum-5-DTE guard.** Spec says options ≥ 5 DTE so near-assignment scenarios land in the post-hoc taxonomy path, not the Quick-Order path. Previously any expiry was accepted. Fix: `_parse_form` now rejects `dte < 5` with the message `"Option-Expiry {iso} ist {dte} DTE — Minimum 5 DTE (unter 5 Tagen ist near-assignment)"`. Live probe: `expiry=today+2d` returns the error fragment.

- **H4 BH-1 + EC-15 — Orphan `quick_orders` rows on mid-submit crash.** `submit_quick_order` persists BEFORE the network call (correct for NFR-R3a idempotency), which means a crash between the INSERT and `place_bracket_order` leaves a row in `status='submitted'` with `ib_order_id=NULL` forever. Fix: new `sweep_orphan_quick_orders(conn)` marks any such row older than 5 minutes as `rejected`. Wired into `app/main.py` lifespan BEFORE scheduler start, next to `sweep_stranded_jobs` (Epic 11 H5 pattern). Live probe: inserted a `created_at = NOW() - 10 min` row, restarted the service, row flipped to `rejected`. Logs: `{"count": 1, "ids": [4], "event": "ib_quick_order.sweep_orphans"}`.

- **H5 BH-6 — `_RETRYABLE_EXCEPTIONS` listed `IBTransientError` AND `ConnectionError`.** Redundant — `IBTransientError` subclasses `ConnectionError`. Same pattern Epic 8 BH-1 caught. Fix: dropped `ConnectionError`, kept `TimeoutError` (asyncio socket deadline).

- **H6 EC-16 — `handle_fill_event` status update + trade INSERT not transactional.** The UPDATE at `quick_orders.status='filled'` and the `trades` INSERT were two separate statements with no `async with conn.transaction()` wrapper. On INSERT failure (constraint, disk), `quick_orders.status='filled'` would exist with no matching `trades` row — invariant "every filled quick_order has a trade" broken. Fix: wrapped both in a single transaction. The logging branch (trade_dedup vs trade_created) moved outside the transaction so side-effects don't rollback.

- **H7 EC-8 — `horizon='swing'` was not a canonical taxonomy value.** `HORIZON_LABELS` has `{intraday, swing_short, swing_long, position}` — no `swing` key. Quick-Order defaulted to the literal `"swing"`, which rendered as the raw string in the drilldown and broke the Horizon facet filter. Fix: default is now `"swing_short"` (Chef's IB Swing-Order product is ~5-20 DTE, short-swing). Verified via fresh stock submit: `trade.trigger_spec.horizon = "swing_short"` (row id 18).

- **H8 EC-7 — `trigger_prose.PATTERNS` had no `quick_order` entry.** Quick-Order rows fell through to `DEFAULT_PATTERN` and rendered `"Unbekannt Unbekannt — Unbekannt."` Fix: added pattern `"Chef {side_de} {symbol} per Quick-Order ({horizon_label})."` + added `quick_order` to `taxonomy.yaml trigger_types` so the `test_pattern_catalogue_has_no_dead_patterns` invariant holds.

- **H9 EC-10 — No regime kill-switch context in the form.** FR42 exempts manual IB Quick-Orders from the kill-switch (correct), but Chef had no visibility that the crypto/CFD bots were paused while he was typing in the form. Fix: `quick_order_form` handler now probes `get_current_regime(conn).kill_switch_active` and the template renders a yellow informational banner `"⚠ Regime-Kill-Switch aktiv — Crypto/CFD-Bots pausiert. IB Swing-Order bleibt manuell freigegeben (FR42)."` Submit stays enabled — the banner is informational only.

- **H10 EC-11 — Health-Widget IB dot conflated live-sync with Quick-Order client.** `_ib_status` tracked Story 2.2's `connect_ib` handshake. The `ib_quick_order_client` was a SEPARATE wiring that always returned `StubIBQuickOrderClient`. Two failure modes: (a) TWS running → live-sync green but Quick-Order still stub; (b) TWS offline → live-sync grey but stub `is_connected()=True` so submit was "live". Fix: new `_ib_quick_order_status(ib_quick_order_client)` with `isinstance(StubIBQuickOrderClient)` check (same pattern as `_ctrader_status`). Added a 4th dot to the health widget (`health_widget.html`). Live probe: `/api/health` returns `health-dot--yellow` with `"IB Quick-Order: stub (real ib_async adapter pending)"`.

- **H11 EC-1 — `trade_query._LIST_SQL` / `_DETAIL_SQL` did NOT SELECT Migration 019's option columns.** The 4 columns (`option_expiry`, `option_strike`, `option_right`, `option_multiplier`) were write-only. Every drilldown for an option trade silently lost them. Fix: added all 4 columns to both SELECT lists.

- **H12 EC-2 + Auditor 12.3 #5 — `trade_detail.html` never rendered option metadata.** Even after the SELECT was fixed, the drilldown dl block had no reference to the option columns — Chef couldn't identify the contract beyond the symbol. Fix: new conditional block (Right / Strike / Expiry / DTE / Multiplier). `option_dte` is computed in the router (`_date.today() - expiry`) so no Python import leaks into Jinja. Live probe on trade #16 (`SPY 450 P 2026-05-15`): renders `Put · 450.00 · 2026-05-15 · 31 DTE · ×100`.

- **H13 EC-3 — Quick-Order trades never captured a Fundamental snapshot.** `ib_live_sync.handle_execution` fires `_capture_snapshot_fire_and_forget` on every new IB trade; `_on_quick_order_fill` in `main.py` did NOT. Drilldown for a Quick-Order option → "Damals" column always empty. Fix: the handler now captures the trade_id from `handle_fill_event`'s return, fetches `symbol + asset_class` from the fresh `trades` row, and calls `capture_fundamental_snapshot` with a new pooled connection. Errors swallowed + logged at WARNING (same fire-and-forget contract as Epic 8 H8).

- **H14 Auditor 12.4 + BH-2 — Inconsistent error response shapes.** The submit path returned `HTTPException(422, detail=str)` for parse failures AND `QuickOrderSubmitError`, producing JSON 422 for HTMX targets expecting HTML. Fix: new `components/quick_order_error.html` fragment + `_render_error_fragment()` helper. All user-correctable errors (parse failures, `QuickOrderSubmitError`, disconnected client) now render the fragment into `#quick-order-preview-slot` with `HX-Retarget` + `HX-Reswap` headers. Addresses Auditor 12.1 #6 (inline validation) AND 12.4 #2/#4 (error_toast fragment). Live probe: wrong-side stop returns HTML fragment with the German message and the error styling.

### 🟡 MEDIUM (3)

- **M1 EC-17 — German-message leak on terminal IB errors.** `submit_quick_order` re-raised `IBTerminalError` as `QuickOrderSubmitError(str(exc))`, which surfaced the English stub message `"No option chain for symbol ..."` instead of the German catalog entry. Fix: route through `format_for_operator(exc.error_code)` when `error_code` is set, fall back to `exc.german_message` otherwise. Consistent German UI.

- **M2 H14 follow-up — Starlette `HTTP_422_UNPROCESSABLE_ENTITY` deprecation.** Modern Starlette renamed to `HTTP_422_UNPROCESSABLE_CONTENT`. Guarded import with try/except so both old and new Starlette versions work.

- **M3 EC-8 follow-up — Added `quick_order` to `taxonomy.yaml` trigger_types.** Without this, `test_pattern_catalogue_has_no_dead_patterns` would fail as soon as `PATTERNS['quick_order']` was added — the invariant is that every pattern key is a real taxonomy id.

## Live Smoke-Probe Results

Against Docker Compose stack:

| Probe | Outcome |
|---|---|
| Rebuild + restart | `Container ctrader-ctrader-1 Started` |
| `/healthz` | `{"app":"ctrader","version":"0.1.0","status":"ok"}` |
| `/api/health` (4 dots) | IB grey / IB Quick-Order yellow (stub) / cTrader yellow (stub) / MCP grey |
| Submit happy-path stock (AAPL / BUY / 10 / 200 / 190) | `HTTP 201` — new row in `quick_orders` + `trades` with `trigger_spec.horizon='swing_short'` (row id 18) |
| BH-3: stop on wrong side (stop=210, limit=200, BUY) | error fragment `"Stop-Loss muss unter dem Limit-Preis liegen (BUY)"` |
| BH-4: option at expiry=today+2d | error fragment `"Option-Expiry 2026-04-16 ist 2 DTE — Minimum 5 DTE"` |
| EC-1/EC-2: option drilldown for trade 16 | renders `Put · 450.00 · 2026-05-15 · 31 DTE · ×100` |
| BH-1/EC-15: orphan sweep | inserted row at `created_at = NOW() - 10 min, status='submitted', ib_order_id=NULL`; restart flipped it to `rejected`; log `{"count": 1, "ids": [4], "event": "ib_quick_order.sweep_orphans"}` |
| `GET /trades/quick-order/form?symbol=AAPL` | renders form with Stock tab active, `ib_connected=True` (stub), kill-switch banner absent (no active kill-switch) |
| `pytest tests/ -q` | `483 passed, 55 warnings in 4.22s` |
| `ruff check app/ tests/` | `All checks passed!` |

## Deferred (HIGH + MEDIUM + LOW)

All added to `deferred-work.md` as **D250–D268**. Summary of HIGHs NOT patched in this tranche:

- **D250 EC-4** — `Trade` Pydantic model doesn't carry option metadata. Safe today (`extra="ignore"` default), fragile for future hydration callers.
- **D251 EC-5** — Real `ib_async` adapter double-insert risk (Quick-Order raw INSERT vs live-sync `upsert_trade`). Only matters when real adapter lands; stub is fine.
- **D252 EC-6** — Partial-fill accumulation. The comment explicitly says partials don't create trades; real adapter will need `partial_filled_qty` columns.
- **D253 EC-9** — `submit_quick_order` doesn't validate strategy is active. FR42 manual-exempt, but an "ACHTUNG: paused strategy" warning banner in the preview would help.
- **D254 EC-20** — Short-Option `side='SELL'` vs `TradeSide.SHORT`. P&L formulas may misinterpret. Needs P&L semantics decision before touching.
- **D255 EC-18** — `10318 = Margin-Fehler` code is likely fabricated; real IB codes are `201` + text pattern match. Harmless until real adapter.

Plus 13 LOW items: test gaps (D256-D262), taxonomy rename safety (D263), Alpine global-keydown conflict (D264), `tojson` brittleness (D265), fragment size audit (D266), `near-assignment` daily cron (D267), source-value taxonomy doc (D268).

## Status

- **Tranche A applied:** 17 patches (14 HIGH + 3 MEDIUM) + taxonomy.yaml entry
- **Tests:** 483/483 green (479 pre-existing + 4 new Tranche A tests)
- **Ruff:** clean
- **Smoke probe:** end-to-end verified — form → validation → submit → persist → fill → trade → drilldown
- **Deferred:** D250–D268 in deferred-work.md
- **Ready for:** MVP Pipeline wrap-up (Task #84) — remaining Chef decisions: D214 (Gordon trend_radar tool) + D232 (IB Flex Nightly cron) from earlier epics.
