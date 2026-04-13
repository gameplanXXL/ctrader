---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: 25d8f07
stories_reviewed:
  - 4-1-facet-filter-system
  - 4-2-aggregation-hero-metrics
  - 4-3-mae-mfe-calculation
  - 4-4-pnl-calendar-view
  - 4-5-ohlc-chart-lightweight-charts
  - 4-6-command-palette
  - 4-7-csv-export-save-query
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 8
  patch_medium: 8
  patch_low: 0
  defer: 40
  dismiss: 4
status: tranche-a-applied
---

# Code Review — Epic 4 (Stories 4.1–4.7)

**Adversarial multi-layer review** of Epic 4 (Facets, Aggregation, MAE/MFE, Calendar, OHLC Chart, Command Palette, CSV+Presets). Three parallel reviewer personas.

## Patches Applied — Tranche A (16)

### 🔴 HIGH (8)

- **H1** **`templates.env.globals["build_facet_href"]` race condition** (BH-37 / EC-43). The builder was attached to a module-level Jinja environment dict on every request, so a second HTMX request could overwrite the global mid-render and the first response would emit URLs built from the second request's facet selection. Fix: pass `build_facet_href` as a per-request template-context variable and thread it through `facet_bar` as an explicit macro argument. *(app/routers/pages.py, app/templates/components/facet_bar.html, app/templates/pages/journal.html)*

- **H2** **MAE/MFE sign-convention + hot-pinning bugs** (BH-7, BH-9, BH-41, EC-29, EC-48). Three separate defects in the same service:
  - Short trades whose high stayed below entry reported a fabricated negative MAE; long trades whose low stayed above entry reported a fabricated positive MAE. Fix: `min(..., 0)` / `max(..., 0)` clamps.
  - `persist_mae_mfe` stamped `computed_at = NOW()` even when the compute returned all-None — once the stub fallback chain ran, subsequent drilldowns skipped the lazy fetch forever and the degraded state was permanent. Fix: persist only when `result.available`.
  - Signed-negative `quantity` (some broker schemas use it for shorts) flipped dollar-unit signs. Fix: `abs(Decimal(str(quantity)))`. *(app/services/mae_mfe.py)*

- **H3** **Drawdown phantom-zero baseline** (BH-4 / EC-8). `running_max` initialized to `Decimal("0")` so any purely-losing series reported drawdown equal to `-total_loss` against a flat-zero equity curve that never existed. Fix: seed `running_max` with the first cumulative value (`None` sentinel + first-trade seed), so "peak-to-trough" measures from the first trade's own baseline. *(app/services/aggregation.py)*

- **H4** **Broker facet enum injection** (BH-3). A crafted `?broker=alpaca` hit `broker = ANY($1::trade_source[])` and Postgres raised `invalid input value for enum trade_source: "alpaca"` → 500 → wiped the whole journal page. Fix: intersect the selection against an `_VALID_BROKERS` allowlist before binding. *(app/services/facets/broker.py)*

- **H5** **`base.html` never loaded the chart vendor script** (Auditor 4.5). The drilldown expected `window.LightweightCharts` but no `<script src=>` tag existed — the "drop-in library" story was broken. Fix: add the `<script src>` tag with `onerror="this.remove()"` fallback, rename the placeholder file to the expected real filename so the current no-op path still loads 200 OK. *(app/templates/base.html, app/static/js/vendor/)*

- **H6** **Calendar `opened_at::date` timezone drift** (EC-4). The `::date` cast used the Postgres session timezone, not UTC, so a trade opened at 23:30 UTC from Berlin (UTC+2) landed in the "next day" local bucket and a calendar click missed it. Fix: `(opened_at AT TIME ZONE 'UTC')::date` to match the calendar's UTC bucketing in `daily_pnl.get_daily_pnl`. *(app/services/trade_query.py)*

- **H7** **`chart_data` endpoint / MAE/MFE timeframe mismatch** (EC-31, EC-34). `chart_data` hardcoded `Timeframe.M1` but MAE/MFE's read-through walked `(M1, M5)`. A trade whose cache held only M5 candles showed MAE/MFE numbers in the drilldown but "Chart-Daten nicht verfuegbar" in the same view. Fix: walk the same preference order in both code paths. *(app/routers/trades.py)*

- **H8** **`daily_pnl` SQL AND/OR precedence trap** (BH-12 / EC-12). The inner parens were missing around each range so a future `AND user_id = $X` inside the same outer group would only bind to one branch of the OR. Latent bug — added explicit inner parens now. *(app/services/daily_pnl.py)*

### 🟡 MEDIUM (8)

