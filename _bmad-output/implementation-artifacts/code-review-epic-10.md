---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: d031c5a
stories_reviewed:
  - 10-1-gordon-weekly-fetch
  - 10-2-gordon-diff-hot-picks
  - 10-3-strategy-candidate-from-hot-pick
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 1  # D214 cross-project contract gap
  patch_high: 8
  patch_medium: 6
  patch_low: 0
  defer: 18
  dismiss: 0
status: tranche-a-applied
---

# Code Review — Epic 10 (Stories 10.1–10.3)

Adversarial multi-layer review of the Gordon Trend-Radar block. Three reviewers surfaced ~60 findings total — Auditor: 7 ACs MET + 1 DEFERRED + 1 partial + 0 NOT MET; Blind Hunter: 25 diff-based findings with 5 HIGH-severity bugs that would have 500'd the Trends page on first real data; Edge Case Hunter: 26 interaction findings with 3 HIGH including one CROSS-PROJECT contract gap (D214) that Chef needs to make a decision on. Tranche A applies 14 patches (8 HIGH + 6 MEDIUM). **438/438 tests green** (413 pre-existing + 25 Gordon unit tests including new malformed-pick + null-error + horizon-keyed diff coverage), ruff clean, live smoke probe verified.

## Chef-facing decision: D214 — fundamental MCP contract gap

**This is blocking for Story 10.1 real-data operation.** `/home/cneise/Project/fundamental` currently exposes only `crypto`, `fundamentals`, `news`, `price`, `search` tools. The Epic-10 implementation hits `trend_radar` with `arguments={"agent": "gordon"}` — neither the tool nor the agent-routing convention exists on the MCP side. Grep of the entire `/home/cneise/Project/fundamental/src` for `trend_radar`, `hot_picks`, `gordon` returns zero hits.

The Epic-10 always-write contract handles this gracefully — every snapshot row is persisted with `source_error="mcp_error: ..."` and the Trends page shows an "MCP-Fetch-Fehler" banner — but in production Chef would see an empty HOT-picks list forever until he decides either:

1. **Build a `trend_radar` tool on the fundamental MCP side**. Likely the right long-term move per CLAUDE.md's "MCP-Contract frozen at Woche 0" and "Reusable Libraries via MCP" guidance.
2. **Point Story 10.1 at a different data source**: a scheduled scraper of Gordon's public blog, a CSV drop, etc. `_GORDON_TOOL_NAME` + `fetch_gordon_trend_radar` are the single-point-of-change — swap in an httpx scraper and the rest of the pipeline (diff, template, strategy linkage) stays unchanged.

A TODO block above `_GORDON_TOOL_NAME` in `app/services/gordon.py` documents this decision point with full context. **Until Chef decides, Epic 10 is feature-complete but non-functional for real data.**

## Patches Applied — Tranche A (14)

### 🔴 HIGH (8)

- **H1** **`"error" in response` false-positive on `{"error": null}`** (BH-3). MCP JSON-RPC responses can legitimately contain `{"error": null, "result": {...}}` — the previous `in` check mistakenly flagged those as failures and reported `mcp_error: None`. Fix: `response.get("error")` truthy check.

- **H2** **Malformed-pick validation crashed the entire snapshot** (BH-19). `[HotPick.model_validate(p) for p in hot_picks]` was run in `persist_snapshot` BEFORE the INSERT — a single malformed pick (missing `symbol`, empty string, wrong type on `entry_zone`) would raise `ValidationError` and propagate out, **violating Story 10.1 AC #3 "never drop a day"**. Fix: new `_validate_picks_tolerant` helper validates one-at-a-time, logs each drop with its offending payload, persists whatever survived + the raw JSONB blob. New test `test_persist_snapshot_drops_malformed_picks_without_crashing` asserts a 4-pick input with 2 invalid entries still produces a snapshot with 2 valid HotPick models.

