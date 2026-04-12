---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
workflowCompletedAt: '2026-04-11'
visionInsights:
  leitmetapher: persönliche Trading-Werkstatt
  strategienAlsErsteKlasse: Expectancy/R-Multiple primär pro Strategie, nicht nur pro Trade
  horizonAgnostic: Daytrading + Swing gleichwertig — Horizon ist Strategie-Parameter
  kernDifferenzierer: Trigger-Provenance als durchsuchbares Schema
  coAutoren: fundamental-Agents (Viktor, Satoshi, Rita, Cassandra, Gordon) als Co-Autoren jeder Entscheidung
  reviewSpeedPrinzip: Review eines Trades/einer Strategie darf nie länger dauern als die Analyse zum Trade
  coreInsight: Retail-Trader kann Daytrading-Nachteile nicht durch Infrastruktur kompensieren, aber empirisch herausfinden welcher Horizon/welche Strategien für ihn konsistent funktionieren
  briefPatchDecision: PRD präzisiert Brief ohne Brief-Patch (Option a)
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-ctrader.md
  - _bmad-output/planning-artifacts/product-brief-ctrader-distillate.md
documentCounts:
  briefs: 2
  research: 0
  brainstorming: 0
  projectDocs: 0
workflowType: 'prd'
classification:
  projectType: web-application
  domain: fintech-trading-personal-non-regulated
  complexity: medium-high
  projectContext: greenfield
scopeDecisions:
  csvTaxExport: descoped
  csvTaxExportReason: Broker (IB + cTrader) handle tax reporting directly — no regulatory obligation for the software
  personas: single-user-chef-only
  prdStructure: two-phase-with-phase2-appendix
  ibQuickOrder: aktien-only-trailing-stop-loss-slice-a-woche-3
  ibQuickOrderReason: TWS-Stop-Loss-Setup ist mühselig bei jedem Swing-Trade; Bracket Order via ib_async ist technisch trivial und dockt an bestehende Woche-3-Infrastruktur an. Options Phase 2, kein Descope-Gegengewicht.
  ibQuickOrderDate: '2026-04-12'
  auditLog: retained-for-provenance-not-compliance
gapAnalysis:
  date: '2026-04-11'
  comparedAgainst:
    - TraderSync
    - Tradervue
    - Edgewonk
  planFile: ~/.claude/plans/stateless-petting-island.md
  mvpAdditions:
    - FR13a MAE/MFE pro Trade
    - FR13b P&L-Kalender-Heatmap
    - FR13c Screenshot-Attachment pro Trade
    - FR18a Mistake-Tagging-Facette (orthogonal)
    - FR18b Top-N-Mistakes-Report mit $-Kosten-Aggregation
    - NFR-I6 Intraday-Daten-Integration für MAE/MFE
  phase2Additions:
    - Edge Finder / Auto-Ranking
    - Exit-Efficiency-Metrik
    - Monte-Carlo Performance-Simulator
    - Chart-Playback mit Entry/Exit-Markern
    - Playbook / Pre-Trade-Checklist
    - Tiltmeter / Emotions-Score
    - Agent-Comment-Layer für abgeschlossene Trades
  openArchitectureDecision: MAE/MFE-Datenquelle (IB-Historical vs fundamental/price-MCP)
  pivotEvaluation:
    date: '2026-04-11'
    question: Externes Journal-Tool nutzen und nur Bot entwickeln?
    toolsEvaluated:
      - TradesViz
      - TraderSync
      - Edgewonk
      - Tradervue
    headlessAutoSyncFinding: Nur TradesViz bietet echten pull-basierten Auto-Sync (cTrader Open API OAuth + IB Flex Web Service). TraderSync Sync ist manuell ("not automatic" laut eigener Doku), Edgewonk nur Statement-CSV, Tradervue kein cTrader.
    decision: rejected
    decisionReason: ctrader baut eigenes Journal als Teil des MVP. Die Tier-1-Gap-Analyse-Erkenntnisse (MAE/MFE, Calendar, Screenshot, Mistake-Tagging) sind bereits als FRs integriert. Der Bot-Differenzierer (Trigger-Provenance-Schema + AI-Agent-Approval mit Risk-Gate) ist in keinem der Tools verfügbar und bleibt der Kern-Wert.
    referenceForPhase2: TradesViz als potenzielle optionale Export-Bridge dokumentiert, falls Phase 2 eine Journal-Integration will
---

# Product Requirements Document - ctrader

**Author:** Chef
**Date:** 2026-04-10
**Last Updated:** 2026-04-12 (IB Quick-Order mit Trailing Stop-Loss als Scope-Erweiterung für Slice A aufgenommen)

## Executive Summary

**ctrader** ist eine persönliche Trading-Werkstatt, in der ein disziplinierter Retail-Trader seine human-gated AI-Agent-Farm orchestriert und jede Strategie — über Daytrading und Swing-Trading hinweg, bei Interactive Brokers und cTrader — bis auf den ursprünglichen Trigger zurückverfolgen, vergleichen und empirisch bewerten kann. Die Plattform vereint ein **Trade-Journal für manuelle Aktien- und Options-Trades** (IB, Sync + Quick-Order mit Trailing Stop-Loss) mit einer **human-gated AI-Agent-Execution für Crypto und CFDs** (cTrader Demo) in einer einzigen UI mit einem gemeinsamen Schema — gebaut von und für Christian als einzigen Nutzer.

Der zentrale Anspruch: **Trigger-Provenance ist ein Schema-Konzept, kein Notizfeld.** Jeder Trade — ob vom Bot ausgeführt oder von Hand gesetzt — wird mit strukturierter `trigger_spec` (JSONB), Confidence-Band und den damaligen Fundamental-Einschätzungen der `fundamental`-Agents (Viktor, Satoshi, Rita, Cassandra, Gordon) gespeichert. Das Journal ist damit nicht nur ein Post-Mortem-Tool, sondern eine **Query-Oberfläche über das Warum** jeder Entscheidung. Die Leitfrage, die keine existierende Plattform beantworten kann: *"Zeig mir alle Verlust-Trades, bei denen ich einen Viktor-Red-Flag überstimmt habe."*

Strategien sind in ctrader eine **erste Klasse**: Expectancy, R-Multiple, Winrate und Drawdown werden primär pro Strategie aggregiert, erst sekundär pro Einzel-Trade. Jede Strategie trägt ihren Trading-Horizont (Intraday / Swing / Position) als expliziten Parameter — die Plattform ist horizon-agnostisch, weil nicht die Theorie, sondern die eigenen 50+ Trades entscheiden, welcher Horizont für diesen Trader konsistent funktioniert. Das Review-Interface hat einen harten Design-Anspruch: **ein Trade- oder Strategie-Review darf niemals länger dauern als die Analyse, die zum Trade geführt hat.**

ctrader ist die persönliche Antwort auf ein 2026er Dilemma: Diskretionäres Daytrading ist strukturell im Nachteil (89% Algo-Volumen, professionelle Latenzen und Informationsvorteile), aber vollautonome LLM-Trader sind unverantwortbar. Die einzige tragfähige Architektur für einen disziplinierten Einzelnen ist eine human-gated AI-Agent-Farm mit vollständiger Nachvollziehbarkeit — und ein existierender MCP-Server `fundamental` liefert bereits die Agent-Layer, die hier als Co-Autoren jeder Entscheidung angebunden werden. ctrader ist der fehlende Execution- und Review-Layer.

### What Makes This Special

- **Strategien als erste Klasse + Trigger-Provenance als durchsuchbares Schema.** Kein verfügbares Tool (TradeZella, TraderSync, Tradervue, Edgewonk) speichert das *Warum* strukturiert genug, um es zur Such- und Vergleichsdimension zu machen. ctrader tut das.
- **`fundamental`-Agents als Co-Autoren ab Tag 1.** Jede Strategy-Proposal zeigt Agent-Vorschlag und Fundamental-Einschätzung side-by-side. Rita und Cassandra laufen als automatisches Risk-Gate **vor** dem Approval-Button — ohne Green-Flag kein Approval.
- **Horizon-agnostisch: Daytrading und Swing gleichberechtigt.** Der Trading-Horizont ist Strategie-Parameter, nicht Plattform-Default. Die Plattform zeigt dem Trader empirisch, welcher Horizont und welche Strategien für ihn konsistent profitabel sind.
- **Zwei Broker, ein Journal, ein Schema.** IB für Aktien manuell + Quick-Order mit Trailing Stop-Loss, cTrader für Crypto/CFDs via Bot. Gleiche Metriken, gleiche Provenance-Linse, keine Tool-Silos.
- **Review-Geschwindigkeit als Design-Prinzip.** Der kognitive Aufwand eines Reviews ist kleiner als der Aufwand einer Trade-Analyse. Klickpfade sind kurz, der relevante Kontext steht im selben Viewport, Facettenfilter sind Ein-Klick.
- **Expectancy statt Win-Rate als Leitmetrik.** Das Journal zeigt beides, priorisiert aber Expectancy und R-Multiple im Review-UI — weil Win-Rate ohne Risk-Reward bedeutungslos ist.
- **Regime-bewusst mit Kill-Switch.** Fear & Greed, VIX und Per-Broker-P&L werden täglich snapshotted; Horizont-bewusst pausiert der Kill-Switch Bot-Execution automatisch bei Risiko-Regimen, ohne Swing-Strategien unnötig zu stoppen.

Die folgende Klassifikation ordnet ctrader technisch und organisatorisch ein und hält die wichtigsten Rahmenentscheidungen fest, auf die alle Downstream-Abschnitte (Requirements, Stack, Scope-Governance) Bezug nehmen.

## Project Classification

- **Project Type:** Web Application (server-rendered, single-user, lokal betrieben)
- **Frontend-Stack:** FastAPI + HTMX + Tailwind (Python-only, kein Node-Toolchain)
- **Storage:** DuckDB (embedded, zero-ops)
- **Domain:** Fintech / Retail Trading Platform (personal, non-regulated — Steuerreporting erfolgt direkt über die Broker, keine Compliance-Schicht in der Software)
- **Complexity:** Medium-High — technisch anspruchsvoll durch MCP-Contract zu `fundamental`, zwei Broker-API-Integrationen (`ib_async` + OpenApiPy), Trigger-Provenance-Schema, und human-in-the-loop AI-Agent-Approval-Pipeline. Keine regulatorische Komplexität.
- **Project Context:** Greenfield — dritter Anlauf nach zwei archivierten Vorversuchen (`/home/cneise/Project/ALT/ctrader`, `/home/cneise/Project/ALT/ctrader2`), frischer Bootstrap mit expliziter Descope-Ladder und terminalem Abbruch-Kriterium Ende Woche 4.
- **Entwicklungs-Rhythmus:** Fest-getaktete 8 Wochen mit wöchentlichen shippbaren Artefakten; Slice A (Wochen 0–4, inklusive Woche 0 als <1-Tages-Vorarbeit) = Journal + IB, Slice B (Wochen 5–8) = cTrader Bot + Approval + Review. Die Plattform ist für Single-User gebaut, mit genau einer Multi-Agent-Konzession im MVP-Schema: einer `agent_id`-Spalte.
- **Harte externe Dependency:** MCP-Server `fundamental` (`/home/cneise/Project/fundamental`) liefert SFA-, CFA- und Daytrading-Agents sowie Trigger-Evaluatoren, Watchlist und Fear & Greed Client. Der Contract wird in Woche 0 versioniert eingefroren. Keine Re-Implementierung von Fundamental-/News-/Trend-Logik in ctrader.

## Success Criteria

Erfolgskriterien trennen drei Ebenen: **User Success** (das, was Chef in seinem täglichen Review-Loop spürt), **Business Success** (da "Business" hier = "persönlicher Trader mit Kapital im Risiko" ist, zählt hier das eine harte Trading-Kriterium), und **Technical Success** (was die Plattform technisch leisten muss, damit die beiden anderen Ebenen überhaupt messbar sind). North-Star-Ambitionen werden bewusst **außerhalb** der Erfolgsmessung geführt — sie sind Richtung, kein Gate.

### User Success

- **Review-Geschwindigkeit als Alltagstauglichkeit:** Ein Trade-Drilldown (P&L, Trigger-Provenance, damalige Fundamental-Einschätzung, Strategie-Kontext) ist in ≤3 Klicks ab Journal-Startseite erreichbar und lädt im selben Viewport — ohne Scroll durch Nebensächlichkeiten.
- **Der Chef-Moment — die Leitfrage ist beantwortbar:** *"Zeig mir alle Verlust-Trades, bei denen ich einen Viktor-Red-Flag überstimmt habe"* lässt sich im Journal über Facettenfilter in unter 30 Sekunden beantworten. Analog für: *"Alle Swing-Trades mit Gordon-HOT-Trigger der letzten 8 Wochen"*, *"Alle Approval-Override-Fälle meiner Daytrading-Strategien"*.
- **Taxonomie sitzt:** Nach Woche 4 benutzt Chef die Post-hoc-Tagging-UI für manuelle IB-Trades ohne Nachdenken — Trigger-Typen, Exit-Gründe und Regime-Tags decken ≥95% seiner tatsächlichen Trade-Situationen ab, ohne dass er "Sonstiges" wählt.
- **Strategie-Review ist schneller als Strategie-Planung:** Der Review einer Strategie (alle Trades, Expectancy-Kurve, R-Multiple-Verteilung, gefolgt-vs-überstimmt) ist kognitiv kleiner als die ursprüngliche Strategie-Formulierung. Qualitatives Kriterium — Chef spürt es oder er spürt es nicht.

### Business Success

Da ctrader ein Single-User-Produkt ist, ersetzt "Business Success" hier das, was ein disziplinierter Retail-Trader als *finanziellen Beweis der Funktionstüchtigkeit* betrachtet.

