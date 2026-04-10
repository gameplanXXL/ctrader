---
title: "Product Brief: ctrader"
status: "draft"
created: "2026-04-10"
updated: "2026-04-10"
owner: "Christian (Chef)"
inputs:
  - "User interview (2026-04-10)"
  - "/home/cneise/Project/ctrader/ — prior .NET attempt (CTraderAI.sln)"
  - "/home/cneise/Project/ctrader2/ — prior Python attempt"
  - "/home/cneise/Project/fundamental/ — MCP server for fundamental analysis (hard dependency)"
  - "/home/cneise/Project/fundamental/_bmad-output/daytrading/trends/trend-radar-2026-03-29.md"
  - "Web research: IB API landscape, LLM trading agents, existing trade journals, 2026 regulatory context"
---

# Product Brief: ctrader

## Executive Summary

**ctrader** ist eine persönliche Trading-Plattform mit zwei Herzen: einem **vereinigten Trade-Journal** für manuelles Aktien- und Options-Trading bei Interactive Brokers, und einer **AI-Agent-Farm** für vollautomatisches Crypto- und CFD-Trading über cTrader — beides in derselben UI, mit demselben Qualitätsmaßstab: *Für jeden einzelnen Trade muss klar sein, warum er stattgefunden hat und was er gebracht hat.*

Der zentrale Anspruch: **Trigger-Provenance auf Schema-Ebene.** Jeder Trade — ob von Hand gesetzt oder vom Bot ausgeführt — wird bis auf das ursprüngliche Signal, die Indikator-Snapshot, die News oder die LLM-Begründung zurückverfolgt. Kein anderes Tool am Markt macht das: TradeZella, TraderSync, Tradervue und Edgewonk reduzieren "Trigger" auf manuelle Tags und Screenshots. ctrader macht es zur ersten Klasse.

Warum jetzt: Der Trend-Radar des bestehenden `fundamental`-Projekts hält fest, dass rein diskretionäres Daytrading 2026 ein strukturelles Nachteil ist — AI-Algorithmen machen 89% des globalen Handelsvolumens aus, algorithmische Trader schlagen diskretionäre konsistent. Gleichzeitig existiert keine Retail-Plattform, die Broker-Execution, Fundamentalanalyse und human-gated LLM-Strategien in einem Tool vereint. ctrader ist die persönliche Antwort darauf.

## Das Problem

Nach zwei abgebrochenen Versuchen (`ctrader` in .NET, `ctrader2` in Python) ist die Ausgangslage eindeutig: Kein verfügbares Tool liefert das, was für diszipliniertes, lernbasiertes Daytrading in 2026 gebraucht wird.

- **Trade-Journals** (TradeZella, TraderSync, Tradervue) sind reine Post-Mortem-Tools. Sie zeigen P&L, aber die Frage *"Warum habe ich diesen Trade gemacht?"* wird über freitextuelle Notizen beantwortet, die nach drei Wochen niemand mehr pflegt. Die Erkenntnis verpufft.
- **Execution-Frameworks** (NautilusTrader, ib_async, VectorBT) liefern Order-Routing und Backtesting, aber keine Begründungen und keinen Review-Layer. Sie gehen davon aus, dass der Trader die Strategie selbst geschrieben hat.
- **LLM-Trading-Projekte** (TradingAgents, FinMem) generieren Strategien, aber ohne harte Approval-Gates — entweder volles Autopilot oder akademisches Spielzeug.
- **Die persönliche Realität:** Die eigenen Vorprojekte sind an Scope-Explosion gescheitert (`ctrader` hatte 83 Functional Requirements über 8 Epics). Fundamentalanalyse wurde parallel in `fundamental` neu aufgebaut, ohne je mit der Execution-Seite zusammenzukommen. Daytrading blieb Theorie.

Der Preis dieses Status quo: Jeder Trade ist ein potenzieller Lerngewinn, der verloren geht, weil der Kontext fehlt. Man wiederholt Fehler, weil das System sie nicht sichtbar macht. Und man verpasst die algorithmische Assistenz, die 2026 zur Grundausstattung geworden ist.

## Die Lösung

ctrader ist eine Single-User-Python-Plattform mit **vier Kernbausteinen**:

1. **Unified Trade Journal** — die primäre UI. Jeder Trade ist eine Zeile mit P&L, **Expectancy**, **R-Multiple**, und einem aufklappbaren "Warum"-Block: welche Strategie / welches Signal / welche Fundamental-Einschätzung / welche News den Trade getriggert haben. Trigger-Provenance wird technisch über IBs `orderRef`-Feld (~40 Zeichen pro Order) und eine lokale `permId`-verknüpfte Trigger-Tabelle realisiert — ein Pattern, das sonst niemand verwendet.

