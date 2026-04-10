---
title: "Product Brief: ctrader"
status: "complete"
version: "v2"
created: "2026-04-10"
updated: "2026-04-10"
owner: "Christian (Chef)"
inputs:
  - "User interview (2026-04-10, guided discovery)"
  - "/home/cneise/Project/ALT/ctrader/ — prior .NET attempt (CTraderAI.sln), archived"
  - "/home/cneise/Project/ALT/ctrader2/ — prior Python attempt, archived"
  - "/home/cneise/Project/fundamental/ — MCP server for fundamental analysis (HARD dependency)"
  - "/home/cneise/Project/fundamental/_bmad-output/daytrading/trends/trend-radar-2026-03-29.md"
  - "Review panel: Skeptic, Opportunity, Scope-Discipline reviewers (2026-04-10)"
  - "Web research: IB API landscape, LLM trading agents, existing trade journals, 2026 regulatory context"
---

# Product Brief: ctrader

## Executive Summary

**ctrader** ist eine persönliche Trading-Plattform mit zwei Herzen: einem **vereinigten Trade-Journal** für manuelles Aktien- und Options-Trading bei Interactive Brokers, und einer **human-gated AI-Agent-Farm** für Crypto- und CFD-Trading über cTrader — beides in derselben UI, mit demselben Qualitätsmaßstab: *Für jeden einzelnen Trade muss klar sein, warum er stattgefunden hat und was er gebracht hat.*

Der zentrale Anspruch: **Trigger-Provenance als Schema-Konzept, nicht als Notizfeld.** Jeder Trade — ob von Hand gesetzt oder vom Bot ausgeführt — wird bis auf das ursprüngliche Signal, die Indikator-Snapshot, die News oder die LLM-Begründung zurückverfolgt. Kein verfügbares Tool macht das: TradeZella, TraderSync, Tradervue und Edgewonk reduzieren "Trigger" auf manuelle Tags und Screenshots, die nach drei Wochen niemand mehr pflegt. ctrader macht Provenance zur ersten Klasse und zur *Such-Oberfläche*: "Zeig mir alle Verlust-Trades, bei denen ich einen Viktor-Red-Flag überstimmt habe."

Warum jetzt: Der Trend-Radar des bestehenden `fundamental`-Projekts hält fest, dass rein diskretionäres Daytrading 2026 ein strukturelles Nachteil ist — AI-Algorithmen machen 89% des globalen Handelsvolumens aus, algorithmische Trader schlagen diskretionäre konsistent mit Winrates von 55–70%. Gleichzeitig existiert keine Retail-Plattform, die Broker-Execution, Fundamentalanalyse und human-gated LLM-Strategien in einem Tool vereint — der kommerzielle Anreiz ist zu schwach (Haftung, Regulierung), der persönliche Wert ist riesig. ctrader ist die persönliche Antwort darauf.

## Das Problem

Nach zwei abgebrochenen Versuchen (`ctrader` in .NET, `ctrader2` in Python) ist die Ausgangslage eindeutig: Kein verfügbares Tool liefert das, was für diszipliniertes, lernbasiertes Daytrading in 2026 gebraucht wird.

- **Trade-Journals** (TradeZella, TraderSync, Tradervue) sind reine Post-Mortem-Tools. Sie zeigen P&L, aber die Frage *"Warum habe ich diesen Trade gemacht?"* wird über freitextuelle Notizen beantwortet. Die Erkenntnis verpufft.
- **Execution-Frameworks** (NautilusTrader, ib_async, VectorBT) liefern Order-Routing und Backtesting, aber keine Begründungen und keinen Review-Layer. Sie gehen davon aus, dass der Trader die Strategie selbst geschrieben hat.
- **LLM-Trading-Projekte** (TradingAgents, FinMem) generieren Strategien, aber ohne harte Approval-Gates — entweder volles Autopilot oder akademisches Spielzeug.
- **Die persönliche Realität:** Die eigenen Vorprojekte sind an Scope-Explosion gescheitert (`ctrader` hatte 83 FRs über 8 Epics). Fundamentalanalyse wurde parallel in `fundamental` neu aufgebaut, ohne je mit der Execution-Seite zusammenzukommen. Daytrading blieb Theorie.

Der Preis dieses Status quo: Jeder Trade ist ein potenzieller Lerngewinn, der verloren geht, weil der Kontext fehlt. Man wiederholt Fehler, weil das System sie nicht sichtbar macht.