- **Harter Trading-Meilenstein (MVP-Erfolgs-Definition):** **Expectancy > 0 über mindestens 50 Bot-Demo-Trades** auf dem cTrader-Demo-Account, mit berechnetem 95%-Konfidenzintervall, sichtbar im Review-UI. Unter dieser Schwelle wird keine Strategie als "validiert" markiert.
- **Horizont-Empirie:** Nach 50+ abgeschlossenen Trades über Bot + manuell zeigt der Review-Loop pro Horizont (Intraday / Swing / Position) eine Expectancy-Aggregation — Chef kann sehen, welcher Horizont für ihn konsistent im Plus ist und welcher nicht. Das ist das empirische Daytrading-vs-Swing-Urteil des MVP.
- **Provenance-Vollständigkeit:** 100% aller cTrader-Bot-Trades haben eine Non-Null `trigger_spec` in der DB. ≥80% der IB-Trades sind binnen 48h nach Trade-Schluss post-hoc getaggt.
- **Risk-Gate-Disziplin:** Rita/Cassandra-Risk-Checks laufen bei 100% der Bot-Approvals (keine Umgehung möglich — technisch erzwungen).

### Technical Success

- **IB Sync Latency:** Jede IB-Execution erscheint im Journal binnen 5 Minuten nach Trade-Schluss (Live-Sync); historische Reconciliation via Flex Query läuft täglich über Nacht idempotent.
- **MCP-Contract Stabilität:** Der zu Beginn von Woche 0 eingefrorene `fundamental`-MCP-Contract wird über die 8 Wochen versioniert. Breakage des Contracts muss durch einen expliziten Test erkannt werden, nicht durch einen Journal-Fehler im Trade-Review.
- **Wöchentlicher Gordon-Trend-Loop:** Jeden Montagmorgen liegt ein aktualisierter Gordon-Diff mit HOT-Liste und Delta zur Vorwoche vor. Cron-basiert, ohne manuellen Anstoß.
- **Regime-Snapshot & Kill-Switch:** Täglicher Snapshot von Fear & Greed + VIX + Per-Broker-P&L läuft ohne Ausfall. Kill-Switch triggert bei Fear & Greed < 20 eine Pause der Bot-Execution für Strategien mit Horizon ∈ {intraday, swing<5d}. Swing- und Position-Strategien mit längerem Horizont pausieren nicht automatisch (horizon-bewusster Kill-Switch).
- **Zero-Ops-DB:** DuckDB läuft lokal ohne Server, ohne Migrations-Pipeline jenseits der eigenen versionierten Migrations-Skripte. Jede Schema-Änderung ist eine Migration in Git (siehe CLAUDE.md).
- **Audit-Log für Approvals:** Jede Bot-Approval wird in einem unveränderlichen Audit-Log festgehalten (wer, wann, welches Risikobudget, welche Risk-Gate-Ergebnisse, welche Strategie-Version). Nicht aus Compliance-Gründen, sondern als Teil des Trigger-Provenance-Versprechens.

### Measurable Outcomes

Zusammengefasst die **fünf Zahlen**, an denen Ende Woche 8 Erfolg oder Misserfolg gemessen wird:

| # | Metrik | Zielwert | Quelle |
|---|---|---|---|
| 1 | Expectancy über Bot-Demo-Trades (N ≥ 50) | > 0 mit 95%-KI | Review-UI |
| 2 | Bot-Trades mit Non-Null `trigger_spec` | 100% | DB-Query |
| 3 | IB-Trades mit Post-hoc-Tag binnen 48h | ≥ 80% | DB-Query |
| 4 | Rita/Cassandra-Risk-Checks vor Approvals | 100% (technisch erzwungen) | Audit-Log |
| 5 | Wöchentlicher Gordon-Trend-Loop ohne Ausfall | 100% (8/8 Wochen) | Cron-Log |

### North Star (Ambition — KEIN KPI, KEIN Misserfolgs-Trigger)

- **70% Winrate + 5% Monatsgewinn.** Diese Zahlen stehen bewusst *außerhalb* der Erfolgsmessung. Sie würden sonst ein gut funktionierendes System permanent "scheitern" lassen — dabei ist bei realen Trades schon eine Expectancy von 0.3R bei 50% Winrate ein profitables System. Das Journal zeigt den aktuellen Status zu dieser Ambition kontinuierlich an, verwendet sie aber niemals als Gate oder Alarm.

## Product Scope

### MVP - Minimum Viable Product (Wochen 0–8)

**Slice A (Wochen 0–4): Journal + IB + `fundamental`** — das erste zeigbare Artefakt.

- Woche 0 (<1 Tag Vorarbeit): `fundamental`-MCP-Contract ziehen und einfrieren. Handshake-Test. DuckDB + FastAPI-Skelett. "Hello World"-Seite, die einen MCP-Call rendert.
- Woche 1–2: IB Flex Query Import, DuckDB-Schema mit `trade`-Tabelle (inkl. `horizon`, `agent_id`, `trigger_spec` JSONB), `taxonomy.yaml` extrahiert, statische Journal-Seite aller historischen Trades.
- Woche 3: Live IB Sync via `ib_async`, Facettenfilter-UI, Post-hoc-Tagging-UI für manuelle Trades, **IB Quick-Order mit Trailing Stop-Loss** (Aktien-only, Bracket Order via `ib_async`, UI direkt aus Journal/Watchlist).
- Woche 4: Viktor/Satoshi-Integration in die Journal-Drilldown-Ansicht — zeige für jeden Trade die damalige/aktuelle Fundamental-Einschätzung side-by-side.
- **Ende Woche 4: Vollständig benutzbares Journal. Wenn hier nichts Shippbares steht, stopp und descope (siehe Ladder).**

**Slice B (Wochen 5–8): cTrader Bot + Approval + Review**

- Woche 5: cTrader Demo-Account-Verbindung (1-Tag-Spike zur Wiederverwendung aus `ctrader2` — Timebox, keine Archäologie). Handshake, Account-Daten, manuelle Paper-Order.
- Woche 6: **Ein** Trading-Agent mit Skeleton und Strategy-Template. Approval-UI mit automatischem Rita/Cassandra-Risk-Gate. `strategy-template.md` extrahiert mit Pflichtfeldern `horizon` und `typical_holding_period`.
- Woche 7: Wöchentlicher Gordon-Trend-Loop, täglicher Regime-Snapshot-Cron, horizon-bewusster Regime-Kill-Switch, facetted Trigger-Search.
- Woche 8: Strategy Review UI mit Expectancy/R-Multiple/Drawdown-Kurve (aggregiert pro Strategie und pro Horizont), Freitext-Notizen-Feld, Stabilisierung. Erste echte Demo-Trades laufen durch die volle Pipeline.

**MVP-Einzige-Multi-Agent-Konzession:** Eine `agent_id`-Spalte in der `trade`-Tabelle. Sonst keine Multi-Tenant-Logik, keine Per-Agent-Isolation.

**Audit-Log für Bot-Approvals** (inhaltlich: wer, wann, welches Risikobudget, welche Risk-Gate-Ergebnisse, welche Strategie-Version) — im MVP enthalten, als Provenance-Artefakt, nicht als Compliance-Artefakt.

### Out of Scope im MVP (bewusst, explizit)

- **CSV-Tax-Export.** Steuerreporting läuft direkt über die Broker (IB + cTrader), das Produkt muss keinen Abgeltungsteuer-CSV liefern.
- Skalierung auf 10 Bot-Agents × 20k €. Die `agent_id`-Spalte bleibt die einzige Konzession.
- cTrader Live-Modus. Demo only im MVP.
- Multi-Leg Options-Spreads. Single-Leg Optionen bleiben (Sync + Tagging), Multi-Leg ist Phase 2.
- **Options-Order-Platzierung via TWS API.** Im MVP werden nur Aktien-Orders über die Quick-Order-Funktion platziert. Options-Order-Platzierung (erfordert vollständige Kontraktspezifikation mit Strike, Expiry, Right, Multiplier) ist Phase 2.
- Agent-generierter automatischer Strategie-Verbesserungsvorschlag. Nur Freitext-Notizen.
- Counterfactual-/Cohort-Analyse, "Replay Trigger"-UI, eigene Backtest-Engine, eigene News-/Trend-Engine, eigene Indikator-Bibliothek (direkt `pandas-ta` aufrufen), Mobile, Auth jenseits lokaler Absicherung, Multi-User.
- Code-Archäologie in `ctrader`/`ctrader2` jenseits des 1-Tages-Spikes.

> Dieser Abschnitt definiert *was* im Scope ist. Die **Governance-Mechanismen** dazu (Descope-Ladder, Terminal-Kill-Kriterium, Resource-Risks, priorisierte Risk-Watch-Liste) stehen später unter *Project Scoping & Risk Strategy*.

### Growth Features (Post-MVP, Phase 2 Starter)

**Agent- und Execution-Erweiterungen:**
- **Mehrere Bot-Agents parallel** mit Mandat-Isolation (Momentum, Mean-Reversion, News-Driven, Fundamental-Long, Regime-Adaptive, …), jeder mit eigener Strategie-Historie.
- **cTrader Live-Modus** (erst nach 50+ erfolgreichen Demo-Trades mit Expectancy > 0).
- **Options-Order-Platzierung via TWS API** (Single-Leg Options mit Trailing Stop-Loss — erfordert vollständige Kontraktspezifikation mit Strike/Expiry/Right/Multiplier, deutlich aufwändiger als Aktien-Orders).
- **Multi-Leg Options-Spreads** und erweiterte IB-Options-Integration.
- **Erweiterte Trigger-Quellen:** On-Chain für Crypto, Options-Flow für Aktien, Sentiment-Feeds — alles über `fundamental`-MCP-Erweiterungen, nicht in ctrader.
- **Strategy-Notizen mit LLM-Verbesserungsvorschlag** (optional, per Klick, mit explizitem Opt-In — nie automatisch).

**Analyse- und Lern-Loops:**
- **Counterfactual & Cohort-Lens:** *"Was wäre passiert, wenn ich den News-Trigger ignoriert hätte?"*, *"Wie schlägt sich mein Mean-Reversion-Agent gegen Gordons öffentlichen Vorschlag?"* — braucht die 50+-Trade-Basis aus MVP.
- **Replay Trigger:** Historische Trigger gegen heutige Marktdaten re-evaluieren.
- **Edge Finder / Auto-Ranking von Tag-Kombinationen:** Statistisches Ranking aller `trigger_spec`-Kombinationen und Mistake-Tags nach ihrem Effekt auf Expectancy — die Killer-Anwendung des Trigger-Provenance-Schemas. Braucht N ≥ 50 Trades, deshalb Phase 2.
- **Exit-Efficiency-Metrik:** Pro Trade der Anteil des theoretisch maximalen Gewinns (aus MFE), der tatsächlich realisiert wurde. Setzt MAE/MFE aus FR13a voraus.
- **Monte-Carlo Performance-Simulator:** Random-Resampling der Trade-Historie zur Projektion von Equity-Curve-Szenarien. Sinnvoll ab N ≥ 100 Trades.

**Review- und UX-Features aus etablierten Journal-Tools:**
- **Chart-Playback mit Entry/Exit-Markern:** Intraday-Chart des Assets während des Trade-Zeitraums mit visuellen Markern für Entry und Exit. Implementierung via `lightweight-charts`-Widget (lokales JS-File, kein Node-Build). Brückt die visuelle Review-Lücke für Daytrading-Trades.
- **Playbook / Pre-Trade-Checklist für Strategien:** Erweiterung des Strategy-Templates um eine abhakbare Regelliste pro Strategie. Bei manueller Trade-Ausführung macht Chef die Checkliste, bei Bot-Trades erzwingt der Agent die Regeln technisch.
- **Tiltmeter / Emotions-Score pro Trade:** Edgewonks Signatur-Feature — numerischer Emotions-Score pro Trade, korreliert mit P&L. Schlanker Einstieg über Mistake-Tagging (FR18a im MVP), volle Tiltmeter-Tiefe in Phase 2.

**Agent- und Kollaborations-Konzepte:**
- **Agent-Comment-Layer für abgeschlossene Trades:** Viktor, Satoshi und Gordon dürfen nicht nur Proposals bewerten, sondern retroaktiv Kommentare zu abgeschlossenen Trades hinterlegen (*"hätte ich heute anders bewertet"*, *"diese Art Setup läuft aktuell besser/schlechter"*). Konzeptionell eine Übertragung des Tradervue-Mentor-Mode auf den AI-Agent-Ansatz.

### Vision (Phase 2+, langfristig)

ctrader als **persönliche Trading-Werkstatt**, in der Chef und seine Agent-Farm gemeinsam lernen:

- **10 Agents × 20k € auf Live-cTrader**, jeder mit eigenem Mandat und eigenem Approval-Konto.
- **Cross-Agent-Learning:** Der Review-Loop vergleicht Agents untereinander, schlägt Portfolio-Rebalancing vor, identifiziert obsolete Strategie-Cluster.
- **Viktor und Satoshi als vollständige Strategie-Autoren**, nicht nur Input-Lieferanten — sie publizieren Strategien in ein gemeinsames `strategies/`-Verzeichnis, ctrader konsumiert sie nach Approval.
- **Fundamental-getriebene Long-Horizon-Portfolios** (Weeks bis Months), die Viktor und Satoshi selbstständig vorschlagen und Chef genehmigt.

Nach 12 Monaten soll ctrader die Antwort auf eine einzige Frage verkörpern: *"Was ist 2026 möglich, wenn ein disziplinierter Einzelner seinem eigenen AI-Team vertraut — und jede Entscheidung nachvollziehen kann?"*

## User Journeys

Alle Journeys haben denselben User — Chef. Was variiert, ist der **Modus**, in dem er mit ctrader interagiert. Jede Journey ist hier ein konkreter Ablauf, kein Persona-Porträt.

### Journey 1 — Manueller IB-Trade mit Post-hoc-Tagging (Happy Path)

**Modus:** Manueller Trader
**Auslöser:** Chef hat bei Interactive Brokers eine Aktien-Position manuell (TWS, Mobile, oder Web) eröffnet und später geschlossen.