- **H3** **`create_strategy` + linkage UPDATE not atomic** (BH-9 / EC-4). The follow-up `UPDATE strategies SET source_snapshot_id = $1` ran on the same connection but OUTSIDE a transaction. If the UPDATE raised anything other than `ForeignKeyViolationError` (e.g., `UndefinedColumnError` on a pre-migration-015 deployment), the strategy was already persisted without the linkage AND the caller got a 500, leaving an orphaned row. Fix: wrap both in `async with conn.transaction():`. Additional defense: `ForeignKeyViolationError` and `UndefinedColumnError` now fall through to a second transaction that creates the strategy WITHOUT the linkage — the strategy lands even if the snapshot FK has a problem.

- **H4** **`POST /api/gordon/fetch` leaked 500 tracebacks** (BH-23). The router's docstring claimed "never raises on MCP failure" but `fetch_and_persist` can also raise DB-layer errors (connection loss, migration 014 missing). Fix: try/except with distinct `asyncpg.UndefinedTableError` (503 + hint) and generic `Exception` (503 + structured body).

- **H5** **`"gordon"` trigger-source taxonomy mismatch** (EC-1). `taxonomy.yaml` defines `gordon_hot_pick`, not `gordon`. The previous prefill dict used the literal `"gordon"` string, which meant:
  1. The Gordon checkbox in `strategy_form.html` was NEVER pre-checked (the for-loop iterates `taxonomy.trigger_types` and none matched).
  2. On submit, the phantom literal "gordon" landed in `strategies.trigger_sources` with no downstream cross-reference — future journal facet lookups would silently miss.
  Fix: prefill `trigger_sources=["gordon_hot_pick"]`. Live smoke probe verified the `checked` attribute now renders on the `gordon_hot_pick` checkbox.

- **H6** **`compute_diff` symbol-only keying collapsed multi-horizon picks** (EC-12). `{p.symbol for p in current}` deduplicated NVDA-at-swing_short + NVDA-at-swing_long into a single `"NVDA"` entry. If last week had only swing_short, this week's brand-new swing_long NVDA was silently reported as "unchanged". Fix: new `_pick_key(pick)` helper that returns `(symbol, horizon)` tuples; all three diff buckets (new / dropped / unchanged) now key on the tuple. New test `test_compute_diff_keyed_by_symbol_and_horizon` locks the behavior in.

- **H7** **Regime-Hero hidden on Gordon empty-state** (EC-14). The previous template rendered the F&G/VIX/Kill-Switch hero row ONLY in the `{% else %}` branch (populated Gordon snapshot present). Fresh install → Gordon empty → Chef lost access to regime data even though Epic 9 snapshots were available. Fix: extracted a `regime_hero_cards(regime, diff, previous)` macro and call it in both branches (before the Gordon empty-state or populated branches). The KILL-SWITCH card now shows "—" + "Kein Regime-Snapshot" when `regime.snapshot is None` instead of the misleading "🟢 OFF".

- **H8** **Literal `"None"` string leaked via URL query param** (BH-16). If `pick.horizon` was None in the template, a hand-crafted URL `/strategies?prefill_horizon=None` would hit the handler with the literal string `"None"`, which then formed the name `"NVDA (None)"` and polluted the prefill dict. Fix: explicit `if prefill_* == "None": prefill_* = None` coercion in `strategies_page`. The template-side guard (`{% if pick.horizon %}`) was already correct — this is defense in depth for operator-crafted URLs.

### 🟡 MEDIUM (6)

- **M1** **`hx-disabled-elt` on Gordon refresh** (BH-5 / BH-14). Rage-clicking the "⟳ Snapshot fetchen" button created multiple same-minute snapshots, destroying the week-over-week diff semantics. Added `hx-disabled-elt="find button"` so HTMX disables the submit while the request is in flight.