2. **Interactive Brokers Sync (read-only)** für manuell gehandelte Aktien und Optionen. Live-Executions kommen über `ib_async` (moderner Fork von `ib_insync`), historische Reconciliation über Flex Queries (XML). Trades erscheinen ohne manuellen Eingriff im Journal.

3. **cTrader Bot-Execution** für Crypto und CFDs. In der MVP-Phase **ein Agent** auf einem **Demo-Account** mit vollständigem Approval-Workflow: Agent schlägt Strategie vor → Chef reviewt (inkl. expliziter Risikobudget-Freigabe) → Agent führt aus. Die cTrader-Integration aus dem Vorprojekt `ctrader2` (OpenApiPy, Protobuf, OAuth) kann partiell wiederverwendet werden.

4. **Fundamental-/News-Brain über MCP** (**harte Dependency** auf `/home/cneise/Project/fundamental`). ctrader baut *keine* eigene Fundamental- oder Trend-Engine. Stattdessen konsumiert es das bestehende MCP-Interface: SFA für Aktien (Viktor, Rita), CFA für Crypto (Satoshi, Cassandra), News-Tool, Trigger-Evaluatoren, Watchlist, Gordon's Daytrading-Trend-Radar. Die Trading-Agents rufen diese Workflows als Strategie-Input auf.

**Strategy Review Loop:** Jede Strategie wird nach N Trades automatisch gegen Expectancy und R-Multiple gemessen. Chef und Agent sehen in einer Seite-an-Seite-Ansicht, was funktioniert und was nicht — und generieren gemeinsam die nächste Strategie-Iteration.

## Was ctrader anders macht

- **Trigger-Provenance als Schema, nicht als Notizfeld.** `orderRef` + `permId` + lokale Signal-Tabelle liefern einen harten Join zwischen Execution und Begründung. Nachträgliche Rekonstruktion entfällt.
- **Human-in-the-Loop *vor* der Execution, nicht danach.** Beide Vorprojekte haben Live-Trading einmalig freigegeben und dann auto-executiert. ctrader invertiert das: jede neue Strategie braucht eine explizite Freigabe mit Risikobudget.
- **Fundamentalanalyse ist kein Modul, sondern eine Dependency.** Durch die MCP-Integration mit `fundamental` entfallen mehrere Wochen Entwicklungsarbeit und zwei ganze Risk-Bereiche (Datenqualität, LLM-Prompt-Engineering für Fundamentals).
- **Zwei Broker, eine UX.** Aktien/Optionen bei IB (manuell), Crypto/CFDs bei cTrader (Bot). Das Journal macht den Unterschied unsichtbar: ein Trade ist ein Trade.
- **Expectancy statt Win-Rate als Leitmetrik.** Win-Rate allein ist irreführend — ein 75%-Trader mit kleinen Gewinnern verliert gegen einen 45%-Trader mit großen Gewinnern. ctrader macht beide Zahlen sichtbar und priorisiert Expectancy in der Review-UI.

## Wer das Produkt nutzt

**Christian ("Chef") — Single User.** Kein kommerzielles Produkt, keine Multi-User-Fantasien, keine SaaS-Metriken. Die Plattform wird ausschließlich für den eigenen Handel gebaut und muss nur eine Person glücklich machen. Das ist bewusst: Es entfernt Onboarding-Friction, Mandantenfähigkeit, Billing, Support — und schafft den Raum, den Fokus auf die *drei Dinge* zu legen, die zählen: *Execution, Verständnis, Verbesserung*.

Erwartungshaltung: Intermediate Python-Skills, BMad-vertraut, bereit für 2 Monate konzentrierte Arbeit am MVP.

## Erfolgskriterien

**Produkt-Erfolg (nach MVP + 1–3 Monaten Nutzung):**

- **Das Journal ersetzt jede andere Trade-Aufzeichnung.** Alle IB- und cTrader-Trades laufen automatisch ein, die "Warum"-Spalte ist für >90% der Trades gefüllt, der Chef öffnet ctrader täglich und andere Tools nicht.
- **Strategie-Review ist trivial.** Für jede Strategie sieht Chef auf einen Blick: Anzahl Trades, Expectancy, R-Multiple, Win-Rate, größter Drawdown, Verbesserungsvorschlag des Agents. Der Weg von "diese Strategie läuft schlecht" zu "hier ist Version 2" ist eine UI-Interaktion, kein Copy-Paste-Analyse-Loop.
- **Scope-Disziplin hält.** Der MVP hat 5 Komponenten (siehe Scope), nicht 20. Der Feature-Creep, der `ctrader` und `ctrader2` zu Fall gebracht hat, wird durch explizite Phase-2-Ablage vermieden.

