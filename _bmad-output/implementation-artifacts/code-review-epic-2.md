---
review_date: 2026-04-13
review_type: adversarial-multi-layer
stories_reviewed:
  - 2-1-trades-datenmodell-flex-import
  - 2-2-live-ib-sync-reconciliation
  - 2-3-journal-startseite-trade-list
  - 2-4-trade-drilldown-inline-expansion
reviewers:
  - acceptance-auditor (general-purpose subagent)
  - blind-hunter (general-purpose subagent, no project context)
  - edge-case-hunter (general-purpose subagent, project read access)
findings_summary:
  decision_needed: 2
  patch_high: 8
  patch_medium: 15
  patch_low: 3
  defer: 12
  dismiss: 4
status: tranche-a-applied
---

# Code Review — Epic 2 (Stories 2.1–2.4)

**Adversarial multi-layer review** of Epic 2 (Trades-Datenmodell & Flex-Import, Live IB Sync, Journal-Startseite, Trade-Drilldown). Run via three parallel reviewer personas.

## Reviewer Layers

| Layer | Inputs | Findings raised |
|---|---|---|
| **Acceptance Auditor** | diff + 4 story files + PRD + architecture | Cross-spec contradictions, AC coverage matrix |
| **Blind Hunter** | diff only (NO project context) | adversarial prose, no defensive framing |
| **Edge Case Hunter** | diff + project read access | branching/boundary analysis |

## Decisions Taken

Two decision points required Chef's call:

- **D-A** Story 2.2 AC #1 (`execDetailsEvent` subscription) + AC #3 (auto-reconnect loop) were implemented as **skeleton only** (pure async functions, no scheduler, no event subscription). → **Chef chose (b)**: demote to Story 12.1 (scheduler-framework). Story 2.2 file updated with DESCOPE-ENTSCHEIDUNG block; the delivered `reconcile_open_trades()` and `upsert_trade()` primitives remain usable.
- **D-B** Story 2.4 AC #4 (`?expand=<id>` bookmarkable URL) was client-side only — the journal didn't server-prefill the matching expansion row. → **Chef chose (a)**: patch now. `app/routers/pages.py` reads `?expand=`, calls `get_trade_detail`, and the template renders a `<template>` prefill block with a tiny inline script to pre-fill the slot.

## Patches Applied — Tranche A (11)

### 🔴 HIGH (8)

- **H1** Cover-side P&L sign flip. `compute_pnl` and `compute_r_multiple` treated `cover` like `buy`, producing the opposite sign on short-closes — corrupts every strategy aggregate after the first short. Fix: `cover` shares the `sell`/`short` branch (`entry − exit`). New `_to_decimal` helper via `str()` avoids binary-float artifacts. *(app/services/pnl.py, app/services/r_multiple.py)*
- **H2** Live-sync silently dropped multi-fill events. `insert_trades` uses `ON CONFLICT DO NOTHING`, so when IB emits `execDetailsEvent` three times for the same order the second and third fills vanish. New `upsert_trade()` with `ON CONFLICT DO UPDATE` returning `(id, (xmax = 0) AS inserted)` lets the live-sync handler enrich the existing row. *(app/services/ib_flex_import.py, app/services/ib_live_sync.py)*
- **H3** Flex importer never set `exit_price` or `closed_at` for close executions, so Story 2.3's untagged-counter (`WHERE closed_at IS NOT NULL`) returned 0 for all Flex-imported trades. Fix: `_trade_from_element` now sets both fields for SELL+C / BUY+C. *(app/services/ib_flex_import.py)*
- **H4** `_map_side` only read `buySell`, could never produce SHORT or COVER — every historical short was imported as plain `sell`. Fix: read `openCloseIndicator` too, map BUY+O→buy, SELL+C→sell, SELL+O→short, BUY+C→cover. *(app/services/ib_flex_import.py)*
- **H5** Every Flex datetime was hard-tagged as UTC despite IB shipping them in the account-configured timezone — shifted historical trades by 4–5 hours and silently broke `opened_at DESC` ordering across DST. Fix: new `_resolve_tz()` reads `accountTimezone` from `<FlexStatement>`, `_parse_ib_datetime` localizes via that tz then converts to UTC. *(app/services/ib_flex_import.py)*
- **H6** Story 2.2 AC #1 + #3 implemented as skeleton (no scheduler, no event subscription). Descope to Story 12.1. Story file updated with DESCOPE-ENTSCHEIDUNG block, tasks 1–3 marked deferred with rationale. *(implementation-artifacts/2-2-live-ib-sync-reconciliation.md)*
- **H7** `format_time` filter returned naive-timezone wall-clock from whatever tz the datetime came in, so Flex imports (UTC) and live-sync events (server-local) rendered inconsistently. Fix: `value.astimezone(UTC)` before strftime. *(app/filters/formatting.py)*
- **H8** `connect_ib()` would crash the event loop under uvloop because `ib_async` imports `nest_asyncio` which is incompatible. Fix: `_running_under_uvloop()` detection, refuse connect with a clear log line and a hint about `--loop asyncio`. *(app/clients/ib.py)*

### 🟡 MEDIUM (3)

- **M1** `_bucket_options` bucketed by `(ibOrderID, underlying)` but fell through to `("", underlying)` when both order-ID attributes were missing — two unrelated single-leg options on the same underlying would collide and get misclassified as a spread. Fix: fall back to the trade's own `permID` so `len(bucket) == 1` is guaranteed. *(app/services/ib_flex_import.py)*
- **M2** `list_trades` clamped `page < 1` but not `page > total_pages` — a stale `?page=9999` bookmark rendered an empty page instead of the last populated one. Fix: upper-bound clamp to `max_page`. *(app/services/trade_query.py)*
- **M6** Direct `Decimal(value)` calls in `compute_pnl` / `compute_r_multiple` raised `InvalidOperation` on `Decimal(float)` inputs with trailing binary artifacts. Fix: `_to_decimal` routes through `Decimal(str(value))`. *(app/services/pnl.py, app/services/r_multiple.py)*

### ⚙️ Decision-Patches (2)

- **M11** Server-side `?expand=<id>` prefill on the journal page (D-B a). *(app/routers/pages.py, app/templates/pages/journal.html)*
- **M12** `_trigger_spec_json()` wraps `json.dumps(spec, default=str, sort_keys=True)` so dicts with Decimal/datetime values don't crash the upsert. *(app/services/ib_flex_import.py)*

## Test Results

- **166 / 166 passing**
- 3 integration tests (`test_flex_import.py`) updated for the new sample-fixture semantics (4 valid trades, AAPL open+close rows, MSFT SELL+O→short)
- Flex parser unit tests extended with `test_account_timezone_is_respected` and `test_parse_ib_datetime_explicit_tz`
- `ruff check` + `ruff format` clean

## Deferred (12)

All 12 remaining MEDIUM / LOW findings catalogued in `deferred-work.md` (entries D21–D32).
