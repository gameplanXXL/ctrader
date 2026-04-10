---
title: "Product Brief Distillate: ctrader"
type: llm-distillate
source: "product-brief-ctrader.md"
created: "2026-04-10"
purpose: "Token-efficient context for downstream PRD, architecture, and epic creation"
owner: "Christian (Chef)"
---

# ctrader — Detail Pack

Condensed context captured during product brief discovery (2026-04-10). Use alongside `product-brief-ctrader.md` as input to PRD creation.

## 1. User & Project Context

- Single user (Christian / "Chef"), personal tool only — no commercial, multi-user, SaaS, or monetization angles.
- German native, documentation and UI in German, intermediate Python skills.
- User has intermediate BMad framework experience; prior projects used BMad workflow (PRD → Epics → Readiness → Status).
- Third attempt at same idea — prior attempts abandoned at scope-explosion stage, not at technical-infeasibility stage.
- Target timeline: 8 weeks (2 months) solo effort for MVP. Weekly rhythm and descope ladder required because "versanden" (quiet abandonment) is the documented prior failure mode, not explicit kill decisions.
- Success depends as much on behavioral discipline as on code — brief explicitly includes kill-switch / descope ladder as a design concern.

## 2. Prior Project Archaeology (Archived)

**`/home/cneise/Project/ALT/ctrader` — .NET / C#, archived**
- Stack: Avalonia 11.3 UI, CommunityToolkit.Mvvm, Microsoft Semantic Kernel 1.68, Anthropic.SDK 5.8, cTrader.OpenAPI.Net 1.4.4, Rx.NET 6.1, EF Core 8 + Npgsql, PostgreSQL 15 + TimescaleDB 2.24, LiveChartsCore.SkiaSharpView.Avalonia, YamlDotNet, Serilog, DataProtection API.
- Scope at abandonment: 83 FRs across 8 epics and 47 stories, self-reported "100% complete" including Paper/Live engines, backtesting, CFD symbol browser.
- Multi-agent architecture: CrashDetector, SignalAnalyst, RiskManager, Trader agents via Semantic Kernel plugins called inline per pipeline tick.
- Core entities: Tick, Candle, Team, TeamInstance, Trade, Position, AgentDecision, Alert, Backtest, BacktestTrade, BacktestResult, Symbol (17 fields + AssetClass enum).
- Had LotSizeValidator pattern (min/max/step validation before every order) — reusable *concept*, not code.
- Audit requirement already understood: "Alle Live-Trading-Aktionen (Approval, Rebalancing, Circuit Breaker) werden in Audit-Tabellen protokolliert."
- Business targets: ≥3% avg monthly return, ≤25% max drawdown per agent and total.

**`/home/cneise/Project/ALT/ctrader2` — Python, archived**
- Stack: Python 3.12, OpenApiPy (protobuf over SSL to `live1.p.ctrader.com:5035`), DuckDB time-series, pandas/numpy/ta/scipy, Dash 2.15 + dash-bootstrap-components + Plotly, Pydantic v2 + pydantic-settings, structlog, typer CLI, python-telegram-bot, aiosmtplib, optional anthropic/scikit-learn/xgboost/optuna.
- Scope: 10 phases; Phases 1-8 complete, **Phase 9 (AI strategy generator with promotion pipeline) specced in ~47KB SPEC.md but never built** — maps directly to new ctrader's core feature.
- Risk defaults from `config.yaml` (directly reusable as starting envelope):
  - `max_risk_per_trade`: 1%
  - `max_risk_total`: 5%
  - `max_daily_loss`: 3%
  - `max_weekly_loss`: 7%
  - `max_monthly_loss`: 15%
  - `max_drawdown`: 20%
  - `max_positions`: 5
  - `daily_trade_limit`: 20
  - `min_risk_reward_ratio`: 1.5
  - `position_sizing`: `fixed_fractional`