**Ablauf:**
1. **Trade-Ausführung außerhalb ctrader.** Chef handelt in TWS, bewusst ohne `orderRef`-Tagging — er denkt im Moment des Trades nicht an ctrader.
2. **Automatischer Sync.** Die IB-Flex-Query-Nightly-Reconciliation oder der Live-`ib_async`-Stream zieht den Trade binnen 5 Minuten (live) bzw. über Nacht (historisch) in die DuckDB. Der Trade erscheint im Journal mit Status `untagged`.
3. **Journal-Einstieg.** Chef öffnet am nächsten Morgen das Journal. Auf der Startseite sieht er einen "Untagged Trades"-Abschnitt mit einer Zählung.
4. **Drilldown.** Ein Klick auf den Trade öffnet die Detailansicht: P&L, Zeitfenster, Asset-Kontext, die damalige Fundamental-Einschätzung aus Viktor (für Aktien), der Gordon-Trend-Kontext, und ein **Tagging-Formular**.
5. **Tagging.** Chef wählt: Strategie (Dropdown aus `taxonomy.yaml` oder "ad-hoc"), Trigger-Typ, Horizon (intraday/swing/position), Exit-Grund, optional Notizen-Freitext. Ein Klick speichert und setzt den Status auf `tagged`.
6. **Return zur Journal-Liste.** Der Trade verschwindet aus "Untagged", wandert in die Strategie-Aggregation. Expectancy und R-Multiple der zugeordneten Strategie werden neu berechnet.

**Kritischer Moment:** Schritt 5. Wenn das Tagging länger dauert als 60 Sekunden, benutzt Chef es nicht — und das Post-hoc-Tagging-Versprechen bricht. Die `taxonomy.yaml` muss in Woche 2 stehen, damit Dropdown-Optionen am Tag 1 der Journal-Nutzung vollständig sind.

**Requirements, die diese Journey freisetzt:**
- IB Flex Query Import + Live Sync via `ib_async` (Slice A, Woche 1–3)
- DuckDB-Trade-Schema mit `status`, `horizon`, `strategy_id`, `trigger_spec`
- "Untagged Trades"-Widget auf der Journal-Startseite
- Trade-Drilldown-View mit eingebundenem MCP-Call für Viktor/Gordon-Kontext
- Post-hoc-Tagging-Formular mit Taxonomie-Dropdowns
- Recompute der Strategie-Metriken nach Tag-Update

### Journey 2 — Bot-Strategy-Proposal, Risk-Gate und Approval (Slice B Kern)

**Modus:** Bot-Operator
**Auslöser:** Der Trading-Agent hat basierend auf einer Strategie (z.B. "Crypto-Mean-Reversion-Swing") einen Entry-Vorschlag generiert und in ctrader eingereicht.

**Ablauf:**
1. **Benachrichtigung.** Chef sieht auf der Approval-Dashboard-Seite einen neuen "Pending Proposal"-Eintrag. Die Seite zeigt eine Liste aller offenen Proposals mit Agent-Name, Strategie, Asset, Horizon, vorgeschlagener Position, und Status der Risk-Checks.
2. **Drilldown ins Proposal.** Chef klickt auf das Proposal. Die Detailseite zeigt in **einem Viewport**:
   - Agent-Vorschlag: Entry/Stop/Target, Position-Size, Risikobudget, Begründung (strukturiert), `trigger_spec` als lesbare Darstellung
   - **Side-by-side Fundamental-Einschätzung** von Satoshi (Crypto) bzw. Viktor (Aktien, später in Phase 2 für Bot-Trading)
   - **Risk-Gate-Ergebnis** von Cassandra (Crypto) bzw. Rita (Aktien): GREEN / YELLOW / RED mit Detail-Breakdown (`red-flag-scan` / `stress-test` Output)
   - Regime-Kontext: aktuelle Fear & Greed, VIX-Level, horizon-relevanter Kill-Switch-Status
3. **Entscheidung.**
   - Bei **RED Risk-Gate:** Der Approval-Button ist **nicht klickbar**. Chef kann das Proposal nur ablehnen oder zur Revision an den Agent zurückspielen. Technisch erzwungen — kein Workaround.
   - Bei **YELLOW oder GREEN:** Chef kann genehmigen. Ein Pflichtfeld "genehmigtes Risikobudget" muss gefüllt sein (Default = Proposal-Wert, änderbar).
   - Chef kann auch **Viktor/Satoshi überstimmen**, solange das Risk-Gate nicht RED ist — das wird mit einem expliziten `overrode_fundamental=true`-Flag im Audit-Log festgehalten, damit die spätere Query beantwortbar bleibt.
4. **Ausführung.** Nach Approval sendet ctrader die Order über OpenApiPy an den cTrader-Demo-Account. Der Execution-Status wird im Proposal-Detail live aktualisiert.
5. **Audit-Log-Eintrag.** Unveränderlich: wer, wann, welches Risikobudget, welche Risk-Gate-Ergebnisse (volle Snapshots), ob Fundamental überstimmt wurde, welche Strategie-Version.

**Kritischer Moment:** Schritt 2 — der Viewport muss *alle* entscheidungsrelevanten Informationen zeigen. Scroll oder Tab-Wechsel ist ein Design-Versagen. Das ist die Operationalisierung des "Review-Geschwindigkeit"-Prinzips auf dem wichtigsten Single-Klick der Plattform.

**Requirements, die diese Journey freisetzt:**
- cTrader-Demo-Verbindung via OpenApiPy (Slice B, Woche 5)
- Strategy-Template mit Horizon und Risikobudget-Feldern (Woche 6)
- Approval-Dashboard + Proposal-Detail-View (Woche 6)
- MCP-Calls an Satoshi/Cassandra mit Result-Caching
- Automatisches Risk-Gate mit technisch erzwungener RED-Blockade
- `overrode_fundamental`-Flag im Trade-Schema
- Unveränderliches Audit-Log mit Snapshot-Semantik
- Order-Routing und Execution-Status-Tracking

### Journey 3 — Wöchentlicher Strategy-Review (Lern-Loop)

**Modus:** Strategy-Reviewer
**Auslöser:** Freitagabend oder Sonntagmorgen. Chef will wissen, wie seine Strategien über die Woche performt haben — welche weiter laufen, welche pausieren, welche sterben.

**Ablauf:**
1. **Strategy-Liste.** Chef öffnet die Strategy-Review-Seite. Eine Tabelle zeigt alle aktiven Strategien: Name, Horizon, Anzahl Trades (total / diese Woche), Expectancy (total / diese Woche), R-Multiple-Verteilung (Sparkline), Drawdown, Status (aktiv / paused / retired).
2. **Sortierung und Gruppierung.** Chef gruppiert nach Horizon. Er will explizit sehen: "Wie laufen meine Daytrading-Strategien vs. meine Swing-Strategien?" — weil genau das die empirische Frage des MVP ist.
3. **Drilldown in eine Strategie.** Klick öffnet die Strategy-Detailansicht:
   - Expectancy-Kurve über Zeit
   - Liste aller Trades dieser Strategie, sortierbar nach P&L, Datum, Trigger-Typ
   - "Gefolgt vs. überstimmt"-Breakdown bei Fundamental-Agents
   - Freitext-Notizen-Feld mit Versionshistorie
4. **Notiz.** Chef schreibt frei: *"Die Swing-Strategie läuft, aber meine Intraday-Versuche sind nach 12 Trades bei Expectancy -0.2R. Nächste Woche intraday pausieren, swing weiter."*
5. **Aktion.** Chef setzt eine oder mehrere Strategien auf `paused` — das stoppt die Bot-Execution für diese Strategie, ohne sie zu löschen. Die historischen Trades bleiben abrufbar.

**Kritischer Moment:** Schritt 2 + 3. Die Horizon-Gruppierung muss direkt auf der Übersichts-Seite möglich sein, nicht im Drilldown. Das ist das MVP-Horizont-Empirie-Kriterium aus den Success Criteria — es lebt oder stirbt hier.

**Requirements, die diese Journey freisetzt:**
- Strategy-Liste als eigenständige View mit Aggregations-Metriken (Woche 8)
- Gruppierung und Sortierung nach Horizon, Expectancy, Status
- Strategy-Detail-View mit Expectancy-Kurve, Trade-Liste, Override-Statistik
- Freitext-Notizen-Feld mit Timestamped-Versionshistorie
- Strategy-Status-Management (active / paused / retired) mit DB-Enforcement im Bot-Execution-Pfad

### Journey 4 — Trigger-Suche ("Zeig mir alle Trades, bei denen...")

**Modus:** Analyst
**Auslöser:** Chef hat eine These — z.B. *"Ich glaube, meine News-getriggerten Crypto-Shorts sind schlechter als News-getriggerte Longs"* — und will sie im Journal prüfen.

**Ablauf:**
1. **Facettenfilter-UI.** Auf der Journal-Startseite gibt es eine seitliche Facetten-Leiste. Chef klickt Facetten an: Asset-Class = Crypto, Trigger-Quelle = News, Side = Short.
2. **Ergebnis-Liste.** Das Journal zeigt nur noch Trades, die den Filter erfüllen. Eine Mini-Aggregation oberhalb der Liste zeigt: Anzahl, Expectancy, Winrate, R-Multiple-Verteilung.
3. **Gegenprobe.** Chef wechselt Side auf "Long" und vergleicht direkt die Aggregation — das ist die These-Validierung in 2 Klicks.
4. **Speichern als Query** *(nice-to-have, nicht MVP-blockend)*: Chef kann eine Facetten-Kombi als benannte Query speichern, um sie wiederzuverwenden.

**Kritischer Moment:** Schritt 1. Wenn eine relevante Facette fehlt, ist der gesamte Differenzierungs-Anspruch ("durchsuchbares Provenance-Schema") gebrochen. Die Facetten-Taxonomie muss in der `taxonomy.yaml` konsistent sein und muss mindestens umfassen: Asset-Class, Broker, Strategie, Trigger-Quelle (News / Viktor / Satoshi / Gordon / manuell), Confidence-Band, Gefolgt-vs-Überstimmt, Horizon, Regime-Tag zur Trade-Zeit.

**Requirements, die diese Journey freisetzt:**
- Facettenfilter-Komponente (HTMX, server-side) auf der Journal-Seite
- Aggregations-Query pro Facetten-Kombi (DuckDB-Aggregation live)
- Vollständige Trigger-Taxonomie in `taxonomy.yaml`
- JSONB-Query-Unterstützung in DuckDB für `trigger_spec`-Facetten

### Journey 5 — Montagmorgen-Gordon-Diff + Regime-Reaktion

**Modus:** System-Operator
**Auslöser:** Montag, 9:00 Uhr. Chef öffnet ctrader und will wissen: *Was hat sich am Trend-Radar geändert und was bedeutet das für meine laufenden Strategien?*

**Ablauf:**
1. **Gordon-Diff-Seite.** Eine dedizierte Seite zeigt den aktuellen Gordon-Trend-Radar, verglichen mit der Vorwoche. Neue HOT-Picks sind grün markiert, weggefallene rot, unveränderte grau. Der wöchentliche Cron hat das Artefakt bereits über Nacht von Sonntag auf Montag erzeugt.
2. **Kandidaten-Aktion.** Neben jedem HOT-Pick gibt es einen "Strategie-Kandidat erstellen"-Button. Ein Klick öffnet das Strategy-Template mit vorausgefüllten Feldern (Symbol, Horizon aus Gordons Empfehlung, Trigger-Quelle = Gordon). Chef vervollständigt es und speichert als `draft`-Strategie.
3. **Regime-Check.** Auf derselben Seite sieht Chef das aktuelle Fear & Greed und VIX. Ist das Regime kritisch (F&G < 20), sieht er einen prominenten Hinweis mit der Liste pausierter Intraday/Short-Swing-Strategien und einem "Status prüfen"-Link.
4. **Manuelle Reaktivierung (optional).** Falls der Kill-Switch pausiert hat und Chef es anders entscheidet, kann er einzelne Strategien manuell mit explizitem Risikobudget-Override reaktivieren — dokumentiert im Audit-Log als "manual override of kill-switch".

**Kritischer Moment:** Schritt 1. Der Diff muss zum Kaffee am Montag da sein, ohne dass Chef irgendetwas startet. Wenn der Cron nicht zuverlässig läuft, kippt die Wochen-Disziplin.

**Requirements, die diese Journey freisetzt:**
- Wöchentlicher Cron-Job, der Gordons Trend-Radar via MCP holt und als Snapshot speichert (Woche 7)
- Diff-Logik zwischen zwei Snapshots
- Gordon-Diff-View mit Farb-Codierung
- "Strategie-Kandidat aus HOT-Pick erstellen"-Flow
- Regime-Snapshot-Cron (täglich) + horizon-bewusster Kill-Switch
- Kill-Switch-Override-UI mit Audit-Log-Eintrag

### Journey 6 — Quick Order mit Trailing Stop-Loss bei IB (Swing-Trade-Einstieg)

**Modus:** Aktiver Trader
**Auslöser:** Chef hat seine Analyse abgeschlossen (Viktor-Einschätzung gelesen, Chart geprüft, Trigger-Spec im Kopf) und will einen Aktien-Swing-Trade bei Interactive Brokers aufsetzen — inklusive automatischem Trailing Stop-Loss, ohne dafür in die TWS wechseln zu müssen.

**Ablauf:**
1. **Einstieg aus dem Journal oder der Watchlist.** Chef sieht ein Asset (z.B. aus dem Gordon-HOT-Pick oder aus eigenem Research) und klickt "Quick Order". Das öffnet ein kompaktes Order-Formular inline oder als Modal.
2. **Order-Eingabe.** Chef gibt ein: **Symbol** (vorausgefüllt aus Kontext), **Side** (Buy/Sell), **Quantity**, **Limit-Preis** (Entry), **Trailing Stop Amount** (absolut oder prozentual). Das Formular zeigt das berechnete initiale Stop-Level als Vorschau.
3. **Bestätigung.** Chef prüft die Zusammenfassung (Symbol, Seite, Menge, Limit, Trailing-Stop-Betrag, geschätztes Risiko in $) und bestätigt mit einem expliziten "Order senden"-Button. Es gibt keine "One-Click"-Platzierung — die Bestätigung ist Pflicht.
4. **Bracket-Submission.** ctrader sendet eine Bracket Order via `ib_async`: Parent-Order (Limit Buy/Sell) mit `transmit=False`, Child-Order (Trailing Stop) mit `transmit=True`. Beide Orders werden mit einer `orderRef` verknüpft, die ctrader generiert (Idempotenz-Key).
5. **Status-Tracking.** Die Order erscheint im Journal mit Status `submitted`. Sobald IB die Parent-Order füllt, wechselt der Status auf `filled` und der Trailing Stop wird automatisch aktiv (IB-serverseitig). Chef sieht den aktuellen Order-Status im Journal-Eintrag.
6. **Automatisches Tagging.** Der Trade wird im Journal als `auto-tagged` mit Trigger-Quelle und Strategie aus dem Quick-Order-Formular eingetragen — kein Post-hoc-Tagging nötig, weil der Kontext zum Zeitpunkt der Order-Platzierung bekannt ist.

