---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: 12cf693
stories_reviewed:
  - 3-1-post-hoc-tagging-form
  - 3-2-trigger-spec-jsonb
  - 3-3-trigger-spec-readable
  - 3-4-mistake-tags-top-n-report
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 4
  patch_high: 8
  patch_medium: 5
  patch_low: 0
  defer: 30
  dismiss: 3
status: tranche-a-applied
---

# Code Review — Epic 3 (Stories 3.1–3.4)

**Adversarial multi-layer review** of Epic 3 (Trade Tagging, Trigger-Spec JSONB, Prose Renderer, Mistakes Report). Three parallel reviewer personas.

## Reviewer Layers

| Layer | Inputs | Findings raised |
|---|---|---|
| **Acceptance Auditor** | diff + 4 story files + PRD/UX-Spec/CLAUDE.md | AC-coverage matrix, cross-spec contradictions |
| **Blind Hunter** | diff only (no project context) | 38 findings, adversarial style |
| **Edge Case Hunter** | diff + full project access | 50 findings, data-flow / boundary focus |

## Decisions Taken

Four decisions required Chef's call (applied as "Tranche A" fixes since Chef explicitly told us to "fixe Probleme"):

1. **3.3 UX-DR74 "20-30 patterns"** — taxonomy has 8, impl has 8 + default, test locks coverage. → **spec-needs-update**: keep the implementation, update UX-DR74 text later to "one pattern per trigger_type in taxonomy.yaml, default fallback for unknowns".
2. **3.2 AC #2 (bot-proposal auto-population)** — the builder is a documented Epic 7 placeholder. → **defer** to Story 7.x, note in story-completion notes.
3. **3.4 AC #3 (facet filter integration)** — explicit cross-reference to Story 4.1. → **defer** to Epic 4.
4. **3.4 mistake_tag naming drift (PRD hyphens vs taxonomy underscores)** — taxonomy is the implementation source of truth for JSONB key safety. → **spec-needs-update**: PRD FR18a text adjusted in the next PRD pass.

Three LOW findings were **dismissed** as single-user-localhost-acceptable: CSRF protection (EC-14), `datetime(2000, 1, 1)` magic sentinel (BH-36/EC-20), inline `<script>` duplication (EC-32, EC-36).

## Patches Applied — Tranche A (13)

### 🔴 HIGH (8)