- **M1** **Shift+Click multi-select UX** (Auditor 4.1 AC #7). The facet_chip comment promised the feature; no JS implemented it. Fix: inline JS on the facet-bar listens for shift+click and rebuilds the URL to APPEND the new value to any existing selection, routed through `htmx.ajax()` so the swap + pushState both fire. *(app/templates/components/facet_bar.html)*

- **M2** **Arrow-key navigation inside the facet toolbar** (Auditor 4.1 AC #5 / UX-DR13). `role="toolbar"` was set but no key handler. Fix: data-attribute-scoped keydown listener moves focus across `.facet-chip` elements on Arrow/Home/End. *(app/templates/components/facet_bar.html)*

- **M3** **Sparkline only on Expectancy card** (Auditor 4.2 AC #1). Spec says every hero card gets a sparkline. Fix: pass the cumulative-PnL sparkline to all four `stat_card` calls. *(app/templates/pages/journal.html)*

- **M5** **Command palette doesn't index strategies / trade ids** (Auditor 4.6 AC #2). Only routes + presets were in the palette. Fix: `build_palette_items` now loads `list_strategies_for_dropdown` (falls back to taxonomy.yaml before Epic 6) and fetches the 25 most recent trades. Each is isolated in its own try/except so one failure doesn't blank the palette. *(app/services/command_palette.py)*

- **M7** **`datetime.utcnow()` deprecated** (BH-14 / EC-14). Python 3.12 deprecates the naive-datetime alias. Fix: `datetime.now(UTC)`. *(app/routers/pages.py)*

- **M8** **Calendar year/month unbounded** (BH-16 / EC-16). `?month=13` or `?year=-5000` threw `ValueError` at `datetime(year, month, 1)` → 500. Fix: `Query(ge=1970, le=2100)` and `Query(ge=1, le=12)`. *(app/routers/pages.py)*

- **M10** **PresetPayload key whitelist** (BH-25). Any JSON key passed through `POST /api/presets` was persisted. Fix: `cleaned_filters()` intersects keys against `_ALLOWED_FACET_KEYS` and drops empty value lists. *(app/routers/api.py)*

- **M11** **Empty-filter presets allowed** (EC-23). `window.prompt()` + no filter state still POSTed successfully, creating a no-op palette entry. Fix: client-side guard shows a warning toast and aborts; server-side `cleaned_filters()` rejects empty filters with 422. *(app/templates/pages/journal.html, app/routers/api.py)*

### Decisions & Dismissed (4)

- **Auditor 4.2 AC #3 Opacity flash**: deferred as non-critical for Single-User-Localhost. Single-user perceives state changes immediately — no Chef-visible benefit worth the churn.
- **Auditor 4.2 AC #5 Server-side aggregation cache**: deferred. Dataset is 4 trades today, aggregation is O(n) Python. Revisit when a benchmark on 2000+ trades shows a real latency bump.
- **BH-26 / BH-27 CSRF on `/api/presets` + open-redirect on palette**: dismissed. Single-User-Localhost, NFR-S2 binds to 127.0.0.1. Palette URL construction uses `/journal?...` as a hardcoded prefix — same-origin redirect only.
- **Story 4.5 vendor library binary**: still a manual Chef drop-in. The H5 script-tag fix makes the drop-in actually work; the placeholder stays as documentation.

## Test Results

- **255 / 255 passing** (239 unit + 16 integration; +16 new tests in this pass)
- New test modules: `test_mae_mfe.py` (4 tests — short/long clamp + signed quantity), `test_aggregation_drawdown.py` (5 tests — all drawdown baseline corners)
- `ruff check` + `ruff format` clean

## Live Smoke Verification

Tested against the compose stack after rebuild:

- `GET /journal?broker=alpaca` → HTTP 200 (H4 — unknown enum silently dropped)
- `GET /journal/calendar?year=2026&month=13` → HTTP 422 (M8 — bounds check)
- `POST /api/presets` with `filters={}` → HTTP 422 with clear error (M11 + M10)
- `GET /api/command-palette` → 19 items across 4 categories: Navigation(7), Saved Queries(1), Strategies(7), Recent Trades(4) (M5 wiring)
- `GET /journal?asset_class=stock` → 4 sparklines rendered in hero grid (M3); 26 facet-chip renders (H1 per-request builder working)
- `GET /trades/2/detail_fragment` → MAE/MFE section visible, Chart container present

## Deferred (40)

Catalogued in `deferred-work.md` as D63–D102 covering LOW findings, Single-User-Localhost-acceptable edge cases, and spec-text reconciliation.

## Story status after Tranche A

| Story | Status |
|---|---|
| 4.1 Facets | review (Shift+click + arrow-nav landed; 2000-trade perf test still pending) |
| 4.2 Aggregation | review (sparklines on all cards; opacity flash + agg cache deferred) |
| 4.3 MAE/MFE | review (sign bug + hot-pinning fixed; real OHLC clients still stubbed) |
| 4.4 Calendar | done |
| 4.5 OHLC Chart | review (script tag fixed; vendor binary still manual drop-in) |
| 4.6 Palette | review (strategies + trades indexed; aria-activedescendant still pending) |
| 4.7 CSV + Presets | done |