**Kritischer Moment:** Schritt 3. Die Bestätigung muss **alle entscheidungsrelevanten Zahlen** in einem Blick zeigen. Kein Scrollen, kein zweiter Dialog. Und: der Trailing-Stop-Betrag muss prominent sein — das ist der ganze Sinn dieses Features, nicht eine Nebensache.

**Scope-Grenzen dieser Journey:**
- **Nur Aktien** im MVP. Options-Orders erfordern vollständige Kontraktspezifikation (Strike, Expiry, Right, Multiplier) — das ist ein eigenes UI und Phase 2.
- **Kein nachträgliches Editieren** von Stop-Loss-Parametern aus ctrader heraus. Wenn Chef den Trailing Stop anpassen will, macht er das direkt in TWS. ctrader ist Entry-Punkt, nicht Order-Management-System.
- **Kein Take-Profit als dritte Bracket-Leg.** Trailing Stop-Loss ersetzt das — IB managed das Trailing serverseitig.
- **Trailing Stop-Loss wird von IB verwaltet.** ctrader sendet die Order einmal, danach liegt die Verantwortung bei IB. Kein lokales Trailing-Monitoring.

**Requirements, die diese Journey freisetzt:**
- Quick-Order-UI (kompaktes Formular aus Journal/Watchlist-Kontext) — Slice A, Woche 3
- Bracket-Order-Submission via `ib_async` (Parent Limit + Child Trailing Stop)
- `orderRef`-Generierung für Idempotenz (wiederverwendet die bestehende Client-Order-ID-Logik)
- Order-Status-Tracking (submitted / filled / partial / rejected / cancelled) für IB-Orders
- Automatisches Trigger-Tagging bei Order-Platzierung (kein Post-hoc-Tagging nötig)
- TWS/Gateway-Verbindung (bereits Voraussetzung für Live-Sync)

### Journey Requirements Summary

Die sechs Journeys setzen insgesamt folgende **Capability-Cluster** frei, die im FR/NFR-Kapitel strukturiert werden:

| Cluster | Journeys | Slice |
|---|---|---|
| **IB Data Ingestion** (Flex + Live Sync) | J1 | A (Wochen 1–3) |
| **IB Quick-Order** (Bracket mit Trailing Stop-Loss) | J6 | A (Woche 3) |
| **Trade Journal + Drilldown** | J1, J4, J6 | A (Wochen 0–4) |
| **Taxonomy + Post-hoc Tagging** | J1, J4 | A (Wochen 2–3) |
| **Facettenfilter über `trigger_spec`** | J4 | A (Woche 3) |
| **MCP-Integration Viktor/Satoshi/Gordon** | J1, J2, J5 | A+B |
| **cTrader Bot Execution** | J2 | B (Wochen 5–6) |
| **Approval Dashboard + Risk-Gate** | J2 | B (Woche 6) |
| **Audit-Log (unveränderlich)** | J2, J5 | B (Woche 6) |
| **Strategy-Management (Template, Status)** | J2, J3, J5 | B (Wochen 6–8) |
| **Strategy-Review-UI (Aggregation, Notizen)** | J3 | B (Woche 8) |
| **Wöchentlicher Gordon-Trend-Loop (Cron)** | J5 | B (Woche 7) |
| **Regime-Snapshot + Kill-Switch** | J5 | B (Woche 7) |

Die Slice-Zuordnung der Cluster ist konsistent mit dem wöchentlichen Rhythmus aus dem Product Scope.

## Domain-Specific Requirements

ctrader hat keine regulatorischen Anforderungen (Single-User, Steuer-Reporting läuft über die Broker), aber eine Reihe **harter technischer Constraints aus dem Retail-Trading-Domain**, die die Architektur und Stabilität bestimmen. Dieser Abschnitt benennt sie, bevor FRs und NFRs auf ihnen aufbauen.

### Broker-API-Integrationen

Zwei Broker mit sehr unterschiedlichen API-Charakteristika. Beide müssen als **erwachsene Abhängigkeiten** behandelt werden — nicht als "einfache HTTP-Clients".

**Interactive Brokers (`ib_async` + Flex Query):**
- Verbindung läuft über TWS oder IB Gateway als lokalen Proxy; die Software muss wissen, dass TWS/Gateway zwischenzeitlich auto-reconnect machen (nächtliche Wartung, Session-Reset um Mitternacht) und die ctrader-Session entsprechend resilient sein (Auto-Reconnect mit Backoff, State-Recovery nach Reconnect).
- `ib_async` ist der moderne, gewartete Fork — Entscheidung steht, nicht neu eröffnen. `ib_insync` ist tabu (unmaintained seit 2023).
- **Flex Queries** sind das offizielle Tool für historische Reconciliation — sie werden als Batch-Job (täglich über Nacht) gezogen, nicht als Live-Query. Das Resultat ist ein XML, das idempotent in die PostgreSQL eingelesen wird.
- **Dual-Source-Reconciliation:** Live-Sync (`ib_async`) und Flex-Query-Nightly müssen konsistent sein. Bei Abweichungen wird Flex als Source-of-Truth behandelt, der Live-Sync wird korrigiert — nicht umgekehrt.
- **Order-Platzierung (Aktien-only im MVP):** ctrader platziert Bracket Orders via `ib_async` bestehend aus einer Parent-Order (Limit Buy/Sell) und einer Child-Order (Trailing Stop-Loss). TWS/Gateway verwaltet das Trailing serverseitig — ctrader sendet die Order einmal und trackt danach nur den Status. `ib_async` bietet `bracketOrder()` als Convenience-Methode; die Parent-Order wird mit `transmit=False` gesendet, die letzte Child-Order mit `transmit=True`, um atomare Submission zu gewährleisten. **Options-Order-Platzierung ist explizit Phase 2** — die Kontraktspezifikation (Strike, Expiry, Right, Multiplier) und die Ambiguity-Auflösung über `reqContractDetails` erfordern ein eigenes UI.
- **Idempotenz bei Order-Platzierung:** Jede Order erhält eine von ctrader generierte `orderRef` (Client-Order-ID). Bei Retry nach Netzausfall oder Timeout erkennt IB die Duplikat-Order anhand der `orderRef` und lehnt sie ab — kein Doppel-Trade.

**cTrader (OpenApiPy / Protobuf):**
- Protobuf-basiertes API, Session-Auth, Rate-Limits unterhalb der öffentlichen Dokumentation (aus Erfahrung der Vorprojekte).
- **Demo-Account-Nutzung im MVP** neutralisiert die meisten Live-Trading-Themen (Slippage, Partial Fills in Realzeit), aber Order-Routing muss trotzdem idempotent sein — ein erneutes Absenden derselben Order nach Netzausfall darf keinen Doppel-Entry erzeugen.
- **Partielle Wiederverwendung aus `/home/cneise/Project/ALT/ctrader2` nur nach 1-Tages-Spike-Timebox** (siehe Brief): Handshake, Account-Read, Paper-Order. Kein Code-Archäologie-Marathon.

**Gemeinsame Anforderungen für beide Broker-Clients:**
- Idempotenz aller Order-Submits via Client-Order-ID (`orderRef` bei IB, eigene ID bei cTrader) — kein Doppel-Trade durch Retry.
- Rate-Limit-Awareness mit Respekt vor Broker-Quotas (keine aggressiven Polling-Loops).
- Strukturiertes Error-Handling mit Unterscheidung zwischen transient (retry) und terminal (Alert an Chef).

### MCP-Contract-Disziplin

Der `fundamental`-MCP-Server ist die **einzige externe harte Dependency** und braucht entsprechende Behandlung.

- **Versionierter Contract-Snapshot ab Woche 0:** Vor Projektstart wird ein Snapshot der verfügbaren MCP-Tools (`fundamentals`, `price`, `news`, `search`, `crypto`) und Reusable Libraries (`trigger-evaluator.ts`, `fear-greed-client.ts`, `watchlist-schema.ts`) gezogen und als Interface-Vertrag in ctrader eingefroren (Schema, Request/Response-Shapes, Error-Codes).
- **Breakage-Detection als expliziter Test:** Ein Contract-Test läuft täglich gegen den MCP-Server und vergleicht die aktuelle Schema-Antwort mit dem eingefrorenen Snapshot. Bei Abweichung: Alert, bevor es ein User-facing Journal-Fehler wird.
- **Timeout-Policies:** Jeder MCP-Call hat einen expliziten Timeout; bei Timeout zeigt das UI einen klaren Zustand ("Viktor-Einschätzung nicht verfügbar, Stand XX:XX"), der Approval-Flow ist davon nicht blockiert — aber überstimmen bei nicht-verfügbarem Fundamental wird im Audit-Log als `fundamental_unavailable` markiert, nicht als `overridden`.
- **Result-Caching mit klarer Staleness-Semantik:** Fundamental-Einschätzungen sind teuer (LLM-Calls); sie werden gecacht mit TTL pro Asset-Class (z.B. 15min für Crypto, 1h für Aktien), aber mit sichtbarem "Stand: vor X Minuten" im UI.
- **Kein Re-Implement:** Keine lokale News-, Trend- oder Fundamental-Logik in ctrader. Wenn etwas fehlt, wird es in `fundamental` ergänzt (auf ctrader-Zeitbudget) oder akzeptiert, dass es im MVP nicht verfügbar ist.

### Market-Data & Metrik-Determinismus

Trading-Metriken müssen **deterministisch** sein — dieselben Inputs müssen immer dasselbe R-Multiple, dieselbe Expectancy, dasselbe P&L ergeben, unabhängig von Query-Zeitpunkt oder Recompute-Order.

- **Zeit-Handling:** Alle Zeitstempel in DuckDB als UTC; Exchange-TZ (z.B. US/Eastern für IB, UTC für cTrader-Crypto) wird bei der Anzeige konvertiert, nie in der DB gespeichert.
- **P&L-Berechnung:** Gebühren werden *inklusive* Funding-Rates für CFDs gespeichert und in die P&L-Berechnung einbezogen. Keine "Netto vs. Brutto"-Ambiguität — das Journal zeigt eine Wahrheit.
- **R-Multiple & Expectancy:** Formeln sind zentral und getestet definiert (nicht in der View-Layer verteilt). Ein Trade ohne Stop-Loss bekommt R-Multiple `NULL`, nicht "0" — damit Aggregationen sauber zwischen "kein R verfügbar" und "R = 0" unterscheiden.
- **Gap-Handling in historischen Candles:** Fehlende Candles (Handelsfrei-Tage, Exchange-Ausfälle) werden explizit als Gap markiert, nicht interpoliert. Die Entscheidung, wie damit im Review-UI umgegangen wird, ist Teil der Spezifikation (kein stilles Interpolieren).
- **Idempotenz der Reconciliation:** Nightly Flex-Query-Import ist idempotent — wiederholtes Einlesen desselben XML ändert die DB nicht, erzeugt keine Duplikate, korrigiert aber zwischenzeitlich eingelaufene Live-Sync-Fehler.

### Secrets & Local-First-Security

Single-User-lokal ist kein Grund für Schlamperei, aber auch kein Grund für Enterprise-Overhead. Die Anforderungen sind minimal, aber nicht verhandelbar.

- **API-Keys in `.env`, niemals in Git.** `.env` ist in `.gitignore` eingetragen und bleibt dort (siehe CLAUDE.md). Der PRD schreibt diese Policy fest.
- **Secrets-Scope:** IB-Login und cTrader-API-Credentials sind die einzigen Secrets im MVP. Keine Cloud-KMS, keine Vault — `.env` + Filesystem-Permissions reichen für einen Single-User-Localhost.
- **Lokale Netz-Bindung:** FastAPI läuft auf `127.0.0.1`, nicht auf `0.0.0.0`. Keine Port-Forwards ohne explizite Intention.
- **MCP-Auth:** Der `fundamental`-MCP-Server läuft lokal als Sidecar-Prozess; die Authentifizierung ist Prozess-lokal (Unix-Socket bzw. localhost-HTTP mit Shared-Secret). Kein Over-Engineering.
- **Audit-Log-Unveränderlichkeit:** Der Audit-Log (für Approvals) ist technisch append-only — Update/Delete auf dieser Tabelle werden per DB-Constraint oder View-Layer unterbunden. Das ist ein Single-User-Selbstschutz gegen versehentliches Überschreiben, kein Compliance-Ding.

### Operational Risks & Mitigations

Was in einem realen Trading-System kaputtgehen kann und wie ctrader damit umgeht.

| Risiko | Impact | Mitigation (MVP) |
|---|---|---|
| Broker-API-Downtime während offener Bot-Position | Bot verliert Kontrolle über laufenden Trade | Alert an Chef via UI-Banner + Email-Notifier; manuelle Intervention möglich; Audit-Log hält letzten bekannten Status fest |
| MCP-Server `fundamental` crashed während Risk-Check | Approval-Flow blockiert (bewusst — keine Fake-Genehmigung ohne Risk-Gate) | Klare Fehler-UI "Risk-Gate nicht erreichbar", kein Approval möglich, Chef kann manuell Reconnect triggern |
| Clock-Drift zwischen ctrader, Broker und MCP | Trades bekommen falsche Zeitstempel, Aggregationen werden ungenau | NTP-Zeit am Host als Voraussetzung dokumentiert; Broker-Zeitstempel aus der Broker-Antwort übernommen, nicht lokal generiert |
| Duplikat-Detection bei IB-Re-Sync | Trade doppelt im Journal, Expectancy verzerrt | Composite-Key (permId für IB, eigene ID für cTrader) als Unique-Constraint; Duplikat-Erkennung vor Insert |
| Regime-Kill-Switch feuert fälschlich (Datenquellen-Spike) | Legitime Strategien werden pausiert | Kill-Switch-Trigger loggt explizit den Datenquellen-Stand; Chef sieht "ausgelöst weil F&G = 18 um 14:23"; manuelle Reaktivierung mit Audit-Log-Eintrag möglich |
| DuckDB-Datei-Korruption | Journal-Datenverlust | Tägliches Backup via `COPY TO`-Export in ein separates Verzeichnis; Recovery-Prozedur dokumentiert |
| `fundamental`-Contract ändert sich unbemerkt | Trade-Drilldown zeigt plötzlich leere/falsche Fundamental-Einschätzung | Contract-Test täglich gegen MCP-Snapshot; Test-Failure blockiert keine Trades, aber erzeugt UI-Warnung |
| Chef vergisst Post-hoc-Tagging mehrerer Tage | Untagged-Trades akkumulieren, Strategie-Aggregationen unvollständig | "Untagged"-Counter prominent auf Journal-Startseite; keine automatische Alarmierung (das ist Ermessen, nicht Compliance) |