- Strategy families built (trigger taxonomy source): trend-following (MA crossover, MACD, ADX, Ichimoku, SAR), mean-reversion (Bollinger, RSI, Stochastic), breakout (S/R, Donchian, Triangle, Volume), pattern-based (H&S, Double Top/Bottom, Flags, Candlestick), multi-indicator (MACD+RSI, Bollinger+Stoch, Triple Screen, MTF), advanced (Fibonacci, Elliott, Harmonic, S&D, Order Block).
- Alert channels: Telegram bot with `/confirm` flow, SMTP daily/weekly, Dash dashboard toast.
- Ralph autonomous dev loop ran 8+ `claude_output_*.log` sessions totaling 40+MB of streams in ~12h on 2026-02-12 before apparent abandonment — process rigor did not prevent drift.
- cTrader integration code (OpenApiPy, Protobuf, OAuth2 flow, heartbeat, reconnect with exponential backoff) is the single most reusable asset — but only after a time-boxed 1-day reuse spike.

## 3. Hard Dependency: `/home/cneise/Project/fundamental` (MCP Server)

- Node/TypeScript MCP server wrapping EODHD Financial API; MCP-exposed via `.mcp.json`.
- Two BMad modules live alongside:
  - **SFA** (Stock Fundamental Analysis)
    - Agents: **Viktor** (Analyst), **Rita** (Risk Manager)
    - Workflows: `analyze-stock`, `compare-stocks`, `explain-metric`, `fetch-financials`, `investment-decision`, `red-flag-scan`, `risk-assessment`, `sector-analysis`, `stress-test`, `valuation-check`, `watchlist-update`
  - **CFA** (Crypto Fundamental Analysis)
    - Agents: **Satoshi** (Analyst), **Cassandra** (Risk Manager)
    - Workflows: `analyze-crypto`, `crypto-decision`, `compare-cryptos`, `market-overview`, `token-economics`, `fetch-crypto-data`, `explain-metric`
- Supporting `src/lib/` infrastructure (reusable via MCP):
  - `trigger-evaluator.ts` (~411 LOC) — **structured trigger spec format, reusable as ctrader's JSONB schema**
  - `watchlist-schema.ts` (~157 LOC) — trigger/watchlist type definitions
  - `fear-greed-client.ts` — regime input for kill-switch
  - `coingecko-client.ts` — crypto data
  - `crypto-data-fetcher.ts`, `crypto-trigger-evaluator.ts`, `data-fetcher.ts`
  - `notifications.ts`, `trigger-utils.ts`, `watchlist-loader.ts`
- `src/tools/` (MCP tools): `fundamentals.ts`, `price.ts`, `news.ts`, `search.ts`, `crypto.ts`
- Daytrading module output exists: `_bmad-output/daytrading/trends/trend-radar-2026-03-29.md` by "Gordon" analyst — includes HOT / STAYING / DECLINING strategy categorization.
- `_bmad-output/daytrading/strategies/` and `_bmad-output/daytrading/research/` are currently **empty** — ctrader's weekly Gordon loop is designed to populate them.
- MVP expects `make start` to bring MCP server up; ctrader calls MCP tools as client.
- Requires `EODHD_API_KEY` in `.env`; secrets never in logs, `.env` chmod 600.

## 4. Technical Decisions Locked In

- **Language:** Python 3.12+
- **Frontend:** FastAPI + HTMX + Tailwind. Alpine.js only where strictly needed. No Node toolchain, no React/Next.js, no separate build step. Decision final.
- **Storage:** DuckDB (embedded, zero-ops). Explicitly NOT TimescaleDB/PostgreSQL — Docker/migrations overhead rejected for personal use.
- **Dependency manager:** `uv` (inferred preference; confirm at kickoff).
- **IB integration:** `ib_async` (maintained fork) for live executions + **Flex Queries (XML)** for reconciled historical data. `ib_insync` explicitly rejected as unmaintained since 2023.
- **cTrader integration:** OpenApiPy (protobuf over SSL), reuse of `ctrader2` code behind a 1-day spike timebox.
- **MCP client:** ctrader connects to `fundamental` MCP server as a client.
- **Audit log:** append-only, unforgeable, per Approval event (who/when/risk-budget/risk-gate-results).
- **Taxonomy:** `taxonomy.yaml` written in Week 2 *before* any UI, defines trigger types, exit reasons, mistake categories, regime tags. All analytics joins against this.

