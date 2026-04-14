---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: f014a4b
stories_reviewed:
  - 8-1-ctrader-client-execution
  - 8-2-execution-status-tracking
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 10
  patch_medium: 5
  patch_low: 0
  defer: 14
  dismiss: 0
status: tranche-a-applied
---

# Code Review — Epic 8 (Stories 8.1–8.2)

Adversarial multi-layer review of the bot-execution block. Three reviewers surfaced **58 findings** total (Auditor: 1 NOT MET AC + 4 medium recommendations; Blind Hunter: 25 diff-based findings with 6 HIGH; Edge Case Hunter: 28 interaction findings with 6 HIGH). Tranche A applies 15 patches (10 HIGH + 5 MEDIUM) landing in two hot spots — `app/services/bot_execution.py` (major rewrite) and the journal-visibility layer (`trade_row.html` + new `AgentFacet`). **387/387 tests green** (344 pre-existing + 23 rewritten bot_execution + 20 integration), ruff clean, live smoke-probe end-to-end verified against docker compose.

## Patches Applied — Tranche A (15)

### 🔴 HIGH (10)

- **H1** **Fire-and-forget `asyncio.create_task` had no strong reference → GC hazard** (BH-2 / EC-1). `app/routers/approvals.py::post_approve` stored the returned Task nowhere. Python's own docs warn: *"a task whose only reference is held by the event loop can be garbage-collected mid-execution"* — and Chef would get a 200 on approve with no order actually placed. Fix: new `spawn_bot_execution()` factory in `bot_execution.py` that registers each task in a module-level `_background_tasks: set[Task]` with an `add_done_callback(discard)` callback — mirroring `ib_live_sync.py`'s Story-2.2 pattern. Router now calls the factory instead of raw `asyncio.create_task`.

- **H2** **`client_order_id` race-recovery re-fetch could return None → `place_order(None)`** (BH-3 / EC-3). After a lost `UPDATE ... WHERE client_order_id IS NULL`, the refetch path assumed a winner existed — but if the proposal row was deleted between SELECT and UPDATE (admin rollback), the refetch returns None and we'd pass None to `_proposal_to_request` + `place_order`. Fix: explicit `if client_order_id is None: return None` guard after the race-recovery refetch, plus a structlog `client_order_id_race_lost` warning for triage.

- **H3** **`place_order` success could regress `execution_status` filled → submitted** (BH-4). Scenario: execute_proposal sends to cTrader → stub emits FILLED event via the event handler → handler writes `execution_status='filled'` → execute_proposal's completion UPDATE then overwrites it back to 'submitted'. Fix: split the SQL into `_UPDATE_EXECUTION_STATUS_PRELIMINARY_SQL` (used by execute_proposal, CAS'd with `AND (execution_status IS NULL OR execution_status = 'submitted')`) and `_UPDATE_EXECUTION_STATUS_EVENT_SQL` (used by handle_execution_event, accepts any status). Preliminary CAS miss is logged as `bot_execution.place_order.cas_miss` with an explanatory hint, not an error.