Diese Risiko-Liste ist nicht erschöpfend, aber sie ist die Grundlage, auf der spätere NFRs (Resilience, Observability, Backup) ihre Detailspezifikation aufbauen.

## Innovation & Novel Patterns

ctrader ist kein Markt-Produkt, daher entfällt hier Competitive-Landscape-Analyse. Was bleibt und hier explizit festgenagelt wird: **vier Innovations-Claims, jeweils mit empirischem Validation-Test und Fallback**. Diese Liste ist der Lackmus-Test, an dem Ende Woche 8 gemessen wird, ob die innovativen Bestandteile der Plattform tatsächlich getragen haben — unabhängig davon, ob die Plattform "funktioniert".

### Claim 1 — Trigger-Provenance als durchsuchbares Schema

**These:** Strukturierte `trigger_spec` (JSONB) erlaubt Queries, die kein verfügbares Trade-Journal (TradeZella, TraderSync, Tradervue, Edgewonk) beantworten kann — namentlich Fragen der Form *"Zeig mir alle Verlust-Trades, bei denen ich einen Viktor-Red-Flag überstimmt habe."*

**Validation-Test (Ende Woche 8):** Chef stellt dem eigenen Journal **drei nicht-triviale Queries** (nicht "alle Crypto-Longs", sondern strategische Fragestellungen mit ≥3 Facetten, die Fundamental-Agent-Override einbeziehen) und bekommt binnen 30 Sekunden pro Query ein aggregatorisches Ergebnis. Wenn das gelingt, ist der Claim validiert — das Journal ist dann empirisch eine Query-Oberfläche, nicht nur ein Viewer.

**Fallback:** Wenn Queries mehr als 30 Sekunden oder mehr als 5 Klicks brauchen, ist die Facetten-Taxonomie unter-entwickelt oder das JSONB-Schema zu flach. Die Descope-Ladder liefert keine direkte Antwort — der Fix ist **Taxonomie-Erweiterung statt Scope-Abbau**, gegebenenfalls durch Verzicht auf einen anderen Capability-Cluster (typischerweise: Gordon-Trend-Loop auf statisch reduzieren).

### Claim 2 — Human-Gated AI-Agents mit erzwungenem Risk-Gate

**These:** Eine Architektur, in der AI-Strategie-Proposals durch ein automatisches Fundamental-Risk-Gate (Rita/Cassandra) **technisch blockiert** werden können — ohne Workaround — ist eine Innovation gegenüber existierenden LLM-Trading-Systemen (Autopilot oder rein deskriptiv). Sie bringt die Verantwortung explizit zum Human, ohne ihn zu einem Rubber-Stamp zu degradieren.

**Validation-Test (Ende Woche 8):** Im Audit-Log lassen sich **alle Approvals der letzten 4 Wochen** abrufen, und für ≥1 Fall ist dokumentiert, dass das Risk-Gate technisch geblockt hat (RED) und Chef das Proposal deshalb abgelehnt oder zur Revision zurückgeschickt hat. Zusätzlich: Chef überstimmt an mindestens einem Fall Viktor/Satoshi bei YELLOW/GREEN-Status, das `overrode_fundamental`-Flag steht im Audit-Log. Beides zusammen zeigt: Das Gate wirkt, und der Override-Pfad ist nachvollziehbar.

**Fallback:** Wenn das Risk-Gate in 4 Wochen nie RED geworden ist, liegt das entweder an der Demo-Konservativität (unwahrscheinlich) oder an zu weichen Risk-Kriterien in Rita/Cassandra. Der Fix ist eine Justierung im `fundamental`-Projekt (das `red-flag-scan`/`stress-test`-Scoring), nicht in ctrader — die Innovation wäre trotzdem funktional bewiesen, nur nicht scharf genug justiert.

### Claim 3 — Horizon-agnostische Strategy-Empirie

**These:** Eine Plattform, die Strategien als erste Klasse führt und pro Horizon (Intraday / Swing / Position) aggregiert, beantwortet eine Frage empirisch, die Literatur und Tools dogmatisch beantworten: *"Welcher Horizon funktioniert für DICH?"* Das ist die Antwort auf das 2026er Daytrading-Dilemma (strukturell benachteiligt, aber nicht pauschal tot).

**Validation-Test (Ende Woche 8):** Nach ≥50 abgeschlossenen Trades zeigt das Strategy-Review-UI mindestens zwei verschiedene Horizonte mit eigenständiger Expectancy-Aggregation. Chef kann aus dieser Ansicht **eine konkrete Horizon-Entscheidung** treffen ("Intraday pausieren, Swing weiter" oder umgekehrt). Der empirische Input, nicht die Theorie, treibt diese Entscheidung.

**Fallback:** Wenn nach 8 Wochen nicht genug Trades pro Horizon vorliegen (z.B. nur Swing, weil Intraday im Demo-Setup zu träge ist), ist der Claim weder bewiesen noch widerlegt — sondern **verfrüht**. Dokumentation im Review-UI: "Horizon-Empirie braucht mehr Trades", kein Scope-Abbau. Die Architektur bleibt, die Aussage kommt später.

### Claim 4 — Externalisierte Agent-Layer via MCP

**These:** Die Architektur-Entscheidung, `fundamental` als harte externe MCP-Dependency zu behandeln (statt Fundamental-/News-/Agent-Logik lokal in ctrader nachzubauen), ist eine Innovation auf Projektebene: Sie entkoppelt Agent-Entwicklung von Execution-Entwicklung und macht Viktor/Satoshi/Rita/Cassandra/Gordon zu wiederverwendbaren Diensten, nicht zu ctrader-internen Klassen.

**Validation-Test (Ende Woche 8):** Die `ctrader`-Codebasis enthält **keine** Module für Fundamental-Scraping, News-Aggregation, oder Trend-Analyse. Alle entsprechenden Capabilities sind MCP-Calls. Der Contract-Test (siehe Domain-Requirements) läuft erfolgreich gegen den eingefrorenen Woche-0-Snapshot. Wenn das erfüllt ist, ist die Externalisierung bewiesen.

**Fallback:** Wenn im Verlauf der 8 Wochen eine Capability in ctrader re-implementiert wurde (z.B. weil `fundamental` eine Funktion nicht lieferte und der Umweg über Contract-Erweiterung zu lang war), ist das ein **Scope-Warnsignal**. Es wird im PRD-Retrospektive-Abschnitt dokumentiert und treibt die Entscheidung, ob `fundamental` für Phase 2 priorisiert ausgebaut wird.

### Innovation-Validation-Summary

| Claim | Validation-Test kurz | Fallback-Richtung |
|---|---|---|
| 1. Trigger-Provenance als Schema | 3 nicht-triviale Queries <30s | Taxonomie erweitern, nicht Scope abbauen |
| 2. Human-gated AI mit Risk-Gate | Audit-Log zeigt ≥1 Block + ≥1 Override | Justierung in `fundamental`, nicht in ctrader |
| 3. Horizon-agnostische Empirie | ≥2 Horizonte mit eigener Expectancy-Aggregation | "Verfrüht" statt Fail — Aussage kommt später |
| 4. Agent-Layer via MCP extern | Keine Fundamental-Logik in ctrader-Codebasis | Retrospektive, Priorisierung für Phase 2 |

Diese Tabelle ist am Ende von Woche 8 das explizite Review-Artefakt für die Innovationen — zusätzlich zu den fünf Measurable-Outcomes aus den Success Criteria. Während die Success Criteria fragen *"funktioniert die Plattform?"*, fragt diese Tabelle *"trägt, was daran neu ist?"*.

## Web Application — Technical Stack & Implementation Considerations

Dieser Abschnitt konsolidiert technische Entscheidungen für ctrader. Locked Decisions aus `CLAUDE.md` und Brief werden zur Referenz wiederholt, offene Web-App-spezifische Entscheidungen werden hier geschlossen, damit die Architektur-Phase (nach dem PRD) einen klaren Einstiegspunkt hat.

### Technical Stack (Locked — nicht neu eröffnen)

- **Sprache:** Python 3.12+
- **Dependency-Manager:** `uv` (siehe `CLAUDE.md`)
- **Web-Framework:** FastAPI
- **Frontend:** HTMX + Tailwind + Alpine.js *nur wo wirklich nötig* — kein Node, kein React, kein eigener Build-Step
- **Storage:** DuckDB (embedded, zero-ops)
- **IB-Integration:** `ib_async` + Flex Queries
- **cTrader-Integration:** OpenApiPy (Protobuf)
- **MCP-Client:** gegen lokalen `fundamental`-Sidecar

Alle weiteren technischen Details (Broker-API-Handling, MCP-Contract, Secrets, Market-Data-Determinismus) stehen im Domain-Specific-Requirements-Abschnitt oben.

### URL- & Routing-Struktur

Top-Level-Routen, die der Architektur-Workflow als feste Anker verwendet:

| Route | Zweck |
|---|---|
| `/` | Journal-Startseite (alle Trades, Facettenfilter, Untagged-Widget) |
| `/trades/{id}` | Trade-Drilldown mit Trigger-Provenance und MCP-Kontext |
| `/strategies` | Strategy-Liste (aktiv / paused / retired), gruppierbar nach Horizon |
| `/strategies/{id}` | Strategy-Detail mit Expectancy-Kurve, Trade-Liste, Notizen |
| `/approvals` | Approval-Dashboard (Pending Proposals) |
| `/approvals/{id}` | Proposal-Detail mit Risk-Gate und Approval-Button |
| `/trends` | Gordon-Diff-Seite (wöchentlich + aktueller Stand) |
| `/regime` | Regime-Snapshot-View (Fear & Greed, VIX, Kill-Switch-Status) |
| `/settings` | Taxonomie-Ansicht, Broker-Verbindungsstatus, MCP-Status |
| `/admin/contract-test` | Contract-Test-Ergebnis für MCP-Breakage-Detection |

Die Routen sind **server-rendered** — jede Seite ist ein vollständiger FastAPI-Response mit HTML. HTMX wird für partielle Updates innerhalb einer Seite verwendet (z.B. Facetten-Filter-Aktualisierung, Trade-Tagging-Submission), nicht für Client-Side-Routing.

### Session-Management

Single-User-Localhost — die Anforderung ist minimal, aber nicht null.

- **Kein Login-Screen im MVP.** FastAPI läuft auf `127.0.0.1`, Binding nicht auf `0.0.0.0`. Der Localhost-Zugriff ist der Auth-Layer.
- **Einfache Session-Cookies** nur für UI-State, der über Requests erhalten bleibt (gewählte Facetten, letzte Strategie-Ansicht). Keine serverseitige Session-DB.
- **Kein CSRF-Schutz** im MVP (siehe Scope — Single-User-Localhost). Wird Phase 2 relevant, falls ctrader jemals an einen Reverse-Proxy angeschlossen wird.

### Background-Jobs & Scheduled Tasks

FastAPI hat keinen eingebauten Scheduler. Die Journey 5 (Gordon-Diff Montagmorgen) und Journey 2 (Regime-Snapshot täglich) brauchen verlässliche Scheduled Execution.

- **Tool-Entscheidung:** **APScheduler** als Python-intern eingebetteter Scheduler. Läuft im selben Prozess wie FastAPI (Lifetime-Event beim Start), keine separate Service-Unit, keine Systemd-Timer, kein externes Cron. **Grund:** Single-Process-Einfachheit; für 2–3 Jobs ist dedizierte Infrastruktur Overkill.
- **Idempotenz:** Jeder Job muss bei wiederholter Ausführung am selben Tag idempotent sein (kein Doppel-Snapshot).
- **Failure-Handling:** Job-Fehler werden im UI sichtbar (auf `/regime` und `/trends` wird der "Zuletzt erfolgreich"-Zeitstempel angezeigt). Kein automatisches Retry — Chef entscheidet über manuellen Re-Run.
- **Jobs im MVP:**
  - Täglich 00:15 UTC: IB Flex Query Nightly-Reconciliation
  - Täglich 00:30 UTC: Regime-Snapshot (Fear & Greed + VIX + Per-Broker-P&L)
  - Montag 06:00 UTC: Gordon-Trend-Radar holen und Diff gegen Vorwoche berechnen
  - Täglich 03:00 UTC: MCP-Contract-Test gegen eingefrorenen Snapshot
  - Täglich 04:00 UTC: DuckDB-Backup via `COPY TO` in separates Verzeichnis

### Observability (Minimal)

Kein Grafana, kein Prometheus, kein SaaS-Error-Tracker im MVP. Was stattdessen da ist:

- **Strukturiertes Logging** via `structlog` oder Python-Standard-Logging mit JSON-Format. Logs landen in einer Datei im Project-Root (Rotation via `logging.handlers.RotatingFileHandler`).
- **Request-Logging** von FastAPI middleware: Method, Path, Status, Duration — hilft bei der Review-Geschwindigkeits-Metrik ("fühlt sich alles schnell an?").
- **UI-sichtbarer Health-Status:** Auf `/settings` oder einem Admin-Widget — Broker-Verbindungsstatus (IB, cTrader), MCP-Status, letzte Job-Ausführungen, letzte Contract-Test-Ausführung. So sieht Chef auf einen Blick, ob etwas hängt.
- **Kein Sentry, kein DataDog** — Exceptions landen im Log, kritische Fehler zusätzlich als UI-Banner.

### Deployment & Run-Strategie

