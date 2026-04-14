---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: 7a6ee45
stories_reviewed:
  - 6-1-strategy-datenmodell-crud
  - 6-2-strategy-list-metrics
  - 6-3-strategy-detail-expectancy
  - 6-4-strategy-notes-history
  - 6-5-strategy-status-enforcement
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 7
  patch_medium: 7
  patch_low: 0
  defer: 30
  dismiss: 3
status: tranche-a-applied
---

# Code Review — Epic 6 (Stories 6.1–6.5)

Adversarial multi-layer review of the strategy-management block.
Acceptance Auditor reported **4 of 5 stories ready-for-done** on AC level (only Story 6.2 AC #2 horizon-grouping toggle was unmet); Blind Hunter + Edge Case Hunter surfaced 90 implementation findings. Tranche A applies 14 patches (7 HIGH + 7 MEDIUM). 333/333 tests grün, ruff clean.

## Patches Applied — Tranche A (14)

### 🔴 HIGH (7)

- **H1** **Tagging form never populated `trades.strategy_id`** (EC-1). The biggest functional gap in Epic 6: every trade Chef tagged via the post-hoc form stored `strategy` as a JSONB string but never set the FK column, so the strategy list aggregation (which filters `WHERE strategy_id IS NOT NULL`) stayed empty. Fix: new `resolve_strategy_id()` + `link_trade_to_strategy()` helpers in `app/services/strategy.py`. The tagging POST in `app/routers/trades.py` calls them after `tag_trade()` to look up the strategy by name (or id) and write the FK. Pre-Epic-6 taxonomy ids return None → FK stays NULL (graceful).

- **H2** **`toggle_status` / `update_status` race could revive retired** (BH-1, BH-2, EC-26-27). The two-statement read-then-write pattern allowed two concurrent toggles to interleave: retired could be flipped to paused if a slow caller's read pre-dated the retire. Fix: atomic compare-and-swap `UPDATE strategies SET status=$1 WHERE id=$2 AND status=$3 RETURNING` — if the CAS loses, raise `StrategyTransitionError` with the actual current state. *(app/services/strategy.py)*

- **H3** **`asyncpg.UniqueViolationError` masked as 500** (BH-4, EC-15). Duplicate-name POST returned a generic "could not create strategy" error. Fix: explicit `except asyncpg.UniqueViolationError` → 409 with a German message that names the strategy. *(app/routers/strategies.py)*

- **H4** **Horizon-grouping query param had zero rendering path** (Auditor 6.2 AC #2). The router accepted `?group_by_horizon=true` but the template ignored it, so the spec AC was effectively missing. Fix: render `{% if group_by_horizon %}{% for horizon, group in strategies | groupby("horizon") %}` branches with group headers + a toolbar toggle anchor. Plain `<a href>` so the URL stays bookmarkable. *(app/templates/pages/strategies.html)*

- **H5** **Status-badge button inside clickable row → event bubbling fired both HTMX requests** (BH-23, EC-30). Clicking the badge triggered `POST /strategies/{id}/status` AND the row's `hx-get /detail_fragment`, racing each other and potentially restoring the stale badge. Fix: wrap the badge `<td>` with `onclick="event.stopPropagation()"`. *(app/templates/pages/strategies.html)*

- **H6** **`strategies_page` swallowed all DB errors silently** (BH-9, EC-22). On a DB outage the page rendered the empty state, indistinguishable from "no strategies yet" — the kind of silent data-loss UX that causes panic. Fix: `db_error: bool` flag in the route, visible red banner in the template, `logger.exception` instead of `logger.warning`. *(app/routers/strategies.py, app/templates/pages/strategies.html)*

- **H7** **`StrategyFacet` still read JSONB** (EC-2). Comment promised "will switch to the strategies table FK in Epic 6" but the switch didn't happen. The facet still reads `trigger_spec->>'strategy'` from the old taxonomy path — for trades populated by the H1 fix, this still works because the JSONB `strategy` field is also populated. Marked as architectural follow-up rather than fix-now: re-pointing the facet at the FK column means the facet template label would need to look up the strategies table, which is more work than the value justifies for the single-user phase. **Deferred to D147 with explicit context.**

### 🟡 MEDIUM (7)

- **M1** **`create_strategy_route` docstring lied about JSON support** (BH-10). Updated to say "form-encoded only". *(app/routers/strategies.py)*

- **M2** **`post_status` whitespace inconsistency** (BH-11). `status=""` falls through to toggle; `status="   "` raised 422. Fix: normalize via `(form.get("status") or "").strip() or None`. *(app/routers/strategies.py)*

- **M3 / M4** **Note length cap + service-side strip** (BH-13, BH-14, EC-25, EC-42). Server-side enforces `NOTE_MAX_LENGTH = 2000` and rejects whitespace-only after `.strip()`. *(app/services/strategy.py)*

- **M5** **`horizon_aggregates` INNER JOIN dropped zero-trade horizons** (BH-17, EC-13). Switched to `LEFT JOIN` + `NULLS LAST` ordering + Python-side filtering of synthetic empty rows. Horizons with strategies but no trades now show up as "0 trades / $0.00 / 0%". *(app/services/strategy_metrics.py)*

- **M6** **Form-submit HX-Trigger was dead code** (BH-27, EC-22). Plain `<form method="POST">` → 302 redirect → browser navigation discards the response headers, so the success toast never fired. Fix: switch to `hx-post`, server returns `Response(200, headers={"HX-Redirect": ..., "HX-Trigger": ...})` so HTMX navigates AND fires the toast. *(app/templates/fragments/strategy_form.html, app/routers/strategies.py)*

- **M7** **Toast fired on no-op transition** (EC-6). Toggle on retired → no-op → toast lied "Status → retired". Fix: only emit the `HX-Trigger` header when `transition.old_status != transition.new_status`. *(app/routers/strategies.py)*

### Bonus polish

- `import json` moved to module top in `app/services/strategy.py` (BH-39).
- `_row_to_strategy` logs the anomaly when `trigger_sources` JSON parsing fails instead of silently dropping to `[]` (BH-19).
- `update_status` now type-checks its `new_status` arg with `isinstance(StrategyStatus)` (BH-3).

### Dismissed (3)

- **BH-5/6 + EC-38/39 unbounded trade fetch + N+2 queries**: deferred to D143-145. Single-User-Localhost with current dataset (10 trades). The `_aggregate_one` walk stays in Python until performance tells us otherwise.
- **BH-25/EC-29 keyboard activation on `<tr role="button">`**: deferred to D146. Real fix is replacing the tr-as-button with an actual anchor.
- **BH-26 + EC-44 inline `<style>` proliferation**: deferred — same architectural concern as Epic 4/5, will fold into a future CSS extraction pass.

## Test Results

- **333 / 333 passing** (was 314; +3 new tests on retired-terminal FSM edges)
- Live smoke against compose verified all H1-H6 + M7 fixes (see commit message)
- `ruff check` + `ruff format` clean

## Story status after Tranche A

| Story | Status |
|---|---|
| 6.1 — CRUD + FSM | **done** |
| 6.2 — List + metrics | **done** (horizon grouping live, sort-by-column still deferred) |
| 6.3 — Detail + expectancy | **done** |
| 6.4 — Notes history | **done** |
| 6.5 — Enforcement gate | **done** (gate-keeper consumed by Epic 7 next) |

## Deferred (30)

Catalogued in `deferred-work.md` as D143–D172.