## 5. Two Broker Worlds — Semantic Split

**World A — Interactive Brokers (stocks + options, MANUAL trading only)**
- User places trades himself in TWS; ctrader is read-only consumer.
- Live executions via `ib_async` subscription; historical/reconciliation via Flex Queries (XML export).
- Trigger data gotcha: IB `reqExecutions` defaults to "today only" unless TWS GUI setting flipped → every serious tool uses hybrid live + Flex Query approach.
- `permId` is the stable cross-lifecycle order identifier → primary join key to ctrader's local trigger table.
- `orderRef` field is ~40 chars, survives IB lifecycle and Flex Query exports → carries `strategyId:signalId` foreign key for *bot* trades only. Manual IB trades do NOT get `orderRef` populated in TWS → MUST use post-hoc tagging UI with time-window match.
- MVP scope: **single-leg options only**. Multi-leg spreads are Phase 2 due to schema complexity.

**World B — cTrader (crypto + CFDs, BOT-ONLY trading)**
- User does NOT trade cTrader manually — read-only would be meaningless.
- cTrader is exclusively bot-execution surface.
- MVP: 1 agent on **demo account**, full approval pipeline, real paper orders.
- Phase 2: scale to 10 agents × 20k € each = 200k € managed; live-mode config switch.

## 6. Human-in-the-Loop Approval Workflow (core innovation)

- Both prior projects auto-executed after a one-time live-mode switch. ctrader inverts this: **every new strategy requires explicit human approval with risk budget**, not every order.
- Flow: Agent drafts strategy → MCP auto-call to `analyze-stock`/`analyze-crypto` for side-by-side Viktor/Satoshi fundamental verdict → **Rita** (`red-flag-scan`) or **Cassandra** (`stress-test`) auto-runs as risk gate → Chef sees Rita/Cassandra verdict next to risk-budget slider → Chef enters risk budget + clicks approve → Agent begins execution within that budget.
- **Hard rule:** if Rita/Cassandra risk gate flags, the green approval button is disabled. No override path in MVP.
- Audit log captures: proposer agent id, proposed strategy spec, Viktor/Satoshi fundamental output, Rita/Cassandra risk output, approval timestamp, approved risk budget, resulting IB/cTrader order IDs for the life of the strategy.

## 7. Trigger Provenance — the central data model concept

- Not a notes field; a schema-level concept.
- For each trade: `trigger_spec` JSONB column compatible with `fundamental/src/lib/trigger-evaluator.ts` schema → replayability Phase 2.
- Plus: `order_ref` (IB field, foreign key style), `perm_id` (IB primary join key for bot trades).
- Journal UI is a **query surface**, not just a drilldown. Faceted filters: trigger source (News / Viktor / Satoshi / Gordon / manual), confidence band, overridden-vs-followed, strategy, time window.
- Example user queries the journal must answer:
  - "Show all losing trades where I overrode a Viktor red-flag."
  - "Which news source has the worst average R-multiple?"
  - "Which of my Mean-Reversion agent's trades had their Gordon-trend-HOT status change since entry?"
  - "What's my Expectancy during Fear & Greed < 25 vs. > 75?"

## 8. News / Trend Engine — Scope Decision

- User initially requested a dedicated "trend engine" that reads news and produces trends for the bot.
- Resolved: **do NOT build this in ctrader**. Consume `fundamental`'s news tool + Gordon's trend-radar output via MCP.
- Weekly loop: ctrader pulls latest Gordon trend-radar, diffs vs. previous week, renders "What Gordon thinks vs. What your live strategies do" view. Chef can one-click promote a HOT item to strategy candidate.
- News source preference: "start simple, see how far it takes us" — whatever `fundamental`'s news tool returns is MVP-sufficient. Richer sources (social, on-chain, options flow) are Phase 2.

## 9. Success Metrics — Calibrated

**Product-level (observable, measurable):**
- Every IB execution of last 30 days appears in journal ≤5 minutes after trade close.
- Every cTrader bot trade has non-null `trigger_spec`.
- ≥80% of IB trades tagged via post-hoc UI within 48h.
- Weekly Gordon diff lands every Monday morning.
- Rita/Cassandra risk checks run on 100% of bot approvals.