- **Lokaler Run:** `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` als Primär-Kommando. Eventuell mit `--reload` in Dev-Mode.
- **Hintergrund-Betrieb:** Für den Dauerbetrieb `systemd --user` Unit oder `tmux`/`screen`-Session. Der Entscheid wird im Architektur-Workflow getroffen, hier ist die PRD-Anforderung: **ctrader muss als Dauer-Prozess laufen können, damit Live-Sync und Scheduled Jobs zuverlässig funktionieren.**
- **DB-Schonung:** DuckDB-Datei liegt im Project-Root (nicht in `/tmp`). Write-Path ist single-process (FastAPI + APScheduler im selben Prozess); keine externen Writer.
- **Logs-Zugriff:** Log-Datei ist über `tail -f` erreichbar; UI zeigt die letzten N Log-Einträge für kritische Ereignisse (Job-Failures, Risk-Gate-Fehler).

### Test-Strategie (realistisch für 8 Wochen)

- **Pyramide:**
  1. **Unit-Tests** für reine Business-Logik: P&L-Berechnung, R-Multiple, Expectancy, Trigger-Spec-Parser, Facetten-Filter-Aggregation. **Hoher Wert, niedriger Aufwand** — das kritischste.
  2. **Integration-Tests** für die DB-Schicht (DuckDB-Migrations, Trade-Reconciliation-Idempotenz, Audit-Log-Append-Only).
  3. **Contract-Tests** gegen `fundamental`-MCP (tägliches Kanarienvogel-Test gegen eingefrorenen Snapshot, siehe Domain-Requirements).
  4. **Broker-Integration-Tests:** Gegen IB Paper-Account und cTrader Demo. Nicht als CI-Test (externe Abhängigkeit), sondern als manuell triggerbares Spike-Skript. Im MVP kein Vollautomat.
  5. **Keine E2E-Browser-Tests** im MVP (Playwright, Selenium) — nicht nötig für Single-User, wäre Zeitverbrennung.
- **Coverage-Ziel:** Keine Prozentzahl. Das Ziel ist "die 10 kritischsten Business-Logik-Pfade haben Tests, die bei Breakage sofort fehlschlagen".
- **Test-Runner:** `pytest` via `uv run pytest`.

### Migrations-Disziplin

`CLAUDE.md` sagt: *"Alle DuckDB-Schema-Änderungen MÜSSEN über versionierte Migrations-Skripte erfolgen. Direkte Schema-Änderungen sind verboten."* Dieser PRD formalisiert das:

- **Verzeichnis:** `migrations/` im Project-Root
- **Nummerierung:** Nullpad-Sequential: `001_initial_schema.sql`, `002_add_horizon.sql`, …
- **Runner:** Ein minimales Python-Skript in `app/db/migrate.py`, das nicht-angewendete Migrationen in aufsteigender Reihenfolge ausführt. Tracking in einer `schema_migrations`-Meta-Tabelle. Kein Alembic, kein Flyway — Overhead für DuckDB nicht gerechtfertigt.
- **Idempotenz:** Jede Migration muss bei wiederholter Ausführung sicher sein (Schutz vor Doppel-Apply).
- **Reversibilität:** Wo sinnvoll, eine `.down.sql`-Datei neben der `.up.sql`. Bei destruktiven Änderungen (DROP) darf `.down` fehlen, mit Kommentar warum.
- **Seed-Daten:** `taxonomy.yaml` wird in Migration `002` oder vergleichbar in die DB geladen. Weitere Seeds nach Bedarf.
- **Kein ORM-Mapping:** DuckDB wird über SQL und `duckdb-python` direkt angesprochen. Kein SQLAlchemy, kein ORM — Trade-Schema ist stabil genug, dass ein ORM Overhead wäre.

### Dev-Tooling

- **Linter/Formatter:** `ruff` für Lint und Format (ein Tool, schnell, moderner Standard).
- **Type-Checker:** `mypy` optional in CI; im MVP pragmatisch statt pedantisch.
- **Kein Monorepo, kein Workspaces.** Ein flaches Python-Projekt.
- **Editor:** egal — kein IDE-spezifisches Tooling, das den Repo-State ändert.

## Project Scoping & Risk Strategy

Die bisherigen Kapitel haben das *Was* des MVP definiert: Success Criteria, User Journeys, Domain Requirements, Functional und Non-Functional Requirements. Dieses Kapitel liefert die **Governance-Mechanismen**, die über die 8 Wochen hinweg sicherstellen, dass der Scope nicht erodiert und das Projekt im Engpass die richtigen Entscheidungen trifft: MVP-Philosophie, Descope-Ladder, Terminal-Kill-Kriterium, Resource-Risks und priorisierte Risk-Watch-Liste. Der detaillierte Produkt-Scope (Slices, In/Out-Scope, Growth, Vision) steht bereits im Abschnitt *Product Scope* weiter oben — dieser Abschnitt ist der Lenkmechanismus, nicht die Scope-Liste.

### MVP-Philosophie

ctrader ist kein klassischer Customer-Discovery-MVP. Es gibt keinen Markt, keinen Validation-Funnel, keine Pricing-Frage. Der MVP-Typ ist:

> **Validated-Learning-MVP für eine persönliche Arbeitshypothese.**

Die Hypothese lautet: *Eine human-gated AI-Agent-Farm mit Trigger-Provenance-Schema ermöglicht einem disziplinierten Retail-Trader empirisch besseres Lernen als ein klassisches Journal.* Der MVP ist die **erste Plattform-Generation, die diese Hypothese überhaupt testbar macht** — mit 50+ Bot-Demo-Trades und den vier Innovation-Claims als Lackmus-Test.

Konsequenzen dieser Philosophie:
- **Keine Nutzerrecherche nötig.** Der Nutzer ist Chef selbst, und seine Bedürfnisse sind im Brief dokumentiert.
- **Keine Skalierungsarchitektur nötig.** Die `agent_id`-Spalte reicht; alles andere ist YAGNI.
- **Kein Marketing, kein Onboarding.** Der MVP startet mit "localhost:8000" und einem `.env`.
- **Harte Qualitätsmaßstäbe gelten trotzdem**, weil echtes Kapital (wenn auch Demo) durch die Pipeline läuft und weil das Journal den Lern-Loop ersetzt, der sonst im Kopf des Traders stattfindet.

### Descope-Ladder

Aus dem Brief übernommen und hier als **operatives Governance-Instrument** festgeschrieben. Die Ladder wird **präventiv** in Woche 0 definiert, nicht reaktiv, wenn es bereits eng wird.

| Stufe | Auslöser | Descope-Aktion |
|---|---|---|
| **1** | Engpass Ende Woche 4 | News/Trend-Integration raus, nur noch Fundamental-Einschätzungen über `fundamental` SFA/CFA. Gordon-Trend-Loop wird auf statische Wochen-Ansicht ohne Diff reduziert. |
| **2** | Engpass Ende Woche 5 | cTrader wird auf "Read-Only Spike" zurückgefahren: Verbindung + Account-Daten + manuelle Paper-Order, kein Agent. Slice B verliert die Automation, behält die Integration. |
| **3** | Engpass Ende Woche 6 | Strategy Review UI wird zu statischer Metriken-Seite (Expectancy, R-Multiple, Anzahl Trades pro Strategie), kein Freitext-Notizen-Loop, keine Versionshistorie. |
| **4** | Engpass Ende Woche 7 | Optionen komplett raus, nur Aktien bei IB. Single-Leg Options bleiben Phase 2. |

**Anwendungsregel:** Jeden Freitagabend prüft Chef explizit: *"Steht das Artefakt dieser Woche?"* Wenn nein → nächste noch nicht gezogene Descope-Stufe sofort aktivieren, nicht bis zum nächsten Freitag vertagen. Die Descope-Entscheidung wird mit Datum und Stufe im Project-Knowledge-Verzeichnis dokumentiert.

### Terminal Kill-Kriterium

Aus dem Brief: **Wenn Slice A (Journal + IB + `fundamental`) Ende Woche 4 nicht vollständig benutzbar ist, wird ctrader als Projekt offiziell gestoppt.**

"Vollständig benutzbar" ist dabei definiert als:
- Alle historischen IB-Trades im Journal sichtbar
- Live-Sync oder zumindest Nightly-Reconciliation funktioniert
- Post-hoc-Tagging-UI für manuelle Trades ist verwendbar (nicht perfekt, aber benutzbar)
- `taxonomy.yaml` ist vollständig und wird vom UI konsumiert
- Trade-Drilldown zeigt Viktor/Satoshi-Kontext (oder Graceful Degradation mit klarer Anzeige "MCP nicht verfügbar")
- Facettenfilter über zumindest 3 Facetten funktioniert
- Eine End-to-End-Session ist möglich: *Trade in TWS machen → Nightly-Sync → Morgen im Journal finden → tagen → im Facettenfilter wiederfinden*

Wird dieser Kriterienkatalog Ende Woche 4 nicht erfüllt, ist die ehrliche Antwort: *"Die Plattform ist nicht das richtige Vehikel für Chef; ein anderer Ansatz (z.B. TradeZella + manuelle Journal-Disziplin) ist pragmatischer."*

Das Kill-Kriterium ist kein Drohen, sondern ein **Meta-Commitment-Device gegen Versanden**. Es verhindert, dass ctrader drei Monate lang "fast fertig" ist.

### Resource-Risks & Contingencies

Der realistische Resource-Rahmen:

- **Team-Größe:** 1 (Chef, mit Claude Code als Pair-Programmer)
- **Zeit-Budget:** 8 Wochen, wöchentlicher Freitag-Check
- **Externe Dependency-Budget:** Arbeit in `fundamental` läuft gegen das ctrader-Budget (siehe Brief)
- **Keine Pufferzeit**, kein "10. Woche zur Sicherheit"

**Risk 1 — MCP-Contract-Spike in Woche 0 zieht sich.**
Wenn der Handshake-Test, das Einfrieren des Contract-Snapshots, oder die erste MCP-Integration in Woche 0 länger dauert als einen Tag, zieht sich die gesamte Kette nach hinten. *Contingency:* Woche-0-Spike ist zeit-geboxt auf einen Tag; bei Überschreitung wird der "Hello World"-Endpunkt auf einen minimalen MCP-Call reduziert (nur einen Tool-Call, nicht die ganze SFA/CFA-Pipeline), und der Rest rutscht in Woche 1.

**Risk 2 — IB Flex Query hat undokumentierte Querks.**
Flex Queries sind gut dokumentiert, aber das XML-Format ist komplex und es gibt Edge-Cases bei Multi-Leg-Trades und Options-Assignments. *Contingency:* Single-Leg Optionen only im MVP (aus dem Brief); bei weiteren Querks Fallback auf reines Aktien-Parsing in Woche 1–2, Optionen-Unterstützung kann auf Woche 3 rutschen.

**Risk 3 — cTrader-Spike in Woche 5 findet den alten Code nicht wiederverwendbar.**
Der Brief gibt 1 Tag für die Prüfung der `/home/cneise/Project/ALT/ctrader2`-Wiederverwendung. Wenn sich herausstellt, dass gar nichts brauchbar ist, verlängert sich Woche 5 unweigerlich. *Contingency:* Descope-Stufe 2 greifen (cTrader Read-Only Spike), Slice B-Ambition auf "Approval-UI mit IB-Paper-Trades simulieren" reduzieren, cTrader-Live für Phase 2.

**Risk 4 — Chef selbst wird durch Tages-Job, Urlaub, Krankheit gebunden.**
Kein Team, keine Vertretung. *Contingency:* Descope-Ladder ist die einzige Antwort; bei Ausfällen wird die nächste Stufe ohne Fragen gezogen. Kein "Aufholen am Wochenende".

**Risk 5 — `fundamental` selbst braucht Arbeit.**
Wenn Viktor/Satoshi/Rita/Cassandra/Gordon in ihrer aktuellen Version Lücken haben, die ctrader braucht, kostet die Behebung Zeit aus dem 8-Wochen-Budget. *Contingency:* Lücken werden dokumentiert und zur Priorisierung an `fundamental` weitergegeben — aber nicht in ctrader umgangen (Claim 4 der Innovation-Validation).

### Priorisierte Risk-Watch-Liste

Aus den Operational Risks (Domain-Requirements) + Resource Risks (oben) priorisiert nach **Impact × Wahrscheinlichkeit**:

| Rang | Risiko | Frühwarnsignal | Mitigation |
|---|---|---|---|
| 1 | MCP-Contract-Drift während Entwicklung | Contract-Test schlägt fehl | Contract wird in Woche 0 eingefroren; Breakage = UI-Warnung + Priorisierung |
| 2 | IB-Live-Sync-Instabilität (`ib_async` Disconnects) | Trades fehlen im Live-Feed | Flex Nightly als Source-of-Truth; Live ist Convenience |
| 3 | Scheduled Job falllt still aus | UI zeigt veralteten "Zuletzt erfolgreich"-Timestamp | UI-Widget mit Health-Status prominent platzieren |
| 4 | Chef's verfügbare Zeit unter Annahme | Freitag-Check zeigt "Artefakt nicht fertig" | Descope-Ladder-Stufe sofort ziehen |
| 5 | cTrader-Rate-Limits härter als erwartet | OpenApiPy-Errors im Log | Rate-Limit-Sleep + Descope-Stufe 2 (Read-Only) |
| 6 | DuckDB-Datei-Korruption | Backup-Recovery nötig | Tägliches Backup + dokumentierte Recovery-Prozedur |
| 7 | Regime-Kill-Switch fälschlich ausgelöst | Legitime Strategien pausieren | Manuelle Override + Audit-Log-Eintrag |
| 8 | Post-hoc-Tagging wird vergessen | "Untagged"-Zähler steigt | Prominente UI-Anzeige; kein Alarm, Ermessen |
| 9 | IB-Quick-Order-Doppelausführung bei TWS-Reconnect | Zwei identische Positionen bei IB | `orderRef`-basierte Idempotenz (NFR-R3a); Bracket-Order mit `transmit=False`/`True`-Pattern |

Ränge 1–3 sind **Hochrisiko mit hoher Wahrscheinlichkeit** — sie brauchen explizite Aufmerksamkeit in Woche 0/1. Ränge 4–5 sind **Hochrisiko mit moderater Wahrscheinlichkeit** und werden durch die Descope-Ladder abgefangen. Ränge 6–8 sind **niedrigere Wahrscheinlichkeit**, werden aber wegen des Single-User-Kontexts ohne Alarm-Systeme bewusst beobachtet statt automatisiert.