## Die Lösung

ctrader ist eine Single-User-Python-Plattform mit **fünf Kernbausteinen**, die strikt in MVP-Slices gebaut werden:

1. **Unified Trade Journal** — die primäre UI. Jeder Trade ist eine Zeile mit P&L, **Expectancy**, **R-Multiple**, und einem aufklappbaren "Warum"-Block. Das Journal ist zusätzlich eine *Such-Oberfläche*: Facettenfilter nach Trigger-Quelle (News / Viktor / Satoshi / Gordon / manuell), Confidence-Band, *overridden-vs-followed*. Trigger-Provenance wird technisch über **strukturierte JSONB-Spezifikationen** gespeichert (kompatibel mit `fundamental/src/lib/trigger-evaluator.ts` und `watchlist-schema.ts`), zusätzlich verankert über IBs `orderRef`-Feld für Bot-Trades und über Post-hoc-Tagging-UI für manuelle Trades.

2. **Interactive Brokers Sync (read-only)** für manuell gehandelte Aktien und Optionen (im MVP **nur Single-Leg Optionen** — Multi-Leg Spreads sind Phase 2). Live-Executions über `ib_async` (moderner Fork von `ib_insync`), historische Reconciliation über Flex Queries. Für manuelle Trades, die in TWS ohne `orderRef`-Tagging gesetzt wurden, gibt es ein **Post-hoc-Tagging-UI** mit Zeitfenster-Match: das Journal zeigt untagged Trades, Chef ordnet sie in wenigen Klicks einer Strategie / einem Trigger zu.

3. **cTrader Bot-Execution auf Demo-Account** für Crypto und CFDs. MVP-Umfang: **ein Trading-Agent** mit vollständiger Approval-Pipeline. Der Agent schlägt eine Strategie vor → **Rita** (Aktien-Risk, aus `fundamental` SFA) bzw. **Cassandra** (Crypto-Risk, aus `fundamental` CFA) laufen automatisch als Risk-Gate (`red-flag-scan` / `stress-test`) → Chef sieht den Risiko-Report neben dem Freigabe-Button → Chef genehmigt mit expliziter Risikobudget-Angabe → Agent führt auf Demo aus. **Ohne Rita/Cassandra-Green-Flag kein Approval-Knopf.**

4. **`fundamental` MCP-Integration (HARTE Dependency).** ctrader baut *keine* eigene Fundamental-, News- oder Trend-Engine. Stattdessen konsumiert es als MCP-Client die bestehenden Workflows: **SFA** (Viktor + Rita) für Aktien, **CFA** (Satoshi + Cassandra) für Crypto, News-Tool, Trigger-Evaluatoren, Watchlist, Fear & Greed Client, und den Daytrading-Trend-Radar von **Gordon**. Jede Strategie-Proposal enthält *by default* die Fundamental-Einschätzung von Viktor/Satoshi als Side-by-Side-Vergleich zum Agent-Vorschlag. Vor Projektstart (Woche 0) wird ein **versionierter MCP-Contract-Snapshot** gezogen und als Interface-Vertrag eingefroren. Arbeitszeit an `fundamental` läuft gegen das ctrader-8-Wochen-Budget.

5. **Strategy Review UI + Weekly Trend-Loop.** Pro Strategie: Metriken-Dashboard (Expectancy, R-Multiple, Winrate, Drawdown), Trade-Liste, Versionierung, **Freitext-Notizen-Feld** (kein automatischer LLM-Verbesserungsvorschlag — das ist Phase 2). Parallel läuft ein **wöchentlicher Trend-Loop**: ctrader pollt Gordons neuesten Trend-Radar, diffed gegen den vorherigen, und zeigt eine "Was Gordon denkt vs. was deine Agents tun"-Seite. Aus der Trend-Radar-HOT-Liste kann Chef mit einem Klick einen Strategie-Kandidaten erstellen, der direkt in die Approval-Pipeline geht.

### Trade-Datenmodell (Skizze)

Ein einziger Tradesatz mit Spalten:
`id | source (ib|ctrader) | agent_id (nullable) | asset_class (stock|option|crypto|cfd) | symbol | side | quantity | entry_price | exit_price | fees | funding_rate | realized_pnl | expectancy_at_entry | r_multiple | trigger_spec (jsonb) | order_ref | perm_id | approved_by | approved_at | notes | opened_at | closed_at`