- **H1** **`strategy` + `exit_reason` form values silently dropped** (EC-1, EC-2, BH-1, AA-3.1-AC#1). The tagging form marks both as `required` and sends them; `build_from_tagging_form` never read either key. Fix: add both as optional fields on `TriggerSpec`, require them in the builder with taxonomy validation (`exit_reason` against `taxonomy.exit_reasons`, `strategy` accepted as-is until Epic 6). The stored JSONB now carries `strategy` and `exit_reason` — when Epic 6 lands, the migration will copy into a real `strategy_id` column. *(app/models/trigger_spec.py, app/services/trigger_spec.py)*
- **H2** **Mistakes SQL crashes on non-array `mistake_tags`** (BH-6, EC-17). `jsonb_array_elements_text` raises `cannot extract elements from a scalar` if any row ever stores a string or null in `mistake_tags`. Fix: add `jsonb_typeof(trigger_spec->'mistake_tags') = 'array'` filter to the WHERE clause. *(app/services/mistakes_report.py)*
- **H3** **`tag_trade` can clobber bot-trade `trigger_spec`** (BH-10, EC-15). The UPDATE had no WHERE guard, so a scripted POST to `/trades/{bot_id}/tag` would overwrite Epic 7/8 provenance. Fix: `AND broker = 'ib' AND closed_at IS NOT NULL` + new `TradeNotTaggableError` (→ HTTP 409). *(app/services/tagging.py, app/routers/trades.py)*
- **H4** **Bookmarked `?expand=<untagged>` doesn't wire the tagging slot** (EC-34). The journal's server-side prefill `<template>` sets `innerHTML` but never calls `htmx.process()`, so the nested `hx-get ... hx-trigger="load"` on the tagging slot never fires. Fix: call `window.htmx.process(slot)` after the innerHTML assignment. *(app/templates/pages/journal.html)*
- **H5** **`followed` defaulted to `True` silently** (EC-41). Every manual tag rendered "Chef folgte der Empfehlung" on a signal that didn't exist. Fix: `followed` is now `bool | None` with default `None`; the builder only sets it when the form explicitly provides the key; `_followed_text(None)` renders as "ohne Agent-Empfehlung". Manual trades no longer invent provenance. *(app/models/trigger_spec.py, app/services/trigger_spec.py, app/services/trigger_prose.py)*
- **H6** **`AVG(pnl)` diverges from `SUM/COUNT` when some P&L is NULL** (EC-18). Raw `AVG(pnl)` averages only non-null rows, so `count × avg ≠ total` in the report. Fix: `COALESCE(SUM(pnl) / NULLIF(COUNT(*), 0), 0)` to match the docstring's "frequency counts real trades, money counts only closed ones" invariant. *(app/services/mistakes_report.py)*
- **H7** **JSONB encoder has no `default=` for Decimal / datetime** (BH-18). `json.dumps` raises `TypeError` on any future dict carrying a `Decimal`. Fix: route through `_jsonb_encode = lambda v: json.dumps(v, default=str)`. *(app/db/pool.py)*
- **H8** **`_init_connection` is manual opt-in + test mutates global `app.state`** (EC-25, BH-25). Fix: rename to public `init_connection`, update both integration-test fixtures, rewrite `test_tag_post_rejects_unknown_trigger_type` to use the conftest fake pool instead of mutating `app.state.db_pool` globally. *(app/db/pool.py, tests/integration/test_flex_import.py, tests/integration/test_trade_query.py, tests/unit/test_tagging_form.py)*

### 🟡 MEDIUM (5)

- **M2** **Validation re-render drops strategies dropdown** (EC-12). User hits a 422 and can't resubmit because strategies is `[]`. Fix: `_render_form_error` now re-fetches strategies via `list_strategies_for_dropdown`. *(app/routers/trades.py)*
- **M3** **`hx-trigger="load once"` invalid + autofocus broken on HTMX swap** (BH-21, BH-22). Fix: use `hx-trigger="load"` (already once-shot) + `hx-on::after-swap="this.querySelector('select, input, textarea')?.focus()"`. *(app/templates/fragments/trade_detail.html)*
- **M5** **`extra="forbid"` locks in future field addition** (BH-28, EC-11). Any new JSONB key would break `parse()` on stored rows. Fix: change to `extra="ignore"` on the model; form builder still enforces its own strict field list at the service layer. *(app/models/trigger_spec.py, tests updated)*
- **M7** **Pydantic `ValidationError` not caught in POST → 500 instead of 422** (EC-10). Fix: catch `pydantic.ValidationError` alongside `TriggerSpecValidationError`. *(app/routers/trades.py)*
- **M8** **`next_untagged_trade` failure would 500 the user after a successful tag** (BH-9). Fix: wrap the query separately, degrade to `next_trade = None` with a logged warning. *(app/routers/trades.py)*

### Plus bonus polish (rolled in with Tranche A)

- **BH-2/EC-4** `key.removesuffix("[]")` instead of `rstrip("[]")` so `tags[0]` isn't clobbered.
- **EC-5** `trigger_type=None` or empty → "Nicht getaggt" (prose renderer no longer renders a half-empty line).
- **BH-17** `_confidence_pct` clamped to [0, 100] so a misencoded integer percent doesn't render "4500%".
- **BH-29** `to_jsonb` now uses `exclude_none=True` so the stored JSONB doc stays compact (no always-null `agent_id`, `proposal_id`, `note`, `followed` keys on manual rows).
- **EC-38** Reverse taxonomy-coverage test added (`test_pattern_catalogue_has_no_dead_patterns`).
- **Form polish** dropped the redundant `note` field, merged into `entry_reason` so the form has exactly 6 fields (UX-DR62 cap).

## Test Results

- **219 / 219 passing** (was 208 before Tranche A; +11 new tests across trigger_spec, trigger_prose, tagging_form)
- `ruff check` clean
- Live smoke probe against compose: POST persists the full JSONB with `strategy`, `exit_reason`, `mistake_tags`; drilldown prose renders "verkaufte AAPL auf technischem Ausbruch — Breakout Volume (Horizon: Short Swing, Confidence 72%)."; 409 on the open-AAPL trade; mistakes report aggregates correctly.

## Deferred (30)

All LOW / polish findings catalogued in `deferred-work.md` as D33–D62.

## Spec updates to follow in next PRD pass

- **UX-DR74**: "20-30 Template-Patterns" → "ein Pattern pro `trigger_type` in `taxonomy.yaml`, DEFAULT_PATTERN als Fallback"
- **UX-DR58**: allow an explicit submit button as progressive-enhancement fallback (Enter remains the primary keyboard path)
- **UX-DR59 (blur validation)** and **UX-DR60 (fuzzy search)**: retained as Story 3.1.1 follow-up (tracked in deferred-work.md)
- **PRD FR18a**: mistake-tag naming normalized to underscore form (matches taxonomy)
- **PRD FR18a**: extend the listed mistake_tags from 6 to 9 (adds `chased`, `held_too_long`, `cut_too_early` already in taxonomy)
- **Architecture.md**: document the JSONB codec registration in `app/db/pool.py::init_connection` under "JSONB Implementation"