## Functional Requirements

Diese Liste ist der **Capability-Contract** für ctrader. Jede FR ist testbar und implementation-agnostic. Die FRs sind in 9 Capability-Areas organisiert, die den Capability-Clustern aus der *Journey Requirements Summary* entsprechen. Features, die hier nicht stehen, werden im MVP nicht gebaut.

### 1. Trade Data Ingestion

- **FR1:** Chef kann historische IB-Aktien-Trades über IB Flex Query in das Journal importieren.
- **FR2:** Chef kann historische IB-Single-Leg-Options-Trades über IB Flex Query in das Journal importieren. Multi-Leg-Spreads sind explizit Phase 2.
- **FR3:** Das System synchronisiert Live-IB-Executions automatisch, ohne manuellen Anstoß.
- **FR4:** Das System erkennt Duplikate bei wiederholtem Sync und verhindert Doppel-Einträge auf Basis einer eindeutigen Broker-ID.
- **FR5:** Das System reconciliert Live-Sync und Flex-Nightly und behandelt Flex-Query als Source-of-Truth bei Abweichungen.
- **FR6:** Das System führt genehmigte Bot-Proposals idempotent auf dem cTrader-Demo-Account aus (kein Doppel-Order bei Retry nach Netzausfall).
- **FR7:** Das System trackt den Execution-Status jedes Bot-Trades (submitted / filled / partial / rejected / cancelled).

### 2. Trade Journal & Drilldown

- **FR8:** Chef kann alle Trades (IB + cTrader) in einer einheitlichen, chronologisch sortierbaren Liste sehen.
- **FR9:** Chef kann einen einzelnen Trade in einer Drilldown-Ansicht öffnen, die P&L, Zeitstempel, Broker, Strategie, Trigger-Provenance, und den damaligen Fundamental-Kontext anzeigt.
- **FR10:** Chef kann das Journal über Facetten filtern. Pflicht-Facetten im MVP: Asset-Class, Broker, Strategie, Trigger-Quelle, Horizon, Gefolgt-vs-Überstimmt-Flag, Confidence-Band, Regime-Tag zur Trade-Zeit.
- **FR11:** Chef sieht auf der Journal-Startseite alle untagged manuellen Trades mit einem prominenten Zähler.
- **FR12:** Chef sieht für jeden Trade P&L (inklusive Gebühren und Funding-Rates bei CFDs), Expectancy-at-Entry, und R-Multiple (oder NULL bei fehlendem Stop-Loss, nie "0").
- **FR13:** Chef kann für jede Facetten-Kombination eine Aggregation abrufen (Anzahl Trades, Expectancy, Winrate, R-Multiple-Verteilung).
- **FR13a:** Chef sieht für jeden Trade **MAE (Maximum Adverse Excursion)** und **MFE (Maximum Favorable Excursion)** — jeweils in Preis-Einheiten und in Position-Dollar-Einheiten. Basis sind Intraday-Candle-Daten für den Trade-Zeitraum (Quelle: Architektur-Entscheidung, IB-Historical oder `fundamental/price`-MCP).
- **FR13b:** Chef sieht einen **P&L-Kalender-View** (Monatsraster, jede Zelle ein Handelstag, Farbe nach Tages-P&L); ein Klick auf eine Zelle öffnet die Liste aller Trades dieses Tages.
- **FR13c:** Chef kann für jeden Trade **einen Screenshot** (z.B. vom Chart zum Entry-Zeitpunkt) hochladen; das System speichert die Datei im lokalen Filesystem und verknüpft sie per Pfad-Referenz mit dem Trade. Die Datei ist im Trade-Drilldown sichtbar.

### 3. Taxonomy & Trigger-Provenance

- **FR14:** Das System lädt die Taxonomie (Trigger-Typen, Exit-Gründe, Regime-Tags, Strategie-Kategorien, Horizon-Optionen) aus `taxonomy.yaml`.
- **FR15:** Chef kann einen manuell ausgeführten Trade post-hoc mit Strategie, Trigger-Typ, Horizon, Exit-Grund und Freitext-Notizen taggen.
- **FR16:** Das System speichert für jeden Trade eine strukturierte `trigger_spec` (JSONB) konform zum `fundamental/trigger-evaluator`-Schema.
- **FR17:** Das System befüllt die `trigger_spec` bei Bot-Trades automatisch aus dem genehmigten Proposal; bei manuellen Trades entsteht sie über die Post-hoc-Tagging-UI.
- **FR18:** Chef kann die `trigger_spec` eines Trades in einer lesbaren, nicht-technischen Darstellung sehen (kein Raw-JSON in der User-Facing UI).
- **FR18a:** Die Taxonomie umfasst eine **separate `mistakes`-Facette** (z.B. `fomo`, `no-stop`, `revenge`, `overrode-own-rules`, `oversized`, `ignored-risk-gate`), die **orthogonal zu Trigger-Quelle und Strategie** pro Trade getaggt werden kann. Ein Trade kann null, eine oder mehrere Mistake-Tags tragen.
- **FR18b:** Chef kann einen **Top-N-Mistakes-Report** abrufen, der Mistakes über ein wählbares Zeitfenster nach **Häufigkeit** und nach **aggregierten $-Kosten** (Summe der P&L aller Trades mit diesem Mistake-Tag) sortiert anzeigt. Der Report ist über die Facetten aus FR10 weiter filterbar.

### 4. Fundamental Intelligence Integration

- **FR19:** Das System ruft via MCP die Fundamental-Einschätzung von Viktor (Aktien, SFA) und Satoshi (Crypto, CFA) für ein gegebenes Asset ab.
- **FR20:** Chef sieht im Trade-Drilldown die **damalige** Fundamental-Einschätzung zum Zeitpunkt des Trades und die **aktuelle** Einschätzung side-by-side.
- **FR21:** Chef sieht im Proposal-Drilldown die aktuelle Fundamental-Einschätzung neben dem Agent-Vorschlag.
- **FR22:** Das System cached Fundamental-Ergebnisse mit einer Staleness-Anzeige im UI ("Stand: vor X Minuten") und einer TTL pro Asset-Class.
- **FR23:** Das System zeigt MCP-Outages im UI als klaren Zustand, ohne das Journal oder andere Views zu blockieren.
- **FR24:** Das System führt täglich einen MCP-Contract-Test gegen den in Woche 0 eingefrorenen Snapshot aus und meldet Abweichungen ohne Trade-Flow-Blockade.

### 5. Bot Execution & Approval Pipeline

- **FR25:** Chef sieht alle offenen Bot-Proposals in einem Approval-Dashboard mit Agent-Name, Strategie, Asset, Horizon, vorgeschlagener Position und Risk-Gate-Status.
- **FR26:** Chef sieht im Proposal-Drilldown alle entscheidungsrelevanten Informationen in einem Viewport: Agent-Vorschlag (Entry/Stop/Target, Position-Size, Risikobudget, strukturierte Begründung), Fundamental-Einschätzung, Risk-Gate-Ergebnis, Regime-Kontext.
- **FR27:** Das System führt bei jedem Proposal automatisch ein Risk-Gate via Rita (Aktien) bzw. Cassandra (Crypto) mit einem dreistufigen Ergebnis aus: GREEN, YELLOW, RED.
- **FR28:** Das System blockiert den Approval-Button technisch, wenn das Risk-Gate RED liefert. Es gibt keinen Workaround zur Umgehung der RED-Blockade.
- **FR29:** Chef kann bei YELLOW- oder GREEN-Status ein Proposal mit explizit gesetztem Risikobudget genehmigen (Pflichtfeld, Default aus Proposal).
- **FR30:** Chef kann ein Proposal ablehnen oder zur Revision an den Agent zurückschicken.
- **FR31:** Chef kann die Fundamental-Einschätzung (Viktor/Satoshi) bei YELLOW- oder GREEN-Status überstimmen; das System setzt in diesem Fall das `overrode_fundamental=true`-Flag im Audit-Log.
- **FR32:** Das System speichert für jede Approval einen unveränderlichen Audit-Log-Eintrag mit: Zeitstempel, genehmigtes Risikobudget, Risk-Gate-Snapshot (volle Response), Override-Flags, Strategie-Version, Fundamental-Einschätzung.

### 6. Strategy Management & Review

- **FR33:** Chef kann Strategien über ein Strategy-Template definieren mit Pflichtfeldern: Name, Asset-Class, Horizon (intraday/swing/position), Typical-Holding-Period, Trigger-Quelle(n), Risikobudget pro Trade.
- **FR34:** Chef sieht eine Strategy-Liste mit Aggregations-Metriken pro Strategie (Anzahl Trades total und diese Woche, Expectancy, R-Multiple-Verteilung, Drawdown, aktueller Status).
- **FR35:** Chef kann die Strategy-Liste nach Horizon gruppieren und nach beliebiger Metrik sortieren.
- **FR36:** Chef sieht in der Strategy-Detailansicht die Expectancy-Kurve über Zeit, die vollständige Trade-Liste der Strategie, und einen "Gefolgt-vs-Überstimmt"-Breakdown gegen die Fundamental-Agents.
- **FR37:** Chef kann Freitext-Notizen zu einer Strategie schreiben; das System speichert jede Notiz mit Zeitstempel als eigene Versionshistorie-Entry.
- **FR38:** Chef kann eine Strategie zwischen den Status `active`, `paused` und `retired` wechseln.
- **FR39:** Das System verhindert im Bot-Execution-Pfad, dass Strategien mit Status `paused` oder `retired` neue Proposals generieren.
- **FR40:** Chef sieht Expectancy-Aggregationen pro Horizon (intraday vs swing vs position) über alle Strategien hinweg, um empirische Horizont-Entscheidungen zu treffen.

### 7. Market Regime & Trend Awareness

- **FR41:** Das System erzeugt täglich einen Regime-Snapshot mit Fear & Greed, VIX, und Per-Broker-P&L.
- **FR42:** Das System pausiert bei Fear & Greed < 20 automatisch alle Strategien mit Horizon ∈ {intraday, swing<5d} (horizon-bewusster Kill-Switch).
- **FR43:** Das System pausiert Strategien mit längerem Horizon (swing≥5d, position) NICHT automatisch bei Fear & Greed-Drops.
- **FR44:** Chef kann einen aktiven Kill-Switch manuell für einzelne Strategien überschreiben; das System dokumentiert jeden Override als Audit-Log-Eintrag "manual override of kill-switch".
- **FR45:** Chef sieht den aktuellen Regime-Stand (F&G, VIX, pausierte Strategien durch Kill-Switch) auf einer Regime-Seite.
- **FR46:** Das System holt wöchentlich (Montag morgen) den aktuellen Gordon-Trend-Radar via MCP und speichert ihn als Snapshot.
- **FR47:** Das System berechnet einen Diff zwischen dem aktuellen und dem Vorwochen-Snapshot und zeigt HOT-Picks farblich kategorisiert (neu / weggefallen / unverändert).
- **FR48:** Chef kann aus einem Gordon-HOT-Pick direkt einen Strategie-Kandidaten erstellen; das System füllt Symbol, Horizon und Trigger-Quelle (=Gordon) vorab aus, Chef vervollständigt den Rest.

### 8. Operations, Health & Data Integrity

- **FR49:** Das System führt Scheduled Jobs (IB Flex Nightly, Regime-Snapshot, Gordon-Weekly, MCP-Contract-Test, DuckDB-Backup) zu definierten Zeiten aus und loggt jede Ausführung mit Status.
- **FR50:** Chef sieht einen Health-Widget mit Broker-Verbindungsstatus (IB und cTrader), MCP-Status, Zeitstempel der letzten erfolgreichen Job-Ausführungen, und dem aktuellen Contract-Test-Ergebnis.
- **FR51:** Das System führt alle DuckDB-Schema-Änderungen ausschließlich über versionierte, idempotente Migrations-Skripte aus (`migrations/001_*.sql`, etc.) mit Tracking in einer `schema_migrations`-Meta-Tabelle.
- **FR52:** Das System erstellt tägliche DuckDB-Backups via `COPY TO` in ein separates Verzeichnis; die Recovery-Prozedur ist im Project-Knowledge dokumentiert.

### 9. IB Quick-Order (Aktien mit Trailing Stop-Loss)

- **FR53:** Chef kann aus dem Journal oder der Watchlist heraus eine **Quick-Order** für eine IB-Aktie aufgeben, bestehend aus: Symbol (vorausgefüllt aus Kontext), Side (Buy/Sell), Quantity, Limit-Preis, Trailing-Stop-Amount (absolut in $ oder prozentual).
- **FR54:** Das System zeigt vor Absendung eine **Bestätigungs-Zusammenfassung** mit allen Order-Parametern (Symbol, Seite, Menge, Limit, Trailing-Stop-Betrag, berechnetes initiales Stop-Level, geschätztes Risiko in $). Die Bestätigung erfordert einen expliziten Klick — keine One-Click-Platzierung.
- **FR55:** Das System sendet die Order als **Bracket Order** via `ib_async`: Parent-Order (Limit) + Child-Order (Trailing Stop-Loss). Die Submission ist atomar (`transmit=False` auf Parent, `transmit=True` auf letzter Child-Order). Jede Order erhält eine von ctrader generierte `orderRef` für Idempotenz.
- **FR56:** Das System trackt den **Order-Status** für IB-Quick-Orders (submitted / filled / partial / rejected / cancelled) und aktualisiert den zugehörigen Journal-Eintrag.
- **FR57:** Bei Order-Platzierung über Quick-Order wird der Trade automatisch mit Strategie, Trigger-Quelle und Horizon aus dem Quick-Order-Formular getaggt (**auto-tagged** statt `untagged`). Kein Post-hoc-Tagging nötig.
- **FR58:** Das System unterscheidet im UI klar zwischen Fehlern, die ein Retry rechtfertigen (transient: Netzausfall, TWS-Reconnect) und solchen, die eine Aktion erfordern (terminal: Margin-Fehler, ungültiges Symbol, Markt geschlossen). Bei transienten Fehlern wird der Retry automatisch ausgeführt (max 3×, mit Backoff); bei terminalen Fehlern sieht Chef eine klare Fehlermeldung.