- **M2** **`UndefinedColumnError` fallback in `create_strategy_route`** (BH-10). The follow-up UPDATE assumed Migration 015 was applied. If app code outran the migrations on a deployment, every prefill flow 500'd. Fix: catch `UndefinedColumnError` distinctly, log an operator hint ("Migration 015 not applied"), and retry the CREATE in a fresh transaction WITHOUT the linkage. Same for `ForeignKeyViolationError`.

- **M3** **URL-encode prefill components** (BH-11 / EC-21). A symbol with `&`, `#`, `?` or spaces (e.g. CFD `^GSPC`) would break the prefill query string. Fix: `{{ pick.symbol | urlencode }}` + `{{ pick.horizon | urlencode }}` in the "Als Strategie anlegen" link.

- **M4** **`trends_page` migration hint covered only 014/015** (BH-15). Epic 9's 012/013 are prereqs for the regime hero, so the hint needed to span the 012-015 range. Fix: broaden the hint text.

- **M5** **`source_snapshot_id` was dead-write** (EC-19). Epic-10 inserted the column via `create_strategy_route` but no read path. Fix: added the column to `_GET_SQL` + `_LIST_SQL` in `app/services/strategy.py`, added the field to `app/models/strategy.py::Strategy`, and updated `_row_to_strategy` to thread it through. The strategy-detail UI backlink ("Erstellt aus Gordon-Snapshot #X") is deferred as **D218** — the plumbing is now in place for a future story to render it.

- **M6** *(rolled up into H1 diff)*.

Plus `fetch_gordon_trend_radar` now explicitly re-raises `CancelledError` and passes `exc_info=True` to the warning log for better forensics.

## Live Smoke-Probe Results

Against Docker Compose stack (`docker compose up -d --build`):

| Probe | Outcome |
|---|---|
| Startup | All 15 migrations idempotent |
| `POST /api/gordon/fetch` (MCP offline) | HTTP 201 with `source_error="mcp_client not configured"`, `id=5`, `hot_picks_count=0` — always-write contract works |
| `GET /trends` | Hero row renders F&G + VIX + Kill-Switch outside the empty-state branch (H7 verified) |
| `GET /strategies?prefill_symbol=NVDA&prefill_horizon=swing_short&prefill_source_snapshot_id=4` | Hidden input `source_snapshot_id=4` + `value="NVDA (swing_short)"` + `<input ... name="trigger_sources[]" value="gordon_hot_pick" checked>` — H5 taxonomy fix verified on the rendered HTML |

## Deferred (LOW + blocking dependency) — 18 items

All added to `deferred-work.md` as **D214–D231**. Summary:
- **D214 DECISION-BLOCKING**: fundamental MCP contract gap — no `trend_radar` tool exists; Chef must decide build-it vs swap-data-source
- **D215–D218** UX polish: UNCHANGED section compression, prefill URL reload quirk, selected+prefill collision, strategy-detail backlink
- **D219–D226** Observability / defense: tz guard on is_stale, has_error semantics, day-level UNIQUE, GIN index rollback, dead code cleanup, tolerant entry_zone, source_error on parse failure, nested result.isError
- **D227–D230** Test coverage: router integration, template render, concurrent-post dedup, FK migration test
- **D231** Story 10.1 AC #2 cron registration deferred to Story 11.1

## Status

- **Tranche A applied:** 14 patches (8 HIGH + 6 MEDIUM)
- **Tests:** 438/438 green (413 pre-existing + 25 Gordon unit tests)
- **Ruff:** clean
- **Smoke probe:** full end-to-end — MCP-offline graceful degradation, trends hero in both branches, strategies prefill with correct taxonomy id + taxonomy-matching checkbox
- **Deferred:** D214–D231 in deferred-work.md
- **Ready for:** Epic 11 (System-Health & Scheduled Operations) Yolo-mode — Story 11.1 will wire both the Regime cron (Epic 9) and the Gordon cron (Epic 10) into APScheduler, closing the D231 + D206 deferrals

**Chef decision needed before Epic 10 is truly "done":** D214 contract gap — build `trend_radar` on fundamental MCP, or swap Story 10.1 to a different data source.