Multi-Leg Options-Spreads sind Phase 2. CFDs bekommen `funding_rate` als dedizierte Spalte.

### Frontend-Stack (festgelegt)

**FastAPI + HTMX + Tailwind.** Pure Python, kein Node-Toolchain, server-rendered, schnell zu bauen. Alpine.js nur punktuell wenn wirklich gebraucht. Kein Next.js, kein React, kein eigener Build-Step. Diese Entscheidung ist im Brief final und wird nicht neu eröffnet.

## Was ctrader anders macht

- **Trigger-Provenance als Schema + Such-Oberfläche**, nicht als Tooltip. Das Journal ist ein Query-Interface über das *Warum* jeder Entscheidung.
- **Risk-Gates vor der Approval**, nicht dahinter. Rita und Cassandra laufen automatisch als zweite Meinung bevor Chef den grünen Knopf drücken kann.
- **Viktor und Satoshi als Co-Autoren ab Tag 1.** Jede Proposal zeigt Agent-Vorschlag und Fundamental-Einschätzung side-by-side. Nach 30 Iterationen sieht Chef, welche Einschätzung konsistent die bessere Expectancy hat.
- **Zwei Broker, eine UX.** Aktien/Optionen bei IB (manuell), Crypto/CFDs bei cTrader (Bot). Das Journal macht den Unterschied unsichtbar — gleiche Metriken, gleiche Provenance-Linse.
- **Expectancy statt Win-Rate als Leitmetrik.** Das Journal zeigt beides, priorisiert aber Expectancy und R-Multiple in der Review-UI.
- **`fundamental` als harte Dependency, nicht als optionaler Cache.** Keine Fundamental-Code-Duplikation in ctrader.
- **Regime-aware Behavior-Loop.** Täglicher Snapshot joined Fear & Greed + VIX mit Per-Broker-P&L. Zusätzlich: **Regime-Kill-Switch** — fällt Fear & Greed unter 20, pausiert die Bot-Execution automatisch bis zu manueller Reaktivierung.

## Wer das Produkt nutzt

**Christian ("Chef") — Single User.** Kein kommerzielles Produkt, keine Multi-User-Fantasien, keine SaaS-Metriken. Die Plattform wird ausschließlich für den eigenen Handel gebaut und muss nur eine Person glücklich machen. Das ist bewusst: Es entfernt Onboarding, Mandantenfähigkeit, Billing, Support — und schafft Raum für die drei Dinge, die zählen: *Execution, Verständnis, Verbesserung*.

## Erfolgskriterien

**Produkt-Metriken (beobachtbar, nicht selbst-referenziell):**

- Jede IB-Execution der letzten 30 Tage erscheint im Journal binnen 5 Minuten nach Trade-Schluss.
- Jeder cTrader-Bot-Trade hat eine Non-Null `trigger_spec` in der DB.
- Für ≥80% der IB-Trades wird die Post-hoc-Tagging-UI binnen 48h nach Trade-Schluss benutzt (Bot-Trades sind per Konstruktion 100%).
- Der wöchentliche Trend-Loop liefert jeden Montagmorgen einen aktualisierten Gordon-Diff.
- Rita/Cassandra-Risk-Checks laufen bei 100% der Bot-Approvals.

**Harter Trading-Meilenstein (der einzige, der zählt für MVP-Erfolg):**

- **Expectancy > 0 über mindestens 50 Bot-Demo-Trades** (mit berechnetem 95%-Konfidenzintervall im Review-UI sichtbar).

**North Star (Ambition, KEIN KPI, KEIN Misserfolgs-Trigger):**

- 70% Winrate + 5% Monatsgewinn. Diese Zahlen stehen bewusst außerhalb der Erfolgsmessung — sie würden sonst ein gut funktionierendes System permanent "scheitern" lassen. Das Journal zeigt den Status zu dieser Ambition, ohne sie als Gate zu verwenden.

**Nicht-Code-Deliverables, die während der 2 Monate entstehen müssen:**

- `taxonomy.yaml` — in Woche 2 geschrieben, *bevor* irgendeine UI gebaut wird. Definiert: Trigger-Typen, Exit-Gründe, Fehler-Kategorien, Regime-Tags. Jede spätere Analytics-Seite joined gegen diese Taxonomie.
- `strategy-template.md` — in Woche 6 extrahiert. Schema für: Mandate, Risikobudget, Trigger-Spec-Referenz, Exit-Rules, Kill-Kriterien.