**Hard MVP milestone (the single gating metric):**
- **Expectancy > 0 over ≥50 bot-demo trades with 95% confidence interval visible in review UI.**

**North Star (explicit non-KPI):**
- 70% win rate + 5% monthly gain. Kept out of gating metrics because the combination is mathematically tense (high win rate typically implies small R-multiples). Displayed in UI as aspirational, not as failure trigger.

**Non-code deliverables:**
- `taxonomy.yaml` in Week 2
- `strategy-template.md` in Week 6

## 10. Rejected Ideas (do not re-propose)

| Idea | Rationale |
|---|---|
| Multi-agent LLM orchestration via Semantic Kernel | `ctrader` delivered it; scope ballooned to 83 FRs. Simpler single-agent + HITL is deliberate. |
| Fully autonomous trading after one-time live switch | Both prior projects; user explicitly inverts to per-strategy approval. |
| cTrader / IC Markets as primary broker for stocks | User moved stocks to IB intentionally; only crypto/CFDs stay on cTrader. |
| Own backtest engine | User: "AI-driven trading changes too fast, historical backtests only punctually meaningful." `ctrader2` FR57-64 and Phase 6 rejected as sunk cost. |
| TimescaleDB | DuckDB wins for personal/zero-ops. |
| Dash / Plotly dashboards | Replaced by FastAPI + HTMX + Tailwind (no JS toolchain). |
| .NET / C# / Avalonia | Python throughout. |
| Own news/trend engine in ctrader | Consumed from `fundamental` via MCP. |
| YAML team templates with pipeline + override rules (from `ctrader`) | Heavy config surface rejected as overkill for solo use. |
| Ralph autonomous dev loops, mandatory commit-after-every-change | Process rigor didn't prevent abandonment; rejected. |
| 10 agents × 20k design in MVP architecture | Only `agent_id` column as extension point; everything else YAGNI. |
| Multi-leg options spreads | Phase 2 (schema complexity). |
| Agent-generated strategy improvement suggestions in MVP | MVP has free-text notes + metrics only; auto-improvement is Phase 2. |
| Counterfactual / cohort analysis in MVP | Needs ≥50 trades; meaningful only Phase 2. |
| Replay-trigger UI button in MVP | Only the storage is in MVP; button is Phase 2. |
| Own indicator library | Use `pandas-ta` directly if needed. |

## 11. Competitive Intelligence (2026)

**Trade journals surveyed:**
- **Tradervue** (since 2011): 80+ brokers incl. IB Flex; free tier; manual tagging; no AI; no execution.
- **TradeZella:** best-in-class UI, trade replay, static playbooks, IB Flex sync only daily, no bot execution, no approval flow.
- **TraderSync:** 700+ brokers (widest), native mobile apps, IB Flex auto-sync, no strategy generation, no execution.
- **Edgewonk:** psychology-first, flat $169/yr, fully manual entry, no IB live sync, no AI.
- **TradesViz:** strong IB Flex integration (active + trade confirmation queries), normalizes IB commissions well, read-only journal.
- **WealthBee / Trademetria:** automated IBKR Flex, tax reporting focus, no AI or execution.

**Execution / bot frameworks:**
- **NautilusTrader** (fit: high) — event-driven, native IB adapter, same code for backtest/live. Best foundation if execution mechanics matter. Consider as Phase 2 underlying engine.
- **QuantConnect / LEAN** (fit: medium) — end-to-end but hosted/cloud-coupled, harder to layer custom approval UI.
- **Backtrader** (fit: medium) — Pythonic, has IB store, minimally maintained, weak execution layer.
- **VectorBT / VectorBT Pro** (fit: medium) — excellent for ideation/parameter sweeps, not an execution framework.
- **Freqtrade** (fit: low) — crypto-only, no equities/IB.

**LLM trading reference architectures:**
- **TradingAgents** (Tauric Research) — multi-agent LLM with analyst debate, pluggable GPT/Claude/Gemini backends, no first-class human approval gate.
- **FinMem** — layered memory + character profiles for LLM traders, improves consistency, no built-in approval UI.
- **Celan Bryant / Medium tutorials** — LLMs generating NinjaTrader/Backtrader/QuantConnect strategy CODE for human review before compile → closest pattern to ctrader's approach but still code-review, not strategy-review.

