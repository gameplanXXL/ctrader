---
generated: 2026-04-14T19:40
status: mvp-complete-pending-chef-decisions
test_count: 483
---

# ctrader MVP Readiness Checklist

All 12 epics landed + code-reviewed + Tranche-A-patched. This doc is the single entry point for "what's left before we ship".

## Epic status (12 of 12 done)

| Epic | Title | Status | Notes |
|---|---|---|---|
| 1 | Projekt-Bootstrap & Design-System | ✅ done | — |
| 2 | Trade-Journal & IB-Import | ✅ done* | Story 2.2 Rest-Descope → Story 12.1 |
| 3 | Trade-Tagging & Trigger-Provenance | ✅ done* | 3.1.1 fuzzy-search follow-up pending |
| 4 | Journal-Intelligence | ✅ done* | 2000-trade perf + vendor binary drop pending |
| 5 | Fundamental-Integration (MCP) | ✅ done* | Scheduler wiring moved to 11.1 (done) |
| 6 | Strategy-Management | ✅ done | sort-by-column deferred |
| 7 | Approval-Pipeline & Risk-Gate | ✅ done | Tranche A applied |
| 8 | Bot-Execution (cTrader) | ✅ done | Stub-backed, real OpenApiPy adapter pending D181 |
| 9 | Regime-Awareness & Kill-Switch | ✅ done | Tranche A applied |
| 10 | Gordon Trend-Radar | ✅ done | **D214 Chef decision blocking** |
| 11 | System-Health & Scheduled Operations | ✅ done | **D232 Chef decision blocking** |
| 12 | IB Swing-Order (Stock + Option) | ✅ done | Stub-backed, real ib_async adapter pending |

\* = Tranche A applied; some review-items carried to follow-up or decisions list.

## Chef decisions required before GA

### D214 — Gordon MCP `trend_radar` tool
- **Blocker for:** Epic 10 (Gordon Weekly Fetch) — real data.
- **Finding:** The `fundamental` MCP server exposes `fundamentals`, `price`, `news`, `search`, `crypto`. There is no `trend_radar` tool. Gordon's weekly hot-picks currently fall back to a stub.
- **Options:**
  1. Add a `trend_radar` tool to the `fundamental` MCP (1-day spike in fundamental/).
  2. Re-route Gordon to synthesize a trend_radar from existing tools (fundamentals + news + price).
  3. Descope Gordon real-data to Phase 2 and keep the stub.
- **Recommendation:** Option 2 — no new MCP tool, use existing tools.

### D232 — IB Flex Nightly cron
- **Blocker for:** Story 11.1 AC #2 (5 cron jobs wired; only 4 are).
- **Finding:** `ib_flex_import::import_flex_xml` takes an XML string parameter — it's not self-contained and can't be registered as-is.
- **Options:**
  1. Filesystem watcher that picks up XML drops in `data/ib-flex-inbox/`.
  2. IB Flex Web Service API caller (Chef already has `IB_FLEX_TOKEN`).
  3. Descope to Phase 2.
- **Recommendation:** Option 2 — simplest because the token is already in env.

## Stub adapters pending real wiring

| Service | Stub | Blocks | Estimate |
|---|---|---|---|
| cTrader OpenApiPy (Epic 8) | `StubCTraderClient` | D181 (CLAUDE.md) | 1-day spike |
| IB Quick-Order (Epic 12) | `StubIBQuickOrderClient` | TWS/Gateway running locally | 0.5-day when TWS available |

Neither blocks MVP usability because the Journal + Approval + Regime + Scheduler pipelines all run end-to-end against the stubs.

## Quality gates

| Gate | Status |
|---|---|
| Tests | ✅ `483 passed` |
| Ruff | ✅ clean |
| Ruff format | ✅ clean |
| Live smoke probe | ✅ verified per epic |
| Migrations applied | ✅ 019 (latest: `trades_option_metadata`) |
| Deferred items tracked | ✅ D1–D268 in `deferred-work.md` |

## Next steps (Chef)

1. Decide D214 + D232 (both can be delegated to future PR, neither blocks a first production run).
2. When TWS/Gateway is running locally, replace `StubIBQuickOrderClient` with real `ib_async` adapter (Epic 12 acceptance — already spec'd).
3. Run `docs/recovery.md` once manually (NFR-R5, D245).
4. Review `deferred-work.md` and promote/drop items as needed.