## Scope (MVP — 8 Wochen, fest-getakteter Rhythmus)

### In Scope

1. **Slice A (Wochen 1–4): Journal + IB + `fundamental`** — das erste zeigbare Artefakt
   - Woche 0 (Vorarbeit, <1 Tag): `fundamental` MCP-Contract ziehen und einfrieren. Handshake-Test. DuckDB + FastAPI-Skelett. "Hello World"-Seite, die einen MCP-Call rendert.
   - Woche 1–2: IB Flex Query Import, DuckDB-Schema, `taxonomy.yaml`, statische Journal-Seite aller historischen Trades.
   - Woche 3: Live IB Sync via `ib_async`, Facettenfilter-UI, Post-hoc-Tagging-UI für manuelle Trades.
   - Woche 4: Viktor/Satoshi-Integration in die Journal-Drilldown-Ansicht (zeige für jeden Trade die damalige/aktuelle Fundamental-Einschätzung).
   - **Ende Woche 4: Vollständig benutzbares Journal. Wenn hier nichts Shippbares steht, stopp und descope (siehe Ladder).**

2. **Slice B (Wochen 5–8): cTrader Bot + Approval + Review**
   - Woche 5: cTrader Demo-Account Verbindung (1-Tag-Spike zur Wiederverwendung aus `ctrader2` — Timebox, keine Archäologie). Handshake, Account-Daten, Paper-Order manuell.
   - Woche 6: 1 Trading-Agent Skeleton, Strategy-Template, Approval-UI mit Rita/Cassandra-Risk-Gate, `strategy-template.md` extrahiert.
   - Woche 7: Wöchentlicher Gordon-Trend-Loop, Regime-Snapshot-Cron, Regime-Kill-Switch, faceted Trigger-Search.
   - Woche 8: Strategy Review UI mit Expectancy/R-Multiple, Freitext-Notizen, Stabilisierung, erste echte Demo-Trades laufen.

3. **Regulatorisch-Minimum (über Slice B verteilt):** CSV-Export für Tax-Reporting (Anschaffungs-/Veräußerungspaare nach Abgeltungsteuer-Schema), Audit-Log für jede Approval.

### Explizit Out of Scope (Phase 2+)

- Skalierung auf 10 Bot-Agents × 20k €. **Einzige Architektur-Konzession: eine `agent_id`-Spalte.** Keine Multi-Tenant-Logik, keine Cross-Agent-Reconciliation, keine Per-Agent-Isolation jenseits dieser Spalte. YAGNI.
- cTrader Live-Modus (Demo only im MVP).
- Multi-Leg Options-Spreads.
- Agent-generierter automatischer Strategie-Verbesserungsvorschlag (nur Freitext-Notizen im MVP).
- Counterfactual-/Cohort-Analyse (braucht ≥50 Trades, Phase 2).
- "Replay Trigger"-Button (die Speicherung der Trigger-Spec passiert jetzt, das Replay-UI ist Phase 2).
- Eigene Backtest-Engine (bewusste Entscheidung).
- Eigene News-/Trend-Engine über `fundamental` hinaus.
- Mobile, Auth-System jenseits lokaler Absicherung, Multi-User.
- Eigene Indikator-Bibliothek (direkt `pandas-ta` aufrufen).
- Code-Archäologie in `ctrader`/`ctrader2` jenseits des 1-Tages-Spikes.

## Wöchentlicher Rhythmus & Checkpoints

| Ende Woche | Shippbares Artefakt |
|---|---|
| 0 | MCP-Contract eingefroren, FastAPI+DuckDB-Skelett, Hello-World-MCP-Call rendert |
| 2 | Statisches Journal aller historischen IB-Trades + `taxonomy.yaml` |
| 4 | Live-Journal mit Viktor/Satoshi-Side-by-Side, Post-hoc-Tagging-UI, faceted Filter |
| 6 | cTrader-Demo-Verbindung, 1 Agent Skeleton, Approval-UI mit Risk-Gate, `strategy-template.md` |
| 8 | Vollständiger Review-Loop, Regime-Kill-Switch, erste echte Demo-Trades mit Provenance |

**Check-in-Regel:** Jeden Freitagabend: "Steht das Artefakt dieser Woche?" Nein → Descope-Ladder-Eintrag Y aktivieren, nicht bis nächsten Freitag schleppen.