**Market gap validated:** zero mainstream retail tool combines (a) authoritative IB execution sync via Flex + live `ib_async`, (b) first-class trigger data model linking each fill to indicator/LLM/news cause, (c) human-in-the-loop approval gate with per-strategy risk budget. Commercial incentive is weak (regulatory exposure + LLM liability); personal value is high.

## 12. IB API Gotchas (concrete, pre-verified)

- `ib_insync` unmaintained since 2023 → use `ib_async` (community fork).
- `reqExecutions` only returns trades since midnight unless TWS "Show trades for" setting is manually changed → must hybrid with Flex Queries for >1 day history.
- Commissions and realized P&L arrive via separate `commissionReport` callback → joining with executions in real-time is non-trivial → Flex Queries are authoritative for fees.
- `Order.orderRef` (~40 chars) round-trips through `execDetails` and Flex Query output → standard channel for strategy/signal tagging.
- Parent/child bracket orders share `orderRef` or reference parent ID → algo trades link back to generating strategy.
- `algoStrategy` + `algoParams` are IB-native algo metadata (TWAP, VWAP, Adaptive); NOT intended for app-level trigger data.
- `permId` is stable, IB-assigned unique identifier across order lifecycle → correct primary join key.
- Client Portal Web API (REST + OAuth) is thinner for historical executions and streaming than TWS API → prefer IB Gateway + `ib_async` + nightly Flex Query downloads.

## 13. Regulatory Context (German retail trader)

- **Pattern Day Trader rule** is US-only → **NOT applicable** to Christian as German resident. Common misconception in English algotrading content.
- **MiFID II**: suitability tests, BaFin reporting surface.
- **ESMA leverage caps**: 30:1 major FX, 20:1 indices/commodities, 5:1 single stocks, 2:1 crypto. Mandatory negative balance protection.
- **MiCA**: crypto-specific EU framework; ctrader must respect EU crypto rules for CFD crypto.
- **Abgeltungsteuer** (~26.375% incl. Soli): daytrading gains taxed as Kapitalerträge. 2021 €20k derivative loss-offset cap was struck down by Bundesfinanzhof in 2025; journal should still track realized/unrealized separately.
- **Audit discipline**: every LLM prompt, model version, proposed strategy, approval timestamp, resulting order ID should be logged — both for self-audit and to defend the "human decided" posture under regulatory review.
- **MVP commitment**: CSV export in Abgeltungsteuer-defensible format (Anschaffungs-/Veräußerungspaare with timestamps and fees).

## 14. Trade Schema Sketch (MVP target)

Columns (unified across IB + cTrader sources):
```
id                 -- primary key
source             -- enum: ib | ctrader
agent_id           -- nullable; single extension point for Phase 2 multi-agent
asset_class        -- enum: stock | option | crypto | cfd
symbol             -- instrument ticker
side               -- enum: long | short
quantity           -- fractional for crypto/cfd
entry_price
exit_price
fees
funding_rate       -- nullable; populated for cfd/crypto perpetuals
realized_pnl
expectancy_at_entry
r_multiple
trigger_spec       -- jsonb, compatible with fundamental/src/lib/trigger-evaluator.ts
order_ref          -- IB orderRef field (~40 chars); bot-trades only
perm_id            -- IB permId; primary join key to trigger tables
approved_by        -- single user in MVP, but field exists
approved_at
notes              -- freetext
opened_at
closed_at
```

Multi-leg options spreads = Phase 2 (likely via `parent_trade_id` + child rows or a separate `trade_legs` table).

## 15. Weekly Rhythm (MVP cadence)

| Week | Shippable artifact |
|---|---|
| 0 | Frozen MCP contract, FastAPI+DuckDB skeleton, "hello world" MCP call renders |
| 2 | Static journal of all historical IB trades + `taxonomy.yaml` |
| 4 | Live journal with Viktor/Satoshi side-by-side, post-hoc tagging UI, faceted filter |
| 6 | cTrader demo connection, 1 agent skeleton, approval UI with Rita/Cassandra risk gate, `strategy-template.md` |
| 8 | Full review loop, regime kill-switch, first real demo trades with provenance |