**Trading-Erfolg (vom Chef definierte Ziele, als Tracking-Targets im Journal hinterlegt):**

- Win-Rate 70% *und* 5% Monatsgewinn sind die Ambition. Realitätshinweis: Die Kombination ist mathematisch anspruchsvoll (hohe Winrate impliziert typischerweise niedrige R-Multiple). Das Journal muss ehrlich zeigen, wo die tatsächliche Performance zu diesen Zielen steht — und als erster Meilenstein gilt: *Expectancy > 0 über 50 Trades*.
- Der Bot lernt messbar dazu: Strategien aus Monat 2 schlagen Strategien aus Monat 1 in Expectancy.

## Scope (MVP — 2 Monate)

**In Scope:**

1. **IB Read-Only Sync** — `ib_async` für Live-Executions, Flex Query für historische Reconciliation, Mapping Aktien + Optionen, keine Order-Placement-Fähigkeit zu IB.
2. **cTrader Bot-Execution (Demo-Account, 1 Agent)** — OpenApiPy-basierte Integration (partielle Wiederverwendung aus `ctrader2`), 1 Trading-Agent mit eigenem Approval-Gate, Crypto + ggf. CFDs.
3. **Unified Trade Journal** — DuckDB-Speicher, Web-UI (Stack-Entscheidung in Architektur-Phase: Kandidaten sind FastAPI+HTMX, Dash, oder Next.js — "gescheites Frontend" ist nicht verhandelbar), Trade-Tabelle mit P&L / Expectancy / R-Multiple / Trigger-Provenance-Drilldown.
4. **`fundamental` MCP-Integration** — ctrader als MCP-Client. Konsumiert SFA-, CFA-, News-, Trigger- und Trend-Workflows. Kein eigener Fundamental-/News-Code.
5. **Strategy Review UI** — Pro Strategie: Metriken-Dashboard, Trade-Liste, Agent-generierter Verbesserungsvorschlag, Versionierung von Strategie-Varianten.

**Explizit Out of Scope für MVP (Phase 2 oder später):**

- Skalierung auf 10 Bot-Agents × 20k € (Architektur muss dies aber bereits vorsehen).
- cTrader Live-Modus (Demo only im MVP).
- Eigene Backtest-Engine (bewusste Entscheidung: AI-getriebenes Trading verändert sich zu schnell, historische Backtests sind nur punktuell aussagekräftig).
- Eigene News-/Trend-Engine (wird von `fundamental` bereitgestellt).
- Multi-User, Mandantenfähigkeit, Auth-System (jenseits lokaler Login-Sicherung).
- Mobile Apps, Real-Time-Benachrichtigungen via Push, Social-Sharing.
- Eigene Indikator-Bibliothek (falls gebraucht: direkt aus `ta-lib` oder `pandas-ta`).

## Vision (Phase 2 und darüber hinaus)

Wenn der MVP trägt, wird ctrader zur **persönlichen Trading-Werkstatt**, in der Chef und seine Agent-Farm gemeinsam lernen:

- **10 Agents × 20k € auf Live-cTrader**, jeder mit eigenem Mandat (z.B. Momentum-Agent, Mean-Reversion-Agent, News-Driven-Agent, Fundamental-Long-Agent). Jeder Agent hat seine eigene Strategie-Historie und sein eigenes Approval-Konto.
- **Cross-Agent-Learning**: Der Review-Loop vergleicht Agents untereinander, schlägt Portfolio-Rebalancing vor, identifiziert Strategie-Cluster, die obsolet werden.
- **Erweiterte Trigger-Quellen**: On-Chain-Signale für Crypto, Options-Flow-Daten für Aktien, Sentiment-Feeds.
- **Strategie-Marktplatz mit `fundamental`**: Viktor und Satoshi aus `fundamental` werden zu vollständigen Strategie-Autoren, nicht nur Input-Lieferanten — sie publizieren fertige Strategien, die ctrader nach Approval einsetzt.

Nach 12 Monaten soll ctrader die Antwort auf eine einzige Frage verkörpern: *"Was ist 2026 möglich, wenn ein disziplinierter Einzelner seinem eigenen AI-Team vertraut — und jede Entscheidung nachvollziehen kann?"*