- **H4** **`build_ctrader_client` misled operators about configured credentials** (BH-5 / BH-6). The factory had a dead `None`-guard in main.py and logged `app.ctrader_disabled` even when the stub was actually being used, and fell through both branches to the same `StubCTraderClient` return. Fix: factory now returns a concrete client always (annotation `CTraderClient`, no `| None`), logs at WARN level when credentials ARE set (so an accidentally-live-config doesn't silently hit the stub) vs INFO for the default dev case, and the main.py `is not None` dead branch is removed.

- **H5** **JSONB `||` shallow-merge silently overwrote event history** (BH-11). The previous `COALESCE(execution_details, '{}'::jsonb) || $2::jsonb` overwrote same-named top-level keys on every event — so `place_order_result` disappeared as soon as the FILLED event landed. Fix: store events under a `history` array via `jsonb_set(..., '{history}', existing || jsonb_build_array($2), true)` so every transition is preserved and time-ordered. Live smoke-probe verified: `jsonb_array_length(execution_details->'history') == 2` after approve+fill, with `first_kind='place_order_result'` + `second_kind='execution_event'`.

- **H6** **`trigger_spec` not enriched → journal facet / prose rendered "Unbekannt" for every bot trade** (EC-2 / EC-9). `handle_execution_event` copied the proposal's `trigger_spec` verbatim, but the proposal's `horizon` / `agent_id` / `asset_class` live in typed columns — never merged into the JSONB. Every cTrader bot trade surfaced in the journal with an empty horizon chip and an "Unbekannt kaufte Unbekannt (Unbekannt, Confidence Unbekannt%)" prose line. Fix: new `_enrich_trigger_spec(row)` helper merges the proposal's typed columns into the dict before the INSERT, with defaults `trigger_type='bot_auto'`, `source='bot_execution'`. Smoke-probe verified: bot trade 15's trigger_spec now contains all 6 expected keys.

- **H7** **`side` mapping lost `SHORT` / `COVER` info** (BH-7 / EC-5). The previous `"BUY" if side.value == "buy" else "SELL"` silently collapsed the 4-value `TradeSide` enum. `COVER` (close a short position) was mapped to `SELL` — the exact opposite of the correct cTrader direction (close a short = BUY). Fix: explicit `_SIDE_TO_CTRADER: {"buy":"BUY","cover":"BUY","sell":"SELL","short":"SELL"}` dict. Unit test `test_execute_proposal_supports_short_and_cover_sides` asserts both cases.

- **H8** **No fundamental snapshot captured on bot trades → Migration 005's invariant violated** (EC-6). Migration 005 explicitly documents *"populated by the live-sync hook AND by Epic 7/8 on bot-order placement"* and `ib_live_sync.upsert_trade` fires `capture_fundamental_snapshot` via a tracked task. Epic 8's bot path did NOT — the Story-5.2 drilldown's "damals vs jetzt" side-by-side was always empty for bot trades. Fix: port the `ib_live_sync._capture_snapshot_fire_and_forget` pattern into `bot_execution.py`; `handle_execution_event` now accepts optional `db_pool` + `mcp_client` kwargs, main.py's lifespan passes both into the `_on_execution_event` closure.

- **H9** **Retry exception tuple had overlapping / aliased types** (BH-1). `_RETRYABLE_EXCEPTIONS` listed both `CTraderTransientError` AND `ConnectionError` — but the former is a subclass of the latter, so the first entry was dead. `asyncio.TimeoutError` is a 3.11+ alias for builtin `TimeoutError`, so using the alias risks shadowing if asyncio ever splits them. Fix: drop `CTraderTransientError` (still caught via its `ConnectionError` base), use `TimeoutError` directly.

- **H10** **Story 8.2 AC #3 NOT MET** (Auditor). The AC requires: *"Given einen Bot-Trade im Journal, When der Status-Indikator angezeigt wird, Then reflektiert er den aktuellen Execution-Status mit passendem status_badge"*. The Epic 8 commit plumbed `trades.agent_id` into the database but never wired it into the journal UI. Fix:
  - `_LIST_SQL` / `_DETAIL_SQL` in `app/services/trade_query.py` now SELECT `agent_id` and `strategy_id`
  - `app/templates/components/trade_row.html` renders a `🤖 {agent_id}` badge in the Broker cell when `trade.agent_id` is non-NULL
  - New `app/services/facets/agent.py::AgentFacet` registered in `registry.py` with synthetic value `bot:any` for the "nur Bot-Trades"-Filter the AC also called out
  - `test_facets.py` updated for the new 9-facet registry order
  - Live smoke-probe verified: `GET /journal?agent=bot:any` returns only bot rows, each with `<span class="bot-badge">🤖 satoshi</span>`

### 🟡 MEDIUM (5)

- **M1** **`trigger_bot_execution` failure had no audit trail** (EC-12). A lost background task or a broken pool meant the operator's only signal was a single WARN structlog line — Chef's approve had already returned 200. Fix: on exception, `trigger_bot_execution` now opens a second pool connection and writes an `audit_log` row with `event_type='proposal_revision'` (reusing the Migration 009 closed-vocab; a dedicated `bot_execution_failed` value is deferred as D189) and `notes='bot_execution_failed: {exc}'`. Chef can query it from Story 12.2's future log viewer. Test: `test_trigger_bot_execution_writes_audit_log_on_failure`.

- **M2** **`_SELECT_PROPOSAL_BY_CLIENT_ORDER_ID_SQL` had 15 dead columns** (BH-17). The query pulled 22 columns of which `handle_execution_event` only read 7 + `horizon` (for H6 enrichment). Fix: pruned to the 8 actually-used columns.

- **M3** **Dead `isinstance(str)` branch on `row["trigger_spec"]`** (BH-15 / EC-16). The JSONB codec in `app/db/pool.py::init_connection` already decodes JSONB to dicts on read, so the defensive str→dict branch was dead and the `import json` was unused. Fix: the `_enrich_trigger_spec` helper writes cleanly against a dict; branch + import removed.

- **M4** **`_UPDATE_EXECUTION_STATUS_SQL` had no `status='approved'` guard** (EC-21). Consistent-with-Epic-7 hardening — an admin that flips a proposal from approved → rejected while execution is in flight should not get its `execution_details` overwritten. Fix: both preliminary and event variants of the SQL now include `AND status='approved'`.

- **M5** **`trade_created` log fired with `trade_id=None` on ON CONFLICT dedup** (BH-19). The `RETURNING id` combined with `ON CONFLICT DO NOTHING` returns no row on conflict, and the code logged `trade_created` with `trade_id=None` anyway — misleading on a replay. Fix: conditional split — `trade_id is None` now logs `bot_execution.trade_dedup` with an explanatory hint, only the actual-insert path logs `trade_created`.

## Live Smoke-Probe Results

Against Docker Compose stack (`docker compose up -d --build`):

| Probe | Outcome |
|---|---|
| Startup | All 11 migrations idempotent, `app.ctrader_stub_default` logged at INFO (correct for no-credentials dev) |
| `POST /proposals/5/approve` (pre-seeded with `risk_gate_result='green'`) | HTTP 200 |
| Background task | structlog `bot_execution.place_order.ok` → 50ms later `bot_execution.trade_created` trade_id=15 |
| `SELECT jsonb_array_length(execution_details->'history')` | **2** (was 1-with-overwrite pre-fix) |
| `history->0->>'kind'` | `place_order_result` |
| `history->1->>'kind'` | `execution_event` |
| `trades WHERE agent_id='satoshi'` | trade 15, perm_id=stub-f1170ce893b6, trigger_spec contains all 6 enrichment keys |
| `GET /journal?agent=bot:any` | HTTP 200, renders only bot rows each with `<span class="bot-badge">🤖 satoshi</span>` |

## Deferred (LOW) — 14 items

All added to `deferred-work.md` as **D181–D194**. Summary:
- **Stub / adapter** (D181–D184): real OpenApiPy adapter, partial-fill VWAP accumulation (needs real cTrader event semantic verification), aclose exception suppression scope, stub market-order price-zero fragility
- **Models / queries** (D185–D188): `_GET_SQL` missing execution columns for drilldown visibility, `Trade` Pydantic model missing `agent_id` / `strategy_id` attrs, aggregation queries not filtering by `agent_id`, `trades.horizon` vs `proposals.horizon` asymmetry
- **Observability / ergonomics** (D189–D191): dedicated `bot_execution_failed` audit event_type (needs migration), shutdown-ordering drain for real adapter, production-mode stub-refuse gate
- **Test coverage** (D192–D194): router-integration test for `post_approve` → `spawn_bot_execution`, concurrent-approve TOCTOU real-DB test, Migration 011 UNIQUE constraint integration test

None block Epic 9 — all are post-MVP polish or post-spike follow-ups.

## Status

- **Tranche A applied:** 15 patches (10 HIGH + 5 MEDIUM)
- **Tests:** 387/387 green (344 pre-existing unit + 23 bot_execution + 20 integration)
- **Ruff:** clean
- **Smoke probe:** full end-to-end verified (approve → bot execution → trade row → journal render)
- **Deferred:** D181–D194 in deferred-work.md
- **Ready for:** Epic 9 (Regime-Awareness & Kill-Switch) Yolo-mode implementation
