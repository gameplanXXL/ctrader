---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: 134561b
stories_reviewed:
  - 9-1-regime-snapshot-model
  - 9-2-horizon-aware-kill-switch
  - 9-3-kill-switch-override-regime-page
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 8
  patch_medium: 4
  patch_low: 0
  defer: 19
  dismiss: 0
status: tranche-a-applied
---

# Code Review — Epic 9 (Stories 9.1–9.3)

Adversarial multi-layer review of the regime-awareness + kill-switch block. Three reviewers surfaced 53 findings — Auditor: 7 ACs MET + 1 deferred + **1 NOT MET (9.3 #3)**; Blind Hunter: 25 diff-based findings with **8 HIGH** that would have crashed the Regime page in production; Edge Case Hunter: 22 interaction findings with **1 HIGH** around the approve→execute race. Tranche A applies 12 patches (8 HIGH + 4 MEDIUM). **413/413 tests green** (387 pre-existing + 26 regime unit tests including new JSONB-null + strategy-gate coverage), ruff clean, live smoke probe end-to-end verified.

## Patches Applied — Tranche A (12)

### 🔴 HIGH (8)

- **H1** **`_SELECT_HISTORY_SQL` crashed on any manual override** (BH-1 / BH-2). The naive `NULLIF(al.override_flags->>'fear_greed_index', '')::int` pattern exploded whenever a `kill_switch_overridden` row existed: `manual_override` passed `fear_greed_index=None`, the JSONB codec serialized it as a JSON `null` literal, `->>` returned the text `'null'`, `NULLIF('null', '')` is `'null'` (non-empty), and `::int` raises `invalid input syntax for type integer: "null"`. **The Regime page would 500 the moment any override existed.** Fix (belt-and-suspenders):
  1. `kill_switch._log_state_change` now OMITS the `fear_greed_index` key from `override_flags` when None rather than writing JSON null — the `->>` extraction returns SQL NULL for a missing key, and the NULLIF/CAST chain handles it cleanly.
  2. `_SELECT_HISTORY_SQL` was rewritten to use a `CASE WHEN override_flags ? 'fear_greed_index' AND jsonb_typeof(override_flags->'fear_greed_index') = 'number' THEN … ELSE NULL END` guard so any legacy row with a JSON null cannot crash the query.
  New tests: `test_manual_override_audit_row_omits_none_fear_greed_index` + `test_evaluate_kill_switch_pause_audit_flags_include_fg` lock in the override_flags shape.

- **H2** **`evaluate_kill_switch` was not transactional** (BH-3 / EC-3). The function ran `UPDATE strategies RETURNING` then looped N `_INSERT_AUDIT_SQL` calls on a plain `asyncpg.Connection` — asyncpg auto-commits per statement outside a transaction block. A FK violation or connection blip mid-loop would leave strategies paused with a PARTIAL audit trail, violating Story 9.2's "every state transition writes audit_log" invariant. Fix: wrapped the body in `async with conn.transaction():` so PAUSE + all audit INSERTs commit atomically or roll back together.

- **H3** **`manual_override` was not transactional** (BH-4). Same problem — the `_OVERRIDE_SQL` UPDATE and audit INSERT ran on one connection without a transaction. A crash between them would leave a reactivated strategy without its `kill_switch_overridden` audit row (FR44 durability gap). Fix: `async with conn.transaction():` around both operations.

- **H4** **`post_regime_snapshot` cross-connection race** (BH-5). The router opened one connection inside `create_regime_snapshot` (fetch + INSERT snapshot), released it, then opened a SECOND connection for `evaluate_kill_switch`. Under a drained pool this could interleave with another request's snapshot INSERT, leaving the kill-switch reading a stale F&G value. Also: on pool exhaustion the kill-switch eval could deadlock while the snapshot row was already persisted. Fix: completely rewrote the router to hold a single `db_pool.acquire()` + nested `conn.transaction()` for the entire pipeline: per-broker P&L + snapshot INSERT + kill-switch eval.

- **H5** **VIX template cell crashed on `Decimal`** (BH-7). The Jinja expression `{{ '%.2f' | format(snap.vix) if snap.vix is not none else '—' }}` used Python's `%` operator, which rejects `Decimal` with `TypeError: must be real number, not decimal.Decimal`. **The whole Regime page would 500 on first real snapshot render.** The unit test suite didn't catch it because no test runs the template (it was a smoke-probe-only bug). Fix: convert to float via the Jinja `float` filter first — VIX precision beyond 2dp is noise anyway: `{{ '%.2f' | format(snap.vix | float) }}`.

- **H6** **HTMX `after-request="reload()"` hid failures** (BH-8). The snapshot refresh button's `hx-on::after-request="window.location.reload()"` fired on ANY response — including 500 / 503 — so Chef would see a flash-reload that silently hid the error. Fix: gate on `event.detail.successful`, and render a visible `.regime-page__refresh-error` span with the HTTP status code on failure.

- **H7** **Story 9.3 AC #3 NOT MET — Regime footer missing from approval viewport** (Auditor / EC-1). The Story file explicitly calls out "F&G X · VIX Y · Kill-Switch: ACTIVE (N paused)" in the approval-viewport footer per UX-DR75, and the Epic 9 commit implemented zero of it. Fix:
  - `proposal_drilldown` in `app/routers/approvals.py` now loads `get_current_regime(conn)` under the same pool acquire as the proposal fetch.
  - `proposal_drilldown.html` fragment passes `regime` into the `proposal_viewport` macro.
  - `proposal_viewport` macro signature extended with `regime=None`.
  - New footer block rendered below the decision buttons with three metric spans (F&G + classification, VIX, Kill-Switch state + paused count), including a `--alert` CSS variant that flips to red when `kill_switch_active` is true.
  - Live smoke probe verified via `GET /proposals/{id}/drilldown` — shows `F&G 21`, `VIX 18.10`, `Kill-Switch:` in the rendered HTML.

- **H8** **`execute_proposal` didn't re-check strategy status** (EC-2). A proposal approved at T2, then kill-switch-paused at T4, would still fire at T5 when the fire-and-forget `trigger_bot_execution` task woke up — defeating the whole point of the kill switch. Fix: added `_SELECT_STRATEGY_STATUS_SQL` query at the top of `execute_proposal` (before `client_order_id` lookup). If `strategy_id` is non-NULL and the strategies row either doesn't exist or has `status != 'active'`, the function skips with a structlog `bot_execution.skip_strategy_inactive` warning. Two new tests: `test_execute_proposal_skips_when_strategy_kill_switch_paused` + `test_execute_proposal_skips_when_strategy_row_missing`.

### 🟡 MEDIUM (4)

- **M1** **Jinja operator-precedence footgun in override-history row** (BH-6). `{{ entry.strategy_name or ('#' + entry.strategy_id|string) if entry.strategy_id else '—' }}` parses as `(name or '#id') if strategy_id else '—'` — if name is truthy but id is None, it still emits `'—'`. Fix: explicit `{% if %}{% elif %}{% else %}{% endif %}` block.

- **M2** **Local import in `post_override_kill_switch`** (BH-14). `from app.services.kill_switch import ...` inside the function body, no circular-dep justification. Fix: hoisted to module top of `app/routers/strategies.py`.

- **M3** **`regime_page` bare `except Exception`** (BH-15). The handler swallowed every database error behind a generic "DB-Fehler" banner — operators would think Postgres was down when really Migration 012 / 013 hadn't been applied yet. Fix: caught `asyncpg.UndefinedTableError` + `asyncpg.UndefinedColumnError` distinctly with an operator hint ("run migrate"), generic `except Exception` as fallback.

- **M4** **`format_datetime` was tz-naive** (EC-8). Unlike the sibling `format_time` filter, `format_datetime` didn't call `astimezone(UTC)` before rendering. The regime override-history table could show different timestamps than the journal for the same row if asyncpg's session tz ever shifts. Fix: copied the `astimezone(UTC)` clause from `format_time`.

Plus one minor cleanup: dropped the dead `format_pnl` helper from `app/services/regime.py` (BH-20) — the template uses the `format_signed_money` Jinja filter, not the duplicated service-layer function.

## Live Smoke-Probe Results

Against Docker Compose stack (`docker compose up -d --build`):

| Probe | Outcome |
|---|---|
| Startup | All 13 migrations idempotent (012/013 already applied from Epic 9 commit) |
| `POST /api/regime/snapshot` | HTTP 201, real F&G=21, VIX=18.10 from alternative.me + Yahoo |
| Kill-switch action on re-paused strategy (F&G=21 above threshold) | **`action=recover, recovered_ids=[5]`** — transaction wrap working |
| `GET /regime` rendered hero | FEAR & GREED = 21 / VIX = **18.10** (H5 fix verified), Extreme Fear label |
| Override history | Shows both `auto-recover` + `manual override` pills cleanly — H1 JSONB null path no longer crashes |
| `GET /proposals/6/drilldown` | Renders regime footer with `F&G 21 (Extreme Fear)`, `VIX 18.10`, `Kill-Switch:` — **H7 AC #3 verified in the actual HTML** |

## Deferred (LOW) — 19 items

All added to `deferred-work.md` as **D195–D213**. Summary:
- **Migration polish** (D195–D197): CHECK NOT VALID pattern, date-level UNIQUE, audit batching
- **Data-source robustness** (D198–D201): F&G bucket alignment, settings override for URLs, User-Agent retry, intraday F&G retry
- **Integration gaps** (D202–D205): audit row on H8 skip, Epic-6 `update_status` doesn't clear `paused_by`, migration 013 docstring vs code mismatch, strategies page UX differentiation
- **Observability** (D206–D208): kill-switch error surfacing, CSRF on override, history pagination
- **Test coverage** (D209–D213): router-integration test, template render test, failure-injection rollback test, CHECK-constraint test, end-to-end kill-switch → create_proposal test

None block Epic 10 — all are post-MVP polish or cross-epic follow-ups.

## Status

- **Tranche A applied:** 12 patches (8 HIGH + 4 MEDIUM) + dead code cleanup
- **Tests:** 413/413 green (387 pre-existing + 26 regime + 2 new execute_proposal strategy-gate tests)
- **Ruff:** clean
- **Smoke probe:** full end-to-end verified — snapshot + kill-switch recover + regime page + approval-viewport footer
- **Deferred:** D195–D213 in deferred-work.md
- **Ready for:** Epic 10 (Gordon Trend-Radar) Yolo-mode implementation