**Check-in rule:** Every Friday evening: "Does this week's artifact stand?" No → activate descope ladder rung Y, do NOT drag into next week.

## 16. Descope Ladder (defined now, not in week 6)

| Rung | Trigger | Action |
|---|---|---|
| 1 | Week 4 tight | Drop news/trend integration; only fundamental via SFA/CFA |
| 2 | Week 5 tight | cTrader reduced to "read-only spike" (connect + account data + manual paper order, no agent) |
| 3 | Week 6 tight | Strategy Review UI reduced to static metrics page, no agent text loop |
| 4 | Week 7 tight | Options dropped entirely; stocks only. Single-leg options becomes Phase 2. |

**Terminal kill criterion:** If Slice A (Journal + IB) is not fully usable at end of Week 4, ctrader is officially stopped. The platform is not the right vehicle; switching to TradeZella + manual discipline is the honest answer.

## 17. Regime Snapshot & Kill-Switch

- Daily cron job: joins Fear & Greed + VIX with per-broker P&L and per-agent Expectancy delta. One row per day. Drives Phase 2 behavioral regime analysis.
- **Kill-switch (MVP):** Fear & Greed < 20 → bot execution auto-pauses until manual reactivation. Uses `fundamental/src/lib/fear-greed-client.ts` as source of truth.
- Future regime signals (Phase 2): personal regime detection from accumulated journal data — e.g., "Chef's manual options Expectancy collapses in F&G < 25" → automatic behavioral guardrails.

## 18. Open Questions (defer until PRD or kickoff)

- Which asset class for first Bot-Demo strategy? (crypto spot? crypto perpetual? CFD index?)
- First Viktor/Satoshi workflow to integrate as side-by-side view: `investment-decision` or `analyze-stock`?
- Concrete first daytrading strategy family to implement from Gordon's HOT list?
- Tax-CSV exact schema — does a German tax tool expect a specific format (e.g., Elster-kompatibel) or is free CSV fine for personal use?
- Audit-log storage: same DuckDB file or append-only sidecar file?
- How does Chef want to run ctrader? (systemd service? `uv run`? Docker? CLI foreground?)
- Secrets storage approach: `.env` file or system keyring?
- Timezone handling for multi-broker, multi-timezone trade timestamps (IB usually ET, cTrader UTC, German tax records want CET).
- Dependency risk contingency: what if `fundamental` needs breaking changes mid-MVP? Fork or branch or dual-track?

## 19. Scope Signals Summary

**IN MVP (Weeks 0–8):**
- IB read-only sync (stocks + single-leg options) via `ib_async` + Flex Query
- cTrader demo + 1 bot agent + full approval pipeline with Rita/Cassandra risk gates
- Unified journal (FastAPI + HTMX + Tailwind + DuckDB) with Expectancy, R-Multiple, faceted filter, post-hoc tagging UI
- Viktor/Satoshi side-by-side in proposals (MCP calls, zero new `fundamental` code)
- `fundamental` MCP client consumption for fundamentals, news, trigger specs
- Weekly Gordon trend-loop into `strategies/` candidate promotion
- Regime snapshot cron + F&G < 20 kill-switch
- Strategy Review UI with metrics + freetext notes
- `taxonomy.yaml` (Week 2), `strategy-template.md` (Week 6)
- CSV tax export + append-only audit log

**PHASE 2+:**
- 10 agents × 20k € live on cTrader
- Multi-leg options spreads
- Agent-generated auto-improvement of strategies
- Counterfactual + cohort analysis
- Replay-trigger UI button
- Viktor/Satoshi as full strategy authors (not just advisors)
- Extended trigger sources (on-chain, options flow, social sentiment)
- Cross-agent portfolio balancing
- Live cTrader mode switch
- Mobile apps, rich notifications, multi-user

**HARD-REJECTED (do not raise again without explicit user redirection):**
- See Section 10 above.