## Descope-Ladder (definiert *jetzt*, nicht in Woche 6)

- **Stufe 1** (Engpass Woche 4): News/Trend-Integration raus, nur noch Fundamental-Einschätzungen über `fundamental` SFA/CFA.
- **Stufe 2** (Engpass Woche 5): cTrader wird auf "Read-Only Spike" zurückgefahren (Verbindung + Account-Daten + Paper-Order manuell, kein Agent).
- **Stufe 3** (Engpass Woche 6): Strategy Review UI wird zu statischer Metriken-Seite, kein Agent-Freitext-Loop.
- **Stufe 4** (Engpass Woche 7): Optionen komplett raus, nur Aktien. Single-Leg bleibt Phase 2.

**Abbruch-Kriterium (das Metacriterion gegen Versanden):** Wenn an Ende Woche 4 Slice A *nicht* vollständig benutzbar ist, wird ctrader als Projekt offiziell gestoppt. Die Plattform ist dann nicht das richtige Vehikel und ein anderer Ansatz (z.B. TradeZella + manuelle Journal-Disziplin) ist die ehrlichere Antwort.

## Regulatorisch-Minimum

Einzelner Retail-Trader aus Deutschland. Relevant: MiFID II-Suitability, BaFin-Leverage-Caps, MiCA für Crypto, Abgeltungsteuer. Demo-Account im MVP neutralisiert die meisten Live-Trading-Themen. MVP-Commitment: der CSV-Export muss ein steuerlich defensives Format liefern (Anschaffungs-/Veräußerungspaare mit Zeitstempel und Gebühren). Jede Approval wird in einem unveränderlichen Audit-Log festgehalten (wer / wann / welches Risikobudget / welche Risk-Gate-Ergebnisse).

## Tag 1 — Minute Null

Um Scope-Sharks am Start keinen Angriffspunkt zu geben, ist der Tag-1-Eintritt explizit definiert:

1. `cd /home/cneise/Project/fundamental && make start` — MCP-Server läuft.
2. Im neuen ctrader-Repo: `uv init`, FastAPI + DuckDB + mcp-client Dependencies.
3. Ein HTTP-Endpunkt, der einen MCP-Call (z.B. `analyze-crypto BTC`) macht und das Rohergebnis in einer einfachen HTML-Seite rendert.
4. Git init, erster Commit: "feat: hello world — MCP handshake works".

Erwartete Dauer: 2–4 Stunden. Wenn das an Tag 1 nicht steht, ist die `fundamental`-MCP-Dependency schon das erste gebrochene Versprechen — und der Brief muss revidiert werden, bevor Woche 1 beginnt.

## Vision (Phase 2 und darüber hinaus)

Wenn der MVP trägt, wird ctrader zur **persönlichen Trading-Werkstatt**, in der Chef und seine Agent-Farm gemeinsam lernen:

- **10 Agents × 20k € auf Live-cTrader**, jeder mit eigenem Mandat (Momentum, Mean-Reversion, News-Driven, Fundamental-Long, Regime-Adaptive, …). Jeder Agent hat eigene Strategie-Historie und eigenes Approval-Konto.
- **Cross-Agent-Learning**: Der Review-Loop vergleicht Agents untereinander, schlägt Portfolio-Rebalancing vor, identifiziert Strategie-Cluster, die obsolet werden.
- **Counterfactual & Cohort-Lens**: "Was wäre passiert, wenn ich den News-Trigger ignoriert hätte?" und "Wie schlägt sich mein Mean-Reversion-Agent gegen Gordons öffentlichen Vorschlag?"
- **Replay Trigger**: Jeder historische Trigger kann gegen heutige Marktdaten re-evaluiert werden — "würde dieses Signal noch feuern?"
- **Viktor und Satoshi als vollständige Strategie-Autoren**, nicht nur Input-Lieferanten — sie publizieren Strategien in ein gemeinsames `strategies/`-Verzeichnis, ctrader konsumiert sie nach Approval.
- **Erweiterte Trigger-Quellen**: On-Chain für Crypto, Options-Flow für Aktien, Sentiment-Feeds.
- **Multi-Leg Options-Spreads** und cTrader Live-Modus.

Nach 12 Monaten soll ctrader die Antwort auf eine einzige Frage verkörpern: *"Was ist 2026 möglich, wenn ein disziplinierter Einzelner seinem eigenen AI-Team vertraut — und jede Entscheidung nachvollziehen kann?"*