**Scope-Einschränkungen (bindend):**
- **Nur Aktien.** Options-Order-Platzierung ist Phase 2 (erfordert vollständige Kontraktspezifikation mit Strike/Expiry/Right/Multiplier und ein eigenes UI).
- **Kein nachträgliches Editieren** von Order-Parametern (Stop-Loss-Anpassung etc.) aus ctrader. Dafür TWS direkt verwenden.
- **Kein Take-Profit** als dritte Bracket-Leg. Trailing Stop-Loss ersetzt das — IB managed das Trailing serverseitig.

### Power-User-UX (FR59–FR62) — nachträglich aus UX-Spec in PRD überführt am 2026-04-12

Diese vier Features stammen aus der UX Design Specification und wurden beim Epic-Breakdown pragmatisch in die Epics aufgenommen. Nach dem Implementation Readiness Review vom 2026-04-12 sind sie hier als formelle FRs nachdokumentiert, um Traceability zwischen PRD und Epics sicherzustellen. Alle vier sind niedrig-Aufwand, hoch-Wert und passen konsistent zu Chefs Keyboard-First-Power-User-Profil.

- **FR59:** Chef kann via **Command Palette (`Ctrl+K`)** per Fuzzy-Search schnell zu beliebigen Views, Strategien, Trade-IDs oder gespeicherten Query-Presets navigieren, ohne Maus-Navigation. Die Palette öffnet sich als 600px zentriertes Overlay, Escape schließt, Enter navigiert.
- **FR60:** Chef kann die **aktuelle Journal-Ansicht** (inklusive aktiver Facetten-Filter) als **CSV exportieren**, um externe Analysen in Excel o.ä. durchzuführen. Der Export respektiert den aktiven Filter-Stand.
- **FR61:** Chef kann eine Facetten-Filter-Kombination als **benannten Query-Preset** speichern (z.B. "Satoshi Overrides Lost") und diese Presets über die Command Palette schnell aufrufen. Ein Star-Icon im Hero-Block triggert das Speichern.
- **FR62:** Jede Journal-View mit aktiven Filtern produziert eine **bookmarkbare URL**, über die die exakte Filter-Kombination wiederhergestellt werden kann. Browser-Back funktioniert als natürliches State-Management. Die URL ist shareable (Copy-Paste an externe Analyst-Tools möglich).

**Capability-Contract-Hinweis:** Diese 62 FRs (FR1–FR52 + FR53–FR58 + FR59–FR62) sind **bindend** für alle Downstream-Workflows (UX Design, Architektur, Epic Breakdown, Story Implementation). Features außerhalb dieser Liste werden im MVP nicht implementiert, außer sie werden explizit als Änderung dieses Kapitels dokumentiert. Die Descope-Ladder (siehe oben) definiert, welche FR-Cluster im Ernstfall zurückgefahren werden. FR59–FR62 haben Descope-Priorität 1 (als erste rauscuttbar bei Zeitdruck), da sie reine Power-User-Ergonomie sind und keine Kern-Funktionalität blockieren.

## Non-Functional Requirements

Dieser Abschnitt listet messbare Quality-Attributes. Für jede NFR ist ein konkretes Kriterium definiert, an dem sie testbar ist. Begründung und Kontext zu den Entscheidungen stehen in den vorherigen Abschnitten (*Domain Requirements*, *Web Application Stack*, *Success Criteria*) — hier stehen nur die Zahlen und Schwellwerte.

**Ausgeschlossene Kategorien** (bewusst leer): Scalability (Single-User, YAGNI), Accessibility (ein einzelner Nutzer ohne dokumentierten Bedarf), Internationalization (Deutsch im UI, keine Lokalisierung), Compliance (keine Regulatorik — siehe Classification).

### Performance

Performance ist für ctrader ein **Review-Speed-Kriterium**, keine Enterprise-Latency-Disziplin. Die Zahlen sind auf Localhost-Betrieb mit realistischer Datenmenge kalibriert (initial 100–500 Trades, nach 8 Wochen ~200 zusätzliche Bot-Trades).

- **NFR-P1:** Die Journal-Startseite (FR8) lädt vollständig (inkl. Untagged-Widget und oberster 100 Trades) in **≤ 1.5 Sekunden** bei einer Datenbank mit ≤ 2000 Trades.
- **NFR-P2:** Der Trade-Drilldown (FR9) lädt in **≤ 3 Sekunden** inklusive Fundamental-Einschätzung via MCP bei Cache-Miss, und in **≤ 500 ms** bei Cache-Hit.
- **NFR-P3:** Ein Facettenfilter-Update (FR10) aktualisiert die Trefferliste in **≤ 500 ms** bei einer Datenbank mit ≤ 2000 Trades.
- **NFR-P4:** Die Aggregations-Anzeige (FR13) für eine Facetten-Kombination (Count, Expectancy, Winrate, R-Multiple-Verteilung) berechnet sich in **≤ 800 ms** bei ≤ 2000 Trades.
- **NFR-P5:** Das Approval-Dashboard (FR25) und der Proposal-Drilldown (FR26) laden in **≤ 2 Sekunden** inklusive aller notwendigen MCP-Calls (Fundamental, Risk-Gate) bei Cache-Miss.
- **NFR-P6:** **Kognitives Review-Kriterium (qualitativ):** Ein Trade-Drilldown ist in **≤ 3 Klicks** ab der Journal-Startseite erreichbar; eine Facetten-Abfrage mit 3 Facetten in **≤ 4 Klicks**. Qualitativ getestet, nicht durch Benchmark.

### Security & Privacy

Security ist für ctrader **Localhost-First + Defense-in-Depth-Minimal**. Die Begründung steht im Abschnitt *Secrets & Local-First-Security*.

- **NFR-S1:** API-Credentials (IB, cTrader, MCP) liegen ausschließlich in `.env`-Dateien oder Systemumgebungsvariablen. Die `.gitignore` enforced das; ein Commit-Hook (`pre-commit`) prüft optional.
- **NFR-S2:** FastAPI bindet ausschließlich an `127.0.0.1`. Kein Binding auf `0.0.0.0` im MVP. Jede Abweichung erfordert eine explizite PRD-Änderung.
- **NFR-S3:** Der Audit-Log für Approvals ist **technisch append-only**: Update- und Delete-Operationen auf der `approval_audit_log`-Tabelle werden per DB-Constraint oder Anwendungs-Layer unterbunden. Testbar über einen Negative-Test im Test-Suite.
- **NFR-S4:** Keine Telemetrie, kein externes Error-Tracking (Sentry, DataDog) im MVP. Alle Logs bleiben lokal.
- **NFR-S5:** Die DuckDB-Datei und das Backup-Verzeichnis haben restriktive Filesystem-Permissions (`0600` für Files, `0700` für Verzeichnisse), damit andere Nutzer des Host-Systems nicht lesen können.

### Reliability & Data Integrity

Reliability ist das wichtigste NFR-Kapitel für ctrader, weil Trade-Daten-Verlust oder Duplikate den gesamten Lern-Loop kaputtmachen.

- **NFR-R1:** Die IB-Sync-Pipeline (Live + Nightly) erkennt Duplikate deterministisch anhand der Broker-Unique-ID (`permId`) und verhindert Doppel-Einträge. Testbar durch wiederholtes Einlesen desselben Flex-Query-XMLs: **die DB-Row-Count darf sich nicht ändern.**
- **NFR-R2:** Der Live-IB-Sync übersteht TWS/Gateway-Reconnects (nächtliche Wartung, Session-Reset) mit automatischem Auto-Reconnect und State-Recovery, ohne dass Trades verloren gehen. Verifiziert durch das **Dual-Source-Reconciliation-Kriterium** (Flex-Nightly als Source-of-Truth korrigiert Live-Lücken).
- **NFR-R3:** Genehmigte Bot-Orders sind idempotent: Ein Retry nach Netzausfall oder Timeout darf **keinen Doppel-Order** erzeugen. Testbar durch Replay des Order-Submit mit identischer Client-Order-ID.
- **NFR-R3a:** IB-Quick-Orders (FR55) sind idempotent: Die `orderRef` (Client-Order-ID) ist der Idempotenz-Key. Ein Retry nach TWS-Reconnect oder Netzausfall darf keinen Doppel-Trade erzeugen. Testbar durch Replay des `placeOrder`-Calls mit identischer `orderRef`.
- **NFR-R3b:** Die Quick-Order-Bestätigungs-UI (FR54) zeigt **alle entscheidungsrelevanten Zahlen** (Symbol, Seite, Menge, Limit, Trailing-Stop-Betrag, initiales Stop-Level, geschätztes Risiko in $) **ohne Scrollen in einem Viewport**. Kein zweiter Dialog, kein versteckter Parameter.
- **NFR-R4:** Der MCP-Contract-Test (FR24) läuft täglich erfolgreich. Bei Abweichung erscheint ein UI-Warnbanner binnen 24 Stunden nach Drift, der Trade-Flow ist nicht blockiert.
- **NFR-R5:** Tägliche DuckDB-Backups (FR52) schreiben erfolgreich in das Backup-Verzeichnis mit einem Alter ≤ 24 Stunden. Der Health-Widget (FR50) zeigt den Zeitstempel des letzten erfolgreichen Backups sichtbar.
- **NFR-R6:** Graceful Degradation bei MCP-Outage: Die Journal-, Strategy- und Regime-Views bleiben funktional, Fundamental-Einschätzungen zeigen einen klaren "Nicht verfügbar"-Zustand (FR23). Der Approval-Flow ist entsprechend behandelt — bei MCP-Timeout vor Risk-Gate wird das Proposal in einen expliziten "Risk-Gate nicht erreichbar, Approval blockiert"-Zustand gesetzt (siehe Operational Risks Tabelle).
- **NFR-R7:** Schema-Änderungen laufen ausschließlich über versionierte, idempotente Migrations (FR51). Ein Test verifiziert, dass alle Migrations in `migrations/` zweimal angewandt dasselbe DB-State erzeugen wie einmal.
- **NFR-R8:** Das Audit-Log enthält für jede Approval einen vollständigen Snapshot (Risk-Gate-Response, Fundamental-Response, Strategie-Version). Ein Test-Case verifiziert, dass aus dem Log allein eine historische Approval-Entscheidung reproduzierbar ist, auch wenn Rita/Cassandra ihre Meinung zwischenzeitlich geändert haben.

### Integration & External Dependencies

Begründung steht im Abschnitt *Broker-API-Integrationen* und *MCP-Contract-Disziplin*. Hier die messbaren Kriterien:

- **NFR-I1:** Jeder MCP-Call hat einen expliziten Timeout von **≤ 10 Sekunden** (konfigurierbar). Nach Timeout zeigt das UI einen "Nicht verfügbar"-Zustand, und die Request wird nicht automatisch retried.
- **NFR-I2:** MCP-Fundamental-Calls werden mit TTL-Cache versehen: **15 Minuten TTL für Crypto-Assets, 1 Stunde TTL für Aktien.** Die Staleness ist im UI sichtbar ("Stand: vor X Minuten").
- **NFR-I3:** Broker-API-Calls respektieren Rate-Limits und verwenden exponentielles Backoff bei HTTP-429 oder äquivalenten Broker-Fehlern. Der Backoff-Start ist **1 Sekunde**, der Maximum-Backoff **60 Sekunden**, mit maximal **5 Retries** pro Request.
- **NFR-I4:** Der wöchentliche Gordon-Trend-Loop (FR46) ist zur Referenzzeit (Montag 06:00 UTC) erfolgreich abgeschlossen mit einer Erfolgsrate von **8/8 Wochen** im MVP (siehe Measurable Outcome #5).
- **NFR-I5:** Das MCP-Contract-Test-Ergebnis (FR24) ist in allen 8 Wochen des MVP entweder "PASS" oder enthält dokumentierte Drifts, die manuell verifiziert wurden. Kein stilles Fail.
- **NFR-I6:** Das System bezieht Intraday-Candle-Daten (1m/5m-Granularität) für den jeweiligen Trade-Zeitraum zur Berechnung von MAE/MFE (FR13a). Datenquelle ist quellen-agnostisch spezifiziert — die Architektur-Phase entscheidet zwischen IB-Historical-Data (nativ für IB-Trades), `fundamental/price`-MCP-Tool (einheitlich für Aktien und Crypto) oder beidem. Requests werden mit Cache-TTL versehen (Empfehlung: **24h** für historische Candles, da nicht revisionsbehaftet), haben einen Timeout von **≤ 15 Sekunden**, und degradieren graceful (MAE/MFE-Felder sind `NULL` bei Datenquellen-Ausfall, nicht "0").

### Maintainability & Operability

Begründung steht im Abschnitt *Web Application — Technical Stack & Implementation Considerations*. Hier nur messbare Anforderungen.

- **NFR-M1:** Die Code-Base läuft ohne Lint- und Format-Fehler unter `ruff` im Default-Konfigurationsmodus. CI-Hook wünschenswert, nicht MVP-blockend.
- **NFR-M2:** Alle Business-Logik-Module (P&L, R-Multiple, Expectancy, Trigger-Spec-Parser, Facetten-Aggregation) haben Unit-Tests. "Alle" bezieht sich auf die **10 kritischsten Pfade** aus dem Web-App-Stack-Abschnitt.
- **NFR-M3:** Das Health-Widget (FR50) zeigt Broker-Verbindungsstatus, MCP-Status, letzte Job-Ausführungen innerhalb von **≤ 5 Sekunden** Refresh-Latenz.
- **NFR-M4:** Logs sind strukturiert (JSON) und im Project-Root unter einem definierten Pfad erreichbar. Log-Rotation durch Python-Logging-Handler mit einer Obergrenze von **100 MB pro Log-Datei, 5 Rotationen**.
- **NFR-M5:** Die Migrations-History (FR51) ist im Repo committet und vollständig rekonstruierbar ab `001_initial_schema.sql`. Keine "squash"-Operationen im MVP.
- **NFR-M6:** ctrader läuft als **Single-Process** (FastAPI + APScheduler im selben Prozess). Keine Multi-Process-Koordination, kein externer Worker-Queue im MVP.
