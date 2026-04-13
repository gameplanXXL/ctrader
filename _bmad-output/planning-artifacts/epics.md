---
stepsCompleted: ["step-01", "step-02", "step-03"]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# ctrader - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for ctrader, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Chef kann historische IB-Aktien-Trades ueber IB Flex Query in das Journal importieren.

FR2: Chef kann historische IB-Single-Leg-Options-Trades ueber IB Flex Query in das Journal importieren. Multi-Leg-Spreads sind explizit Phase 2.

FR3: Das System synchronisiert Live-IB-Executions automatisch, ohne manuellen Anstoss.

FR4: Das System erkennt Duplikate bei wiederholtem Sync und verhindert Doppel-Eintraege auf Basis einer eindeutigen Broker-ID.

FR5: Das System reconciliert Live-Sync und Flex-Nightly und behandelt Flex-Query als Source-of-Truth bei Abweichungen.

FR6: Das System fuehrt genehmigte Bot-Proposals idempotent auf dem cTrader-Demo-Account aus (kein Doppel-Order bei Retry nach Netzausfall).

FR7: Das System trackt den Execution-Status jedes Bot-Trades (submitted / filled / partial / rejected / cancelled).

FR8: Chef kann alle Trades (IB + cTrader) in einer einheitlichen, chronologisch sortierbaren Liste sehen.

FR9: Chef kann einen einzelnen Trade in einer Drilldown-Ansicht oeffnen, die P&L, Zeitstempel, Broker, Strategie, Trigger-Provenance, und den damaligen Fundamental-Kontext anzeigt.

FR10: Chef kann das Journal ueber Facetten filtern. Pflicht-Facetten im MVP: Asset-Class, Broker, Strategie, Trigger-Quelle, Horizon, Gefolgt-vs-Ueberstimmt-Flag, Confidence-Band, Regime-Tag zur Trade-Zeit.

FR11: Chef sieht auf der Journal-Startseite alle untagged manuellen Trades mit einem prominenten Zaehler.

FR12: Chef sieht fuer jeden Trade P&L (inklusive Gebuehren und Funding-Rates bei CFDs), Expectancy-at-Entry, und R-Multiple (oder NULL bei fehlendem Stop-Loss, nie "0").

FR13: Chef kann fuer jede Facetten-Kombination eine Aggregation abrufen (Anzahl Trades, Expectancy, Winrate, R-Multiple-Verteilung).

FR13a: Chef sieht fuer jeden Trade MAE (Maximum Adverse Excursion) und MFE (Maximum Favorable Excursion) — jeweils in Preis-Einheiten und in Position-Dollar-Einheiten. Basis sind Intraday-Candle-Daten fuer den Trade-Zeitraum.

FR13b: Chef sieht einen P&L-Kalender-View (Monatsraster, jede Zelle ein Handelstag, Farbe nach Tages-P&L); ein Klick auf eine Zelle oeffnet die Liste aller Trades dieses Tages.

FR13c: Chef kann fuer jeden Trade einen interaktiven OHLC-Chart mit Entry/Exit-Markern und Indikatoren im Trade-Drilldown sehen (lightweight-charts, TradingView Open-Source).

FR14: Das System laedt die Taxonomie (Trigger-Typen, Exit-Gruende, Regime-Tags, Strategie-Kategorien, Horizon-Optionen) aus taxonomy.yaml.

FR15: Chef kann einen manuell ausgefuehrten Trade post-hoc mit Strategie, Trigger-Typ, Horizon, Exit-Grund und Freitext-Notizen taggen.

FR16: Das System speichert fuer jeden Trade eine strukturierte trigger_spec (JSONB) konform zum fundamental/trigger-evaluator-Schema.

FR17: Das System befuellt die trigger_spec bei Bot-Trades automatisch aus dem genehmigten Proposal; bei manuellen Trades entsteht sie ueber die Post-hoc-Tagging-UI.

FR18: Chef kann die trigger_spec eines Trades in einer lesbaren, nicht-technischen Darstellung sehen (kein Raw-JSON in der User-Facing UI).

FR18a: Die Taxonomie umfasst eine separate mistakes-Facette (z.B. fomo, no-stop, revenge, overrode-own-rules, oversized, ignored-risk-gate), die orthogonal zu Trigger-Quelle und Strategie pro Trade getaggt werden kann.

FR18b: Chef kann einen Top-N-Mistakes-Report abrufen, der Mistakes ueber ein waehlbares Zeitfenster nach Haeufigkeit und nach aggregierten $-Kosten sortiert anzeigt.

FR19: Das System ruft via MCP die Fundamental-Einschaetzung von Viktor (Aktien, SFA) und Satoshi (Crypto, CFA) fuer ein gegebenes Asset ab.

FR20: Chef sieht im Trade-Drilldown die damalige Fundamental-Einschaetzung zum Zeitpunkt des Trades und die aktuelle Einschaetzung side-by-side.

FR21: Chef sieht im Proposal-Drilldown die aktuelle Fundamental-Einschaetzung neben dem Agent-Vorschlag.

FR22: Das System cached Fundamental-Ergebnisse mit einer Staleness-Anzeige im UI ("Stand: vor X Minuten") und einer TTL pro Asset-Class.

FR23: Das System zeigt MCP-Outages im UI als klaren Zustand, ohne das Journal oder andere Views zu blockieren.

FR24: Das System fuehrt taeglich einen MCP-Contract-Test gegen den in Woche 0 eingefrorenen Snapshot aus und meldet Abweichungen ohne Trade-Flow-Blockade.

FR25: Chef sieht alle offenen Bot-Proposals in einem Approval-Dashboard mit Agent-Name, Strategie, Asset, Horizon, vorgeschlagener Position und Risk-Gate-Status.

FR26: Chef sieht im Proposal-Drilldown alle entscheidungsrelevanten Informationen in einem Viewport: Agent-Vorschlag, Fundamental-Einschaetzung, Risk-Gate-Ergebnis, Regime-Kontext.

FR27: Das System fuehrt bei jedem Proposal automatisch ein Risk-Gate via Rita (Aktien) bzw. Cassandra (Crypto) mit einem dreistufigen Ergebnis aus: GREEN, YELLOW, RED.

FR28: Das System blockiert den Approval-Button technisch, wenn das Risk-Gate RED liefert. Es gibt keinen Workaround zur Umgehung der RED-Blockade.

FR29: Chef kann bei YELLOW- oder GREEN-Status ein Proposal mit explizit gesetztem Risikobudget genehmigen (Pflichtfeld, Default aus Proposal).

FR30: Chef kann ein Proposal ablehnen oder zur Revision an den Agent zurueckschicken.

FR31: Chef kann die Fundamental-Einschaetzung bei YELLOW- oder GREEN-Status ueberstimmen; das System setzt overrode_fundamental=true im Audit-Log.

FR32: Das System speichert fuer jede Approval einen unveraenderlichen Audit-Log-Eintrag mit: Zeitstempel, genehmigtes Risikobudget, Risk-Gate-Snapshot, Override-Flags, Strategie-Version, Fundamental-Einschaetzung.

FR33: Chef kann Strategien ueber ein Strategy-Template definieren mit Pflichtfeldern: Name, Asset-Class, Horizon, Typical-Holding-Period, Trigger-Quelle(n), Risikobudget pro Trade.

FR34: Chef sieht eine Strategy-Liste mit Aggregations-Metriken pro Strategie (Anzahl Trades, Expectancy, R-Multiple-Verteilung, Drawdown, aktueller Status).

FR35: Chef kann die Strategy-Liste nach Horizon gruppieren und nach beliebiger Metrik sortieren.

FR36: Chef sieht in der Strategy-Detailansicht die Expectancy-Kurve ueber Zeit, die vollstaendige Trade-Liste der Strategie, und einen "Gefolgt-vs-Ueberstimmt"-Breakdown.

FR37: Chef kann Freitext-Notizen zu einer Strategie schreiben; das System speichert jede Notiz mit Zeitstempel als eigene Versionshistorie-Entry.

FR38: Chef kann eine Strategie zwischen den Status active, paused und retired wechseln.

FR39: Das System verhindert im Bot-Execution-Pfad, dass Strategien mit Status paused oder retired neue Proposals generieren.

FR40: Chef sieht Expectancy-Aggregationen pro Horizon ueber alle Strategien hinweg.

FR41: Das System erzeugt taeglich einen Regime-Snapshot mit Fear & Greed, VIX, und Per-Broker-P&L.

FR42: Das System pausiert bei Fear & Greed < 20 automatisch alle Strategien mit Horizon in {intraday, swing<5d} (horizon-bewusster Kill-Switch).

FR43: Das System pausiert Strategien mit laengerem Horizon (swing>=5d, position) NICHT automatisch bei Fear & Greed-Drops.

FR44: Chef kann einen aktiven Kill-Switch manuell fuer einzelne Strategien ueberschreiben; Override wird als Audit-Log-Eintrag dokumentiert.

FR45: Chef sieht den aktuellen Regime-Stand (F&G, VIX, pausierte Strategien durch Kill-Switch) auf einer Regime-Seite.

FR46: Das System holt woechentlich (Montag morgen) den aktuellen Gordon-Trend-Radar via MCP und speichert ihn als Snapshot.

FR47: Das System berechnet einen Diff zwischen dem aktuellen und dem Vorwochen-Snapshot und zeigt HOT-Picks farblich kategorisiert (neu / weggefallen / unveraendert).

FR48: Chef kann aus einem Gordon-HOT-Pick direkt einen Strategie-Kandidaten erstellen; das System fuellt Symbol, Horizon und Trigger-Quelle vorab aus.

FR49: Das System fuehrt Scheduled Jobs (IB Flex Nightly, Regime-Snapshot, Gordon-Weekly, MCP-Contract-Test, DB-Backup) zu definierten Zeiten aus und loggt jede Ausfuehrung mit Status.

FR50: Chef sieht einen Health-Widget mit Broker-Verbindungsstatus, MCP-Status, Zeitstempel der letzten erfolgreichen Job-Ausfuehrungen, und dem aktuellen Contract-Test-Ergebnis.

FR51: Das System fuehrt alle PostgreSQL-Schema-Aenderungen ausschliesslich ueber versionierte, idempotente Migrations-Skripte aus mit Tracking in einer schema_migrations-Meta-Tabelle.

FR52: Das System erstellt taegliche PostgreSQL-Backups; die Recovery-Prozedur ist im Project-Knowledge dokumentiert.

FR53: Chef kann aus dem Journal oder der Watchlist heraus eine Quick-Order fuer eine IB-Aktie aufgeben: Symbol, Side, Quantity, Limit-Preis, Trailing-Stop-Amount.

FR54: Das System zeigt vor Absendung eine Bestaetigungs-Zusammenfassung mit allen Order-Parametern. Die Bestaetigung erfordert einen expliziten Klick.

FR55: Das System sendet die Order als Bracket Order via ib_async: Parent-Order (Limit) + Child-Order (Trailing Stop-Loss). Atomare Submission mit orderRef fuer Idempotenz.

FR56: Das System trackt den Order-Status fuer IB-Quick-Orders (submitted / filled / partial / rejected / cancelled) und aktualisiert den zugehoerigen Journal-Eintrag.

FR57: Bei Order-Platzierung ueber Quick-Order wird der Trade automatisch mit Strategie, Trigger-Quelle und Horizon getaggt (auto-tagged statt untagged).

FR58: Das System unterscheidet im UI klar zwischen transienten Fehlern (Retry) und terminalen Fehlern (Aktion erforderlich). Bei transienten Fehlern automatischer Retry (max 3x, Backoff); bei terminalen Fehlern klare Fehlermeldung.

### NonFunctional Requirements

NFR-P1: Performance — Journal-Startseite laedt vollstaendig innerhalb von <= 1.5 Sekunden bei <= 2000 Trades.

NFR-P2: Performance — Trade-Drilldown laedt innerhalb <= 3s (Cache-Miss) oder <= 500ms (Cache-Hit) inklusive Fundamental-Einschaetzung.

NFR-P3: Performance — Facet-Filter-Update aktualisiert Ergebnisliste innerhalb <= 500ms bei <= 2000 Trades.

NFR-P4: Performance — Aggregation fuer Facetten-Kombinationen berechnet innerhalb <= 800ms bei <= 2000 Trades.

NFR-P5: Performance — Approval-Dashboard und Proposal-Drilldown laden innerhalb <= 2s inklusive aller MCP-Calls bei Cache-Miss.

NFR-P6: Usability — Trade-Drilldown erreichbar in <= 3 Klicks von Journal-Startseite; Facet-Query mit 3 Facetten in <= 4 Klicks.

NFR-S1: Security — API-Credentials ausschliesslich in .env-Dateien oder System-Umgebungsvariablen mit .gitignore-Enforcement.

NFR-S2: Security — FastAPI bindet ausschliesslich an 127.0.0.1; kein Binding an 0.0.0.0 im MVP.

NFR-S3: Security — Approval-Audit-Log ist technisch append-only; Update/Delete-Operationen verhindert via DB-Constraint.

NFR-S4: Security — Kein Telemetry oder externes Error-Tracking im MVP; alle Logs bleiben lokal.

NFR-S5: Security — PostgreSQL-Dateien und Backup-Verzeichnis haben restriktive Filesystem-Permissions (0600/0700).

NFR-R1: Reliability — IB-Sync-Pipeline verhindert Duplikate deterministisch per Broker-Unique-ID (permId).

NFR-R2: Reliability — Live-IB-Sync ueberlebt TWS/Gateway-Reconnects mit Auto-Reconnect und State-Recovery ohne Trade-Verlust.

NFR-R3: Reliability — Genehmigte Bot-Orders sind idempotent; Retry nach Netzausfall kann keine Duplikat-Orders erzeugen.

NFR-R3a: Reliability — IB-Quick-Orders sind idempotent via orderRef (Client-Order-ID) als Idempotenz-Schluessel.

NFR-R3b: Usability — Quick-Order-Confirmation-UI zeigt alle entscheidungsrelevanten Daten ohne Scrollen in einem Viewport.

NFR-R4: Reliability — MCP-Contract-Test laeuft taeglich erfolgreich; UI-Warning-Banner erscheint innerhalb 24h nach Drift-Erkennung.

NFR-R5: Reliability — Taegliche PostgreSQL-Backups mit Alter <= 24h; Health-Widget zeigt letzten erfolgreichen Backup-Zeitstempel.

NFR-R6: Reliability — Graceful Degradation bei MCP-Outage: Journal, Strategy, Regime Views bleiben funktional; Approval-Flow blockiert explizit bei "Risk-Gate unreachable".

NFR-R7: Reliability — Schema-Aenderungen ausschliesslich ueber versionierte, idempotente Migrationen.

NFR-R8: Reliability — Audit-Log enthaelt vollstaendigen Snapshot fuer jede Approval; historische Entscheidungen reproduzierbar.

NFR-I1: Integration — Jeder MCP-Call hat expliziten Timeout <= 10s; UI zeigt Unavailability nach Timeout.

NFR-I2: Integration — MCP-Fundamental-Calls nutzen TTL-Cache: 15 Minuten fuer Crypto, 1 Stunde fuer Aktien; Staleness sichtbar im UI.

NFR-I3: Integration — Broker-API-Calls respektieren Rate-Limits mit Exponential Backoff (1s Start, 60s Max, max 5 Retries).

NFR-I4: Integration — Woechentlicher Gordon-Trend-Loop (Montag 06:00 UTC) mit 8/8 Wochen Erfolgsrate im MVP.

NFR-I5: Integration — MCP-Contract-Test-Ergebnis ist PASS oder enthaelt dokumentierte Drifts ueber alle 8 Wochen.

NFR-I6: Integration — Intraday-Candle-Daten (1m/5m) fuer MAE/MFE mit 24h Cache-TTL, <= 15s Timeout, Graceful Degradation.

NFR-M1: Maintainability — Codebase laeuft ohne Lint- und Format-Fehler unter ruff.

NFR-M2: Maintainability — Alle Business-Logic-Module haben Unit-Tests fuer 10 kritische Pfade.

NFR-M3: Maintainability — Health-Widget zeigt Broker-Status, MCP-Status, letzte Job-Ausfuehrungen innerhalb <= 5s Refresh-Latenz.

NFR-M4: Maintainability — Strukturierte JSON-Logs mit Rotation (max 100MB/File, 5 Rotationen).

NFR-M5: Maintainability — Migrations-History committed, vollstaendig rekonstruierbar ab 001_initial_schema.sql.

NFR-M6: Maintainability — ctrader laeuft als Single-Process (FastAPI + APScheduler); kein Multi-Process im MVP.

### Additional Requirements

- **Kein Starter-Template verfuegbar** — Greenfield-Scaffolding erforderlich (4 FastAPI+HTMX+Tailwind Starters evaluiert und verworfen). Betrifft Epic 1 Story 1.
- PostgreSQL via `asyncpg` mit Connection-Pool (min=2, max=10), initialisiert im FastAPI Lifespan. Kein ORM — raw SQL mit Pydantic-Validierung.
- Docker Compose mit 2 Services: `ctrader` (FastAPI + APScheduler, Multi-Stage Build) und `postgres`.
- Sequentielle Migration-Nummerierung (001_*.sql, 002_*.sql) mit `schema_migrations` Tracking-Tabelle. Idempotente Migrationen.
- JSONB `trigger_spec` als Cross-Cutting Concern: GIN-Index, `asyncpg` automatische JSONB-dict-Konvertierung, zentrale Schema-Definition + Renderer + Query-Builder.
- Append-Only Audit-Log via PostgreSQL `BEFORE UPDATE OR DELETE` Trigger (`RAISE EXCEPTION 'audit log is append-only'`). Dedizierte Migration.
- MCP HTTP/SSE Client-Wrapper (`app/clients/mcp.py`) mit einheitlichem Pattern: Timeout <= 10s, TTL-Cache mit Staleness-Tracking, Graceful Degradation.
- `ib_async` fuer Live-Sync + Flex Query fuer historische Reconciliation. Duplikat-Erkennung via `permId` Composite Key.
- `OpenApiPy` fuer cTrader (Protobuf/SSL, Rate-Limits, OAuth2). Eigene ID + Client-Order-ID fuer Idempotenz.
- Dual-Source-Reconciliation: Flex (IB) als Source-of-Truth, cTrader als Secondary Validation.
- In-Memory TTL-Cache (`cachetools.TTLCache`): 15min Crypto, 1h Aktien, 24h historische Candle-Daten. Cache clears on restart.
- OHLC-Candle-Cache in PostgreSQL-Tabelle `ohlc_candles` mit 24h TTL. Endpoint: `GET /trades/{id}/chart_data`.
- Intraday-Candle-Daten: IB Historical Data (`ib_async` `reqHistoricalData()`), Fallback: Binance/Kraken API, Fallback: `fundamental/price` MCP.
- APScheduler im FastAPI-Lifespan (Single-Process): IB Flex Nightly, Regime-Snapshot, Gordon-Weekly, MCP-Contract-Test, DB-Backup.
- `structlog` fuer strukturierte JSON-Logs (File + stdout). Levels: DEBUG/INFO/WARNING/ERROR. Rotation: 100MB/File, 5 Rotationen.
- REST-API: snake_case Routes und Query-Parameter. Fragment-Endpoints mit `_fragment` Suffix oder dedizierte Pfade.
- HTMX Response: HTML-Fragmente mit `data-kebab-case` Attributen. Zwei Endpoint-Typen pro View: Full-Page-Render + Fragment-Update.
- Daten-Serialisierung: ISO 8601 Timestamps, snake_case JSONB-Keys, max 2 Dezimalen fuer Currency.
- Python Naming: Modules `snake_case.py`, Klassen `PascalCase`, Funktionen `snake_case`, Konstanten `UPPER_SNAKE_CASE`.
- Template-Naming: `snake_case.html`, Fragment-Templates mit `_` Prefix.
- DB-Naming: Tables `snake_case`, Columns `snake_case`, PK `id`, Indexes `idx_{table}_{columns}`, Enums via `CREATE TYPE`, Timestamps `_at` Suffix + `TIMESTAMPTZ`.
- Error-Handling: Transient (Backoff 1s-60s, max 5 Retries) vs Terminal (UI-Banner + Log). Keine Silent Failures.
- Week-0 Deliverables: `uv init` + Dependencies + Docker Compose + PostgreSQL, `asyncpg` Pool + Migrations Runner + `001_initial_schema.sql`, MCP HTTP/SSE Handshake + Contract-Snapshot Freeze, FastAPI Skeleton mit MCP-Call Page.
- Offene Entscheidungen: MCP HTTP/SSE Transport Verifikation, PostgreSQL Schema DDL Details, HTMX Helper Libraries (`fasthx` vs `fastapi-htmx`).
- Architektur hat Vorrang ueber PRD/Brief bei Konflikten (insbesondere PostgreSQL statt DuckDB).

### UX Design Requirements

UX-DR1: Dark Cockpit Farbsystem mit CSS-Custom-Properties: Background-Layer (--bg-void, --bg-chrome, --bg-surface, --bg-elevated), Text-Farben (--text-primary, --text-secondary, --text-muted), P&L-Farben (gruen #3fb950, rot #f85149), Status-Farben (green/yellow/red), Akzent-Blau (#58a6ff).

UX-DR2: CSS-Custom-Properties fuer Typographie-Skala: 6 Groessen (11px-28px), Line-Height-Mappings (1.27-1.57), Letter-Spacing-Regeln.

UX-DR3: Spacing-Skala basierend auf 4px-Grid: Tokens 4/8/12/16/24/32/48px (explizit ohne 5/7/9/10/11).

UX-DR4: Zwei-Font-System: Inter (Sans-Serif) fuer Labels/Navigation/Prosa, JetBrains Mono (Monospace) fuer alle numerischen Werte.

UX-DR5: WCAG AA Minimum-Kontrastraten (die meisten AAA): Primary auf Void 16.4:1, Primary auf Surface 13.1:1, Accent-Links 7.1:1.

UX-DR6: Hover-State (background heller), Focus-State (2px Accent-Outline), Active-State (background dunkler), Disabled-State (0.4 Opacity), Selected-State (accent-tinted 15%).

UX-DR7: Custom Design System mit Tailwind CSS + Jinja2 Macros statt externer Component-Libraries, 13 Component-Macros in `app/templates/components/`.

UX-DR8: CSS-Dateistruktur: `design-tokens.css` (Custom Properties) + `main.css` (Tailwind @layer), kompiliert via Tailwind CLI mit Hot-Reload.

UX-DR9: 13 Jinja2 Component-Macros: stat_card, trade_row, facet_chip, facet_bar, sparkline, status_badge, staleness_banner, trigger_spec_readable, calendar_cell, proposal_viewport, command_palette_item, toast, query_prose (Tier-basierter Rollout Wochen 0-6).

UX-DR10: `stat_card(label, value, trend, variant)` — Metriken-Karte fuer Dashboards mit Default, Loading (Opacity-Flash) und Gain/Loss Varianten.

UX-DR11: `trade_row(trade)` — Tabellen-Zeile mit Default, Hover, Selected, Expanded, Untagged States. HTMX Click-to-Expand mit `hx-push-url`.

UX-DR12: `facet_chip(label, active, count)` — Filter-Button mit Inactive, Active (--accent), Hover, Disabled States. HTMX-Facet-Toggling mit `aria-pressed`.

UX-DR13: `facet_bar(facets)` — Horizontaler Facet-Strip mit Reset-Link (nur bei >= 1 aktiven Filter), Toolbar-Role, Arrow-Key Navigation.

UX-DR14: `stat_card` Hero-Metriken (Expectancy, Winrate, Drawdown, Trade Count) mit Sparklines, Monospace 28px/36px.

UX-DR15: `sparkline(data, width, height)` — SVG Mini-Chart mit Default und Empty (dashed placeholder) States. Server-side generiert, `role="img"` + `aria-label`.

UX-DR16: `status_badge(status, label)` — Vier States: Green, Yellow, Red, Unknown. Mit `aria-label` fuer Accessibility.

UX-DR17: `toast(message, variant)` — Feedback-Component: fade-in 200ms, 3s sichtbar, fade-out 200ms. Drei Varianten (success/error/info). Via `HX-Trigger: showToast` + Alpine.js.

UX-DR18: `trigger_spec_readable(spec)` — JSONB zu natuerlichsprachigen Saetzen (20-30 Template-Patterns). Default, Partial ("Unbekannt"), Empty ("Nicht getaggt").

UX-DR19: `calendar_cell(date, pnl, tags)` — P&L-Kalender-Zelle: Gain-Tint, Loss-Tint, Neutral, No-Trading (grau), Today (Accent-Border). HTMX-Click fuer Datum-Filter.

UX-DR20: `staleness_banner(last_update, source)` — Dead-Man's-Switch: Hidden, Visible (gelb), Critical (rot >24h). Optional Polling via `hx-get` alle 60s. `role="alert"`.

UX-DR21: `query_prose(facets)` — Lesbare Query-Beschreibung aus aktiven Facetten. Default, Empty ("Alle Trades"), Complex (>4 Facetten abgekuerzt). `role="status"`.

UX-DR22: `proposal_viewport(proposal, fundamental, risk_gate)` — 3-Spalten-Layout (~440px): Agent Proposal | Fundamental | Risk Gate. States: Default, Fundamental-Unavailable, Risk-Gate-RED (Approve disabled), Approved, Rejected.

UX-DR23: `command_palette_item(label, shortcut, action)` — Command-Palette-Eintrag: Default, Focused (accent), Disabled. Alpine.js, `role="option"`, Keyboard-Navigation.

UX-DR24: Journal-Startseite Layout: Top-Bar → Facet-Bar → Hero-Aggregation (Prosa-Query + 4 Metriken mit Sparklines) → Trade-Table. Keine Sidebar, max 1440px.

UX-DR25: Trade-Drilldown als Inline-Expansion (nicht Modal) unterhalb der geklickten Zeile. `?expand={id}` URL-Parameter fuer Bookmarkability.

UX-DR26: Strategy-Review Layout: Zwei-Pane Split — links 320px Strategie-Liste, rechts flexibel (min 800px) Strategie-Detail.

UX-DR27: Approval-Dashboard: Proposal-Cards mit Inline-Expansion, `proposal_viewport` bei 1440px mit 3-Spalten-Layout. Single Viewport.

UX-DR28: Gordon-Trend-View: Hero-Block mit Weekly-Delta, F&G, VIX, Kill-Switch-Status. HOT-Picks als kompakte Liste. Kein Scrollen noetig.

UX-DR29: Desktop-only Responsive: Optimal >= 1440px, Acceptable 1200-1440px, Notfall 1024-1199px, Blocker <1024px mit Hinweismeldung. Kein Mobile.

UX-DR30: 4px-Grid fuer Padding, Margins, Component-Spacing. Tokens: 4/8/12/16/24/32/48px.

UX-DR31: Zero-Padding horizontale Content-Constraints. --bg-void fuellt Raum jenseits 1440px.

UX-DR32: Trigger-Search Journey ("Chef-Moment"): <= 5 Klicks von Startseite bis Antwort. Alternative: Ctrl+K → Preset. Unter 30 Sekunden.

UX-DR33: Bot-Approval Journey: <= 3 Klicks. Keyboard: Tab + A/R. Alle Daten in einem Viewport.

UX-DR34: Post-hoc-Tagging: Unter 60 Sekunden pro Trade, <= 6 Klicks. Naechster untagged Trade erscheint automatisch nach Submission.

UX-DR35: Weekly Strategy-Review: <= 8 Klicks fuer vollstaendige Review. Horizon-Grouping, Expectancy-Vergleich, Notiz, Status-Toggle.

UX-DR36: Monday-Morning Gordon-Trend: <= 3 Klicks. 2-Sekunden Initial-Scan.

UX-DR37: Facet-Filter als primaere Navigation (nicht Sidebar). One-Click Toggle, kein Apply-Button, HTMX <500ms, URL-State via hx-push-url.

UX-DR38: Multi-Select Facet: Shift+Click fuer mehrere Werte innerhalb einer Facette. Kombinierter Chip (z.B. "Crypto OR CFDs").

UX-DR39: Time-Range-Selector Dropdown: All Time, This Week, Last 30 Days, Custom Range. HTMX ohne Apply-Button.

UX-DR40: Inline-Expansion Pattern: Click → expand below (nicht Modal). Escape/Re-Click schliesst. `?expand={id}` URL. Nur eine Expansion offen.

UX-DR41: HTMX Fragment-Update: Jede Facet-Aenderung aktualisiert nur betroffenes Fragment via hx-get/hx-swap. URL via hx-push-url. Kein Full-Page-Reload.

UX-DR42: Live-Aggregation-Update: Opacity-Flash (1→0.5→1) bei Facet-Aenderung. Kein Layout-Jump, kein Skeleton-Loading.

UX-DR43: Keyboard-First Shortcuts: A (Approve), R (Reject), Enter (Submit/Open), Esc (Close), Ctrl+K (Command Palette), G J/G S/G A (Navigation), Pfeiltasten (Pagination).

UX-DR44: Keyboard-Shortcut-Badges neben Aktionen: [A] neben Approve, [Ctrl+K] in Top-Bar.

UX-DR45: Stateful URL Pattern: Alle View-States (Facetten, Date-Range, Pagination, Expansion) in URL encodiert. Bookmark-faehig, Browser-Back funktioniert.

UX-DR46: Pagination: ?page=N (30 Trades/Seite). "Back | Page 2 of 7 | Next" mit Pfeiltasten-Navigation.

UX-DR47: 8 Pflicht-Facetten: Asset-Class, Broker, Strategy, Trigger-Source, Horizon, Followed-vs-Override, Confidence-Band, Regime-Tag. Alle simultan kombinierbar.

UX-DR48: Agent-zentrische Facettierung: Trigger-Source (Viktor/Satoshi/Gordon), Followed-vs-Overridden, Risk-Gate-Status. Queries wie "alle Verluste wo ich Viktor ueberstimmt habe".

UX-DR49: Text-Suche nur in Command Palette (Ctrl+K) mit Fuzzy-Matching. Kein Freitext-Suchfeld im Journal.

UX-DR50: Command Palette: 600px zentriertes Overlay, Ctrl+K Trigger, Fuzzy-Match, Escape schliesst, Enter navigiert. Alpine.js.

UX-DR51: Success-Toast: Bottom-right, gruene Akzent-Leiste, 3s Auto-Dismiss.

UX-DR52: Error-Toast: Bottom-right, rote Akzent-Leiste, detaillierte Fehlermeldung, persistiert bis manuell geschlossen.

UX-DR53: Warning als Staleness-Banner unter Top-Bar: Gelbe Akzent-Leiste, informativ nicht blockierend, persistent bis Daten aktualisiert.

UX-DR54: Loading-Pattern: Opacity-Flash (200ms) fuer Inline-Updates. Spinner + Kontext-Text fuer Calls >1s. Kein Skeleton-Loading.

UX-DR55: Empty-State: Neutraler Text in --text-muted mit Handlungsvorschlag. Keine Illustrationen, keine Emojis.

UX-DR56: Risk-Gate Status-Display: GREEN (Text + Icon), RED (Approve disabled, cursor: not-allowed), YELLOW (Warning, Button klickbar).

UX-DR57: Graceful Degradation bei MCP-Outage: "N/A (14:23)" in betroffenen Spalten. Staleness-Banner. Queries auf unabhaengigen Faktoren weiterhin moeglich.

UX-DR58: Tagging-Form: 4 Felder (Strategy, Trigger, Horizon, Exit-Reason) + Mistake-Tags + Freitext. Auto-Focus, Tab-Navigation, Enter speichert. Kein Submit-Button.

UX-DR59: Inline-Validierung: Roter Rahmen + Text unter Feld, getriggert auf Blur. Sane Defaults fuer optionale Felder.

UX-DR60: Dropdown Fuzzy-Search Filtering fuer Felder mit vielen Werten (Strategies, Assets).

UX-DR61: Form-Labels: Uppercase, 11px, --text-muted, letter-spacing 0.05em, immer ueber Feld. Explizites `<label for>`. Keine Floating-Labels.

UX-DR62: Alle Forms <= 6 Felder. Keine komplexen Multi-Step Wizards.

UX-DR63: Approval: Mandatory Risikobudget-Feld (Default aus Proposal), optionaler Override-Checkbox. In einer Zeile unter Risk-Gate.

UX-DR64: Rejection: Optionales Begruendungs-Feld, automatisch im Audit-Log. Toast "Rejected", Proposal verschwindet sofort.

UX-DR65: Revision-Flow: Reject + Notiz zurueck an Agent. Status wird "revision".

UX-DR66: Approval-Buttons keyboard-accessible: A (Approve, primary filled), R (Reject, secondary outlined). Kein Modal-Confirmation.

UX-DR67: Alle entscheidungsrelevanten Infos in einem Viewport (1440px x ~850px) ohne Scroll: Agent Proposal | Fundamental | Risk-Gate | Regime | Buttons.

UX-DR68: Hero-Aggregation: Live-updated Metriken: Trade Count (Monospace 28px), Expectancy (R-Multiple), Winrate (%), Drawdown (R-Multiple). Sparklines darunter. Update <500ms.

UX-DR69: P&L-Zahlen farbig (gruen/rot). Neutrale Farbe fuer Expectancy/Winrate/R-Multiples.

UX-DR70: Zahlen-Formatierung: Prozente ohne Dezimalen (35%), R-Multiples mit einer Dezimale (+0.8R), NULL R-Multiples als "NULL", leere Felder als em-dash. Monospace rechtsbuendig.

UX-DR71: Timestamp-Display: Absolut in Tabellen ("14:23"), relativ+absolut in Details ("vor 2h (14:23)"). Journal-weiter "Stand: 14:23" Indikator.

UX-DR72: P&L-Kalender: Grid-View taeglicher P&Ls. Gains gruen, Losses rot, Today Accent-Border, No-Trading grau. Click oeffnet Tages-Trades.

UX-DR73: Trade-Details-Panel: Symbol, Side, Entry/Stop/Target, Size, R-Budget, Zeiten, Trigger-Spec, Fundamental, Risk-Gate, Exit-Reason, Mistakes, Notes.

UX-DR74: Trigger-Provenance Narrative: JSONB → lesbare Saetze via trigger_spec_readable. 20-30 Template-Patterns pro Trigger-Typ.

UX-DR75: Regime-Kontext-Display: F&G, VIX, Kill-Switch-Status, Major Events. Im Footer von Approval-Viewport und Strategy-Detail.

UX-DR76: Strategy-Status-Tags: Active (gruen), Paused (gelb), Retired (grau). Click-to-Toggle, Toast-Confirmation, kein Modal.

UX-DR77: Trade-Status-Indikatoren: Untagged (orange), Awaiting-Approval (gelb), Approved (neutral), Rejected (grau). In allen Trade-Listen.

UX-DR78: Persistenter Top-Bar: Logo (links), Navigation (Mitte: Journal, Strategies, Approvals, Trends, Regime, Settings), Health-Status (rechts: IB, cTrader, MCP, Timestamp). Aktive Route in --accent.

UX-DR79: Health-Status-Indikator: Verbindungs-Dots (IB, cTrader, MCP). Green/Yellow/Red mit Hover-Tooltip.

UX-DR80: Settings-Seite: Taxonomie-Editor, MCP-Konfiguration, Audit-Log-Ansicht, DB-Backup-Download, Theme (Phase 2). Vertikal scrollend, keine Tabs.

UX-DR81: Keine Breadcrumbs. Navigation via Browser-Back + Ctrl+K Command Palette.

UX-DR82: Keine Hamburger-Menus, Slide-Out-Drawers oder Tab-Bars. Top-Bar persistent und immer sichtbar.

UX-DR83: Alle interaktiven Elemente keyboard-accessible: Logischer Tab-Order, keine Keyboard-Traps. Enter/Space fuer Buttons, Pfeiltasten fuer Menus.

UX-DR84: Sichtbare Focus-States: 2px Outline in --accent fuer alle fokussierbaren Elemente. Nie unterdrueckt.

UX-DR85: Semantisches HTML: `<button>` fuer Aktionen, `<a>` fuer Navigation, `<table>` mit `<th>`, `<label>` fuer Inputs, `<form>` fuer Forms.

UX-DR86: Alt-Text fuer funktionale Bilder, `aria-hidden` fuer dekorative Icons, `aria-label`/`aria-describedby` fuer unlabeled Elements.

UX-DR87: WCAG AA Kontrastraten auf allen Text-Background-Kombinationen (die meisten AAA).

UX-DR88: Volle Keyboard-Navigation fuer alle primaeren Workflows: Approval (Tab+A/R), Tagging (Tab+Enter), Command Palette (Ctrl+K), Facets, Pagination.

UX-DR89: Keine Screen-Reader-spezifischen Optimierungen im MVP, aber semantisches HTML als Baseline.

UX-DR90: Calm Confidence Design: Dark Mode only, muted Accents, ruhige Typographie, keine aufmerksamkeitsfangenden Animationen.

UX-DR91: Fehler/Warnings informieren ohne zu alarmieren: MCP-Outages als Staleness-Banner, negative P&L in rot ohne zusaetzliche visuelle Bestrafung.

UX-DR92: Keine kuenstlichen Engagement-Patterns: Keine Streaks, kein "Great job!", keine Celebrations, keine Progression-Bars.

UX-DR93: Ehrliche Erfolgsanzeige bei echtem Trading-Milestone (Expectancy >0 bei 50 Bot-Trades). Klarer Marker ohne Confetti.

UX-DR94: Performance-Metrik-Ton als Evidence-Humility: Positive und negative Metriken gleichermassen. Kein Cherry-Picking.

UX-DR95: Farbe sparsam und semantisch: Gruen/Rot nur fuer P&L und Risk-Gate. Neutral-Graustufen fuer informationsdichte Displays.

UX-DR96: Trade-Table-Rows: Information-dense Layout mit 8-10 Spalten in 1440px ohne horizontalen Scroll. Monospace Numerik rechtsbuendig.

UX-DR97: Visueller Rhythmus: Konsistentes Spacing (4/8/12/16/24px), klare Section-Headers (16px Sans-Serif), hierarchische Type-Sizing.

UX-DR98: Table-Headers: Uppercase, 11px Monospace, 0.05em Letter-Spacing, --text-muted, border-bottom. Gruppierte Headers.

UX-DR99: Focus-Center in Approval-Viewport: "Decision Point" (Risk-Gate Button-Row) visuell dominant. Spalten gleichmaessig unterstuetzend.

UX-DR100: Progressive Disclosure: Trade-Drilldown zeigt Core-Fields immer, expandierbare Sections fuer Advanced Metrics (MFE/MAE, Regime, Full Trigger-Spec).

UX-DR101: HTMX <500ms fuer Facet-Changes, <1s fuer MCP-Calls (Spinner bei >1s), <200ms fuer Form-Submissions. Optimistic UI wo moeglich.

UX-DR102: Kein Lazy-Loading/Infinite-Scroll. Stateful Pagination mit 30 Trades/Seite. URL-bookmarkbar.

UX-DR103: Server-side Cache fuer Aggregationen (Trade-Count, Expectancy, Winrate pro Facet-Kombination). Invalidierung nur bei neuen Trades/Tags/Approvals.

UX-DR104: Volle Trade-Daten in Query-Response. Jinja2 Server-Side Rendering. Minimale JavaScript-Dependencies.

UX-DR105: Daten-Export fuer alle Primary Views: Journal → CSV, Strategy → CSV, Approvals → CSV, P&L-Calendar → CSV. Excel-Import-kompatibel.

UX-DR106: Bookmark/Save-Query via Star-Icon: Benannte Presets (z.B. "Satoshi Overrides Lost"). Toast-Confirmation. Presets in Command Palette.

UX-DR107: PostgreSQL-Backup (via pg_dump) als downloadbares Artefakt in Settings. Externe Analyse ohne Application-Lock-in. (Geaendert am 2026-04-13: Storage von DuckDB auf PostgreSQL umgestellt.)

UX-DR108: URL-basiertes Query-Sharing: Jede Journal-View mit aktiven Filtern produziert shareable URL.

UX-DR109: NICHT implementieren im MVP: Trade-Replay-Animation, Multi-Agent-Selection-UI (agent_id als read-only). (Geaendert am 2026-04-13: Screenshot-Upload wurde durch dynamische OHLC-Charts via lightweight-charts ersetzt — siehe FR13c und Story 4.5.)

UX-DR110: NICHT implementieren im MVP: Tiltmeter. Stattdessen einfacheres Mistake-Tag-System.

UX-DR111: NICHT implementieren im MVP: Mobile Responsiveness, Tablet Layouts, Touch Optimization, Light-Mode Theme.

UX-DR112: NICHT implementieren im MVP: Monte-Carlo-Simulation, Custom Indicator-Library, Trade-Replay.

### FR Coverage Map

FR1: Epic 2 — IB-Aktien-Trades importieren (Flex Query)
FR2: Epic 2 — IB-Options-Trades importieren (Flex Query, Single-Leg)
FR3: Epic 2 — Live-IB-Executions automatisch synchronisieren
FR4: Epic 2 — Duplikat-Erkennung bei Sync (permId)
FR5: Epic 2 — Reconciliation Live-Sync vs Flex-Nightly
FR6: Epic 8 — Bot-Proposals idempotent auf cTrader-Demo ausfuehren
FR7: Epic 8 — Execution-Status-Tracking (submitted/filled/partial/rejected/cancelled)
FR8: Epic 2 — Einheitliche, chronologisch sortierbare Trade-Liste
FR9: Epic 2 — Trade-Drilldown (P&L, Zeitstempel, Broker, Strategie, Trigger, Fundamental)
FR10: Epic 4 — Facetten-Filter (8 Pflicht-Facetten)
FR11: Epic 2 — Untagged-Trades-Zaehler auf Journal-Startseite
FR12: Epic 2 — P&L, Expectancy-at-Entry, R-Multiple pro Trade
FR13: Epic 4 — Aggregation pro Facetten-Kombination
FR13a: Epic 4 — MAE/MFE pro Trade (Intraday-Candle-Daten)
FR13b: Epic 4 — P&L-Kalender-View (Monatsraster)
FR13c: Epic 4 — Interaktiver OHLC-Chart mit Entry/Exit-Markern (lightweight-charts)
FR14: Epic 1 — Taxonomie aus taxonomy.yaml laden
FR15: Epic 3 — Post-hoc-Tagging (Strategie, Trigger, Horizon, Exit-Grund, Notizen)
FR16: Epic 3 — Strukturierte trigger_spec (JSONB) pro Trade
FR17: Epic 3 — Auto-Befuellung trigger_spec bei Bot-Trades, Tagging-UI bei manuellen
FR18: Epic 3 — Lesbare Darstellung der trigger_spec (kein Raw-JSON)
FR18a: Epic 3 — Mistakes-Facette (fomo, no-stop, revenge, etc.)
FR18b: Epic 3 — Top-N-Mistakes-Report nach Haeufigkeit und $-Kosten
FR19: Epic 5 — MCP-Abruf Fundamental-Einschaetzung (Viktor/Satoshi)
FR20: Epic 5 — Damalige + aktuelle Fundamental-Einschaetzung im Trade-Drilldown
FR21: Epic 7 — Aktuelle Fundamental-Einschaetzung im Proposal-Drilldown
FR22: Epic 5 — Fundamental-Cache mit Staleness-Anzeige und TTL
FR23: Epic 5 — MCP-Outage-Anzeige im UI (Graceful Degradation)
FR24: Epic 5 — Taeglicher MCP-Contract-Test gegen Woche-0-Snapshot
FR25: Epic 7 — Approval-Dashboard mit offenen Bot-Proposals
FR26: Epic 7 — Proposal-Drilldown (Single Viewport)
FR27: Epic 7 — Automatisches Risk-Gate (Rita/Cassandra, GREEN/YELLOW/RED)
FR28: Epic 7 — RED-Blockade des Approval-Buttons (kein Workaround)
FR29: Epic 7 — Approval mit Risikobudget (Pflichtfeld)
FR30: Epic 7 — Ablehnung oder Revision an Agent
FR31: Epic 7 — Fundamental-Override mit overrode_fundamental=true Flag
FR32: Epic 7 — Unveraenderlicher Audit-Log-Eintrag pro Approval
FR33: Epic 6 — Strategy-Template (Name, Asset-Class, Horizon, etc.)
FR34: Epic 6 — Strategy-Liste mit Aggregations-Metriken
FR35: Epic 6 — Strategy-Liste Horizon-Gruppierung und Sortierung
FR36: Epic 6 — Strategy-Detailansicht (Expectancy-Kurve, Trade-Liste, Gefolgt-vs-Ueberstimmt)
FR37: Epic 6 — Freitext-Notizen zu Strategie mit Versionshistorie
FR38: Epic 6 — Strategy-Status-Wechsel (active/paused/retired)
FR39: Epic 6 — Blockade neuer Proposals fuer paused/retired Strategien
FR40: Epic 6 — Expectancy-Aggregation pro Horizon ueber alle Strategien
FR41: Epic 9 — Taeglicher Regime-Snapshot (F&G, VIX, Per-Broker-P&L)
FR42: Epic 9 — Horizon-bewusster Kill-Switch bei F&G < 20
FR43: Epic 9 — Keine Auto-Pause fuer laengere Horizons
FR44: Epic 9 — Manueller Kill-Switch-Override mit Audit-Log
FR45: Epic 9 — Regime-Seite (F&G, VIX, pausierte Strategien)
FR46: Epic 10 — Woechentlicher Gordon-Trend-Radar via MCP
FR47: Epic 10 — Diff aktuell vs Vorwoche, HOT-Picks farblich kategorisiert
FR48: Epic 10 — Strategie-Kandidat aus Gordon-HOT-Pick erstellen
FR49: Epic 12 — Scheduled Jobs mit Logging (Flex Nightly, Regime, Gordon, Contract-Test, Backup)
FR50: Epic 12 — Health-Widget (Broker-Status, MCP-Status, Job-Zeitstempel, Contract-Test)
FR51: Epic 1 — Versionierte idempotente Migrations-Skripte mit schema_migrations
FR52: Epic 12 — Taegliche PostgreSQL-Backups mit Recovery-Dokumentation
FR53: Epic 11 — Quick-Order-Formular (Symbol, Side, Quantity, Limit, Trailing-Stop)
FR54: Epic 11 — Bestaetigungs-Zusammenfassung vor Order-Absendung
FR55: Epic 11 — Bracket-Order via ib_async (Limit + Trailing Stop-Loss, atomar)
FR56: Epic 11 — Order-Status-Tracking fuer Quick-Orders
FR57: Epic 11 — Auto-Tagging bei Quick-Order (Strategie, Trigger, Horizon)
FR58: Epic 11 — Transient vs Terminal Fehler-Unterscheidung mit Auto-Retry
FR59: Epic 4 Story 4.6 — Command Palette (Ctrl+K) mit Fuzzy-Search
FR60: Epic 4 Story 4.7 — CSV-Export der Journal-Ansicht
FR61: Epic 4 Story 4.7 — Query-Presets (Star-Icon) und Command-Palette-Aufruf
FR62: Epic 4 Story 4.1 — Bookmarkbare Filter-URLs via hx-push-url

## Epic List

### Epic 1: Projekt-Bootstrap & Design-System
Chef hat eine laufende Anwendung mit Datenbank, Migrations-Framework, Taxonomie, Design-System und navigierbarer Seitenstruktur.
**FRs:** FR14, FR51
**Hinweis:** Greenfield-Scaffolding (kein Starter-Template). Liefert: Docker Compose, asyncpg Pool, Migrations-Runner, 001_initial_schema.sql, MCP-Handshake, FastAPI-Skeleton, Design-Tokens, Top-Bar, leere Page-Shells.

### Epic 2: Trade-Journal & IB-Import
Chef kann seine IB-Aktien- und Options-Trades importieren und in einer einheitlichen, chronologisch sortierbaren Liste mit Drilldown durchblaettern.
**FRs:** FR1, FR2, FR3, FR4, FR5, FR8, FR9, FR11, FR12

### Epic 3: Trade-Tagging & Trigger-Provenance
Chef kann jeden manuellen Trade post-hoc taggen (Strategie, Trigger, Horizon, Exit-Grund, Mistakes) und die Trigger-Provenance als lesbaren Text statt Raw-JSON sehen.
**FRs:** FR15, FR16, FR17, FR18, FR18a, FR18b

### Epic 4: Journal-Intelligence — Facetten, Aggregation & Visualisierung
Chef kann gezielte Fragen an sein Journal stellen und bekommt Aggregationen, P&L-Kalender, MAE/MFE und interaktive OHLC-Charts.
**FRs:** FR10, FR13, FR13a, FR13b, FR13c

### Epic 5: Fundamental-Integration (MCP-Layer)
Chef sieht im Trade-Drilldown die damalige und aktuelle Fundamental-Einschaetzung von Viktor/Satoshi, mit Staleness-Anzeige und Graceful Degradation bei MCP-Outages.
**FRs:** FR19, FR20, FR22, FR23, FR24

### Epic 6: Strategy-Management
Chef kann Trading-Strategien definieren, ihre Performance empirisch verfolgen (Expectancy, R-Multiple, Drawdown), Notizen schreiben und den Status zwischen active/paused/retired wechseln.
**FRs:** FR33, FR34, FR35, FR36, FR37, FR38, FR39, FR40

### Epic 7: Approval-Pipeline & Risk-Gate
Chef kann Bot-Proposals im Approval-Dashboard sichten, alle entscheidungsrelevanten Infos in einem Viewport sehen (Agent + Fundamental + Risk-Gate + Regime), und sicher genehmigen/ablehnen mit unveraenderlichem Audit-Log.
**FRs:** FR21, FR25, FR26, FR27, FR28, FR29, FR30, FR31, FR32

### Epic 8: Bot-Execution (cTrader)
Genehmigte Bot-Proposals werden idempotent auf dem cTrader-Demo-Account ausgefuehrt, mit vollem Execution-Status-Tracking.
**FRs:** FR6, FR7

### Epic 9: Regime-Awareness & Kill-Switch
Das System erzeugt taegliche Regime-Snapshots und pausiert bei Crash-Regimen automatisch kurzfristige Strategien — mit manueller Override-Moeglichkeit und Audit-Trail.
**FRs:** FR41, FR42, FR43, FR44, FR45

### Epic 10: Gordon Trend-Radar
Chef bekommt jeden Montag den aktuellen Gordon-Trend-Radar mit Wochen-Diff und kann aus HOT-Picks direkt Strategie-Kandidaten erstellen.
**FRs:** FR46, FR47, FR48

### Epic 11: IB Quick-Order
Chef kann direkt aus ctrader Bracket-Orders (Limit + Trailing Stop-Loss) bei IB platzieren, mit Bestaetigungs-UI, Auto-Tagging und klarer Fehler-Unterscheidung (transient vs terminal).
**FRs:** FR53, FR54, FR55, FR56, FR57, FR58

### Epic 12: System-Health & Scheduled Operations
Chef sieht den Systemzustand auf einen Blick (Broker-Status, MCP-Status, Job-Zeitstempel, Contract-Test, Backup-Status) und weiss, dass taegliche Backups und alle Scheduled Jobs zuverlaessig laufen.
**FRs:** FR49, FR50, FR52

---

## Epic 1: Projekt-Bootstrap & Design-System

Chef hat eine laufende Anwendung mit Datenbank, Migrations-Framework, Taxonomie, Design-System und navigierbarer Seitenstruktur.

### Story 1.1: FastAPI-Projekt-Scaffolding mit Docker Compose & PostgreSQL

As a Chef,
I want a running ctrader application with database connectivity,
so that I have the foundation for all subsequent features.

**Acceptance Criteria:**

**Given** das Projekt ist geklont und .env konfiguriert
**When** `docker compose up` ausgefuehrt wird
**Then** startet die FastAPI-App auf 127.0.0.1:8000 und verbindet sich mit PostgreSQL via asyncpg Pool (min=2, max=10)

**Given** die App laeuft
**When** GET / aufgerufen wird
**Then** wird ein 200-Response zurueckgegeben

**Given** die Docker-Compose-Datei
**When** inspiziert
**Then** enthaelt sie genau 2 Services: ctrader und postgres

**Given** den Python-Code
**When** `ruff check` und `ruff format --check` ausgefuehrt werden
**Then** werden keine Fehler gemeldet (NFR-M1)

**Given** den App-Prozess
**When** er an das Netzwerk bindet
**Then** hoert er ausschliesslich auf 127.0.0.1 (NFR-S2)

**Given** ein beliebiges App-Event
**When** geloggt wird
**Then** ist das Log strukturiertes JSON via structlog mit Rotation (max 100MB/File, 5 Rotationen) (NFR-M4)

### Story 1.2: Migrations-Framework & Basis-Infrastruktur

As a Chef,
I want database schema changes to be tracked and reproducible,
so that my database is always in a known, consistent state.

**Acceptance Criteria:**

**Given** die App startet
**When** der Migrations-Runner ausfuehrt
**Then** wird eine `schema_migrations`-Tabelle erstellt, die angewendete Migrationen trackt (FR51)

**Given** Migration 001_initial_schema.sql existiert
**When** `migrate` laeuft
**Then** werden Basis-Enums (trade_source, trade_side, order_status, horizon_type, strategy_status, risk_gate_result) und Common Types erstellt

**Given** eine Migration wurde bereits angewendet
**When** migrate erneut laeuft
**Then** wird die Migration uebersprungen (idempotent, NFR-R7)

**Given** alle Migrationen
**When** jede zweimal angewendet wird
**Then** ist der DB-Zustand identisch mit einmal anwenden

### Story 1.3: Taxonomie-Loader (taxonomy.yaml)

As a Chef,
I want the system to load trading taxonomy from a YAML file,
so that trigger types, exit reasons, regime tags, strategies, and horizons are consistent across the application.

**Acceptance Criteria:**

**Given** taxonomy.yaml existiert mit Trigger-Typen, Exit-Gruenden, Regime-Tags, Strategie-Kategorien, Horizon-Optionen und Mistake-Tags
**When** die App startet
**Then** sind alle Taxonomie-Eintraege geladen und als Singleton verfuegbar (FR14)

**Given** taxonomy.yaml fehlt
**When** die App startet
**Then** wird ein klarer Fehler geloggt und die App bricht kontrolliert ab (fail fast)

**Given** ein beliebiges Modul fragt Taxonomie-Daten an
**When** die Daten zurueckgegeben werden
**Then** stammen sie aus derselben Singleton-Instanz

### Story 1.4: Design-Tokens & Tailwind-CSS-Pipeline

As a Chef,
I want a consistent dark cockpit visual design,
so that the application looks professional and is easy to read during trading.

**Acceptance Criteria:**

**Given** design-tokens.css
**When** inspiziert
**Then** enthaelt es CSS-Custom-Properties fuer: Background-Layer (--bg-void, --bg-chrome, --bg-surface, --bg-elevated), Text-Farben (--text-primary, --text-secondary, --text-muted), P&L-Farben (#3fb950/#f85149), Status-Farben (green/yellow/red), Accent (#58a6ff) (UX-DR1)

**Given** design-tokens.css
**When** inspiziert
**Then** enthaelt es Typographie-Skala (6 Groessen 11-28px), Spacing-Tokens (4/8/12/16/24/32/48px) und Font-Families (Inter, JetBrains Mono) (UX-DR2-4)

**Given** die Tailwind-Konfiguration
**When** via pytailwindcss gebaut wird
**Then** wird CSS ohne Node.js-Dependency kompiliert (UX-DR8)

**Given** ein Viewport < 1024px
**When** eine Seite geladen wird
**Then** wird eine "Minimum 1024px"-Meldung angezeigt (UX-DR29)

**Given** das kompilierte CSS
**When** WCAG-Kontrast geprueft wird
**Then** erreicht Primary-Text auf Void mindestens AA (16.4:1) (UX-DR5)

**Given** Hover-, Focus-, Active-, Disabled- und Selected-States
**When** auf interaktive Elemente angewendet
**Then** entsprechen sie den definierten Token-Werten (UX-DR6)

### Story 1.5: Base-Layout, Top-Bar & Leere Seiten-Shells

As a Chef,
I want persistent navigation and page structure,
so that I can navigate between all main views of ctrader.

**Acceptance Criteria:**

**Given** eine beliebige Seite
**When** geladen
**Then** ist ein persistenter Top-Bar sichtbar mit: Logo (links), Navigation-Links Journal/Strategies/Approvals/Trends/Regime/Settings (Mitte), Health-Status-Placeholder-Dots (rechts) (UX-DR78)

**Given** die aktuelle Route
**When** die Seite laedt
**Then** ist der aktive Navigation-Link in --accent-Farbe hervorgehoben

**Given** den Top-Bar
**When** inspiziert
**Then** enthaelt er keine Hamburger-Menus, Slide-Out-Drawers oder Tab-Bars (UX-DR82)

**Given** einen Navigation-Link
**When** geklickt
**Then** navigiert er zur entsprechenden leeren Seiten-Shell

**Given** den Seiten-Inhalt
**When** gerendert
**Then** ist er zentriert mit max-width 1440px und --bg-void fuellt den Raum darueber hinaus (UX-DR31)

**Given** die Jinja2-Template-Struktur
**When** inspiziert
**Then** existieren Stub-Macros fuer alle 13 Component-Macros in app/templates/components/ (UX-DR9)

### Story 1.6: MCP-Client-Wrapper & Contract-Snapshot

As a Chef,
I want a verified connection to the fundamental MCP server,
so that I know the AI integration works before building features on top of it.

**Acceptance Criteria:**

**Given** der fundamental MCP-Server laeuft
**When** die App startet
**Then** wird eine HTTP/SSE-Verbindung hergestellt und eine Tools-Liste abgerufen

**Given** die MCP-Verbindung ist erfolgreich
**When** Tools gelistet werden
**Then** werden die verfuegbaren Tools als Contract-Snapshot-JSON in data/mcp-snapshots/ gespeichert

**Given** der MCP-Server laeuft nicht
**When** die App startet
**Then** wird eine Warnung geloggt und die App faehrt fort (Graceful Degradation, kein Crash)

**Given** den MCP-Client-Wrapper
**When** ein beliebiger MCP-Call ausgefuehrt wird
**Then** erzwingt er einen 10-Sekunden-Timeout (NFR-I1)

---

## Epic 2: Trade-Journal & IB-Import

Chef kann seine IB-Aktien- und Options-Trades importieren und in einer einheitlichen, chronologisch sortierbaren Liste mit Drilldown durchblaettern.

### Story 2.1: Trade-Datenmodell & IB Flex Query Import

As a Chef,
I want to import my historical IB stock and options trades via Flex Query,
so that my trading history is captured in ctrader from day one.

**Acceptance Criteria:**

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die `trades`-Tabelle erstellt mit: id, symbol, asset_class, side, quantity, entry_price, exit_price, opened_at (TIMESTAMPTZ), closed_at, pnl, fees, broker (trade_source enum), perm_id, trigger_spec (JSONB), und allen relevanten Indizes (FR1, FR2)

**Hinweis:** `strategy_id` und `agent_id` werden NICHT in dieser Story angelegt, da die referenzierten Tabellen erst in spaeteren Epics erstellt werden. Die Spalten werden per ALTER TABLE ergaenzt in Story 6.1 (strategy_id) und Story 8.1 (agent_id).

**Given** eine IB Flex Query XML-Datei mit Aktien-Trades
**When** der Import ausgefuehrt wird
**Then** werden alle Trades korrekt geparst und in die trades-Tabelle eingefuegt (FR1)

**Given** eine IB Flex Query XML-Datei mit Single-Leg-Options-Trades
**When** der Import ausgefuehrt wird
**Then** werden Options-Trades korrekt importiert; Multi-Leg-Spreads werden ignoriert mit Log-Warnung (FR2)

**Given** ein Trade mit identischem permId existiert bereits
**When** derselbe Trade erneut importiert wird
**Then** wird kein Duplikat erstellt; die Zeile bleibt unveraendert (FR4, NFR-R1)

### Story 2.2: Live-IB-Sync & Reconciliation

As a Chef,
I want my IB trades to sync automatically in real-time,
so that I don't have to manually trigger imports during the trading day.

**Acceptance Criteria:**

**Given** die App laeuft und ib_async mit TWS/Gateway verbunden ist
**When** eine neue Execution bei IB stattfindet
**Then** wird der Trade automatisch in die trades-Tabelle synchronisiert ohne manuellen Anstoss (FR3)

**Given** Live-Sync und Flex-Nightly liefern abweichende Daten fuer denselben Trade
**When** Reconciliation laeuft
**Then** wird Flex-Query als Source-of-Truth behandelt und der Trade entsprechend aktualisiert (FR5)

**Given** die TWS/Gateway-Verbindung bricht ab
**When** die Verbindung wiederhergestellt wird
**Then** reconnected ib_async automatisch und setzt den Sync fort ohne Trade-Verlust (NFR-R2)

**Given** einen bereits via Live-Sync erfassten Trade
**When** derselbe Trade via Flex-Nightly importiert wird
**Then** wird kein Duplikat erstellt (Erkennung via permId) (FR4)

### Story 2.3: Journal-Startseite — Trade-Liste & Untagged-Zaehler

As a Chef,
I want to see all my trades in a unified, chronologically sorted list with an untagged counter,
so that I can quickly scan my trading activity and identify trades that need tagging.

**Acceptance Criteria:**

**Given** Trades aus IB und cTrader existieren in der Datenbank
**When** die Journal-Startseite geladen wird
**Then** werden alle Trades in einer einheitlichen, chronologisch sortierten Liste angezeigt (neueste zuerst) (FR8)

**Given** die Trade-Liste
**When** gerendert
**Then** zeigt jede Zeile via trade_row-Macro: Symbol, Side, Entry-Time, P&L (farbig), Trigger-Type, Horizon, Status-Indikator (UX-DR11, UX-DR96)

**Given** es existieren untagged manuelle Trades
**When** die Journal-Startseite geladen wird
**Then** wird ein prominenter Zaehler mit Anzahl ungetaggter Trades angezeigt (FR11, UX-DR77)

**Given** die Trade-Liste hat mehr als 30 Eintraege
**When** die Seite geladen wird
**Then** wird Pagination mit 30 Trades/Seite angezeigt (?page=N) mit Pfeiltasten-Navigation (UX-DR46, UX-DR102)

**Given** die Journal-Startseite
**When** geladen bei <= 2000 Trades
**Then** laedt sie vollstaendig innerhalb von 1.5 Sekunden (NFR-P1)

**Given** P&L-Werte in der Trade-Liste
**When** gerendert
**Then** sind Gewinne in #3fb950, Verluste in #f85149, R-Multiples mit einer Dezimale, NULL als "NULL", leere Felder als em-dash (UX-DR69, UX-DR70)

### Story 2.4: Trade-Drilldown — Inline Expansion

As a Chef,
I want to drill into any trade to see full details including P&L, timing, and provenance,
so that I can understand every aspect of a trade decision.

**Acceptance Criteria:**

**Given** eine Trade-Zeile in der Journal-Liste
**When** geklickt
**Then** expandiert eine Detail-Ansicht inline unterhalb der Zeile (nicht als Modal) (FR9, UX-DR25, UX-DR40)

**Given** den expandierten Trade-Drilldown
**When** angezeigt
**Then** sind sichtbar: Symbol, Side, Entry/Exit-Preis, Size, P&L (inkl. Gebuehren/Funding-Rates), Expectancy-at-Entry, R-Multiple (oder NULL bei fehlendem Stop-Loss, nie "0"), Zeitstempel, Broker, Strategie (FR12, UX-DR73)

**Given** eine offene Inline-Expansion
**When** Escape gedrueckt oder die Zeile erneut geklickt wird
**Then** schliesst sich die Expansion (UX-DR40)

**Given** eine offene Expansion
**When** die URL inspiziert wird
**Then** enthaelt sie ?expand={id} fuer Bookmarkability (UX-DR45)

**Given** nur eine Expansion ist erlaubt
**When** eine andere Trade-Zeile geklickt wird
**Then** schliesst sich die aktuelle und oeffnet die neue Expansion (UX-DR40)

**Given** den Trade-Drilldown bei Cache-Miss
**When** geladen
**Then** erscheint er innerhalb von 3 Sekunden (NFR-P2)

**Given** den Trade-Drilldown
**When** angezeigt
**Then** zeigt er Core-Fields immer, und Advanced-Metrics (MFE/MAE, Regime-Kontext, Full-Trigger-Spec) in expandierbaren Sections (UX-DR100)

---

## Epic 3: Trade-Tagging & Trigger-Provenance

Chef kann jeden manuellen Trade post-hoc taggen (Strategie, Trigger, Horizon, Exit-Grund, Mistakes) und die Trigger-Provenance als lesbaren Text statt Raw-JSON sehen.

### Story 3.1: Post-hoc-Tagging-Formular

As a Chef,
I want to tag my manual trades with strategy, trigger, horizon, and exit reason,
so that I can later analyze my trading patterns and decision quality.

**Acceptance Criteria:**

**Given** einen ungetaggten manuellen Trade im Drilldown
**When** das Tagging-Formular angezeigt wird
**Then** enthaelt es: Strategy-Dropdown, Trigger-Source, Horizon, Exit-Reason (4 Pflichtfelder) plus optionale Mistake-Tags und Freitext-Notiz (FR15, UX-DR58)

**Given** das Strategy-Dropdown
**When** gerendert vor Epic 6 (strategies-Tabelle existiert noch nicht)
**Then** zeigt es die Strategie-Kategorien aus `taxonomy.yaml` als Auswahl-Werte an (Fallback-Quelle)

**Given** das Strategy-Dropdown
**When** gerendert nach Epic 6 (strategies-Tabelle existiert)
**Then** zeigt es die user-definierten Strategie-Instanzen aus der strategies-Tabelle an (mit Upgrade-Pfad fuer existierende Tags von Kategorie-Strings auf strategy_id)

**Given** das Tagging-Formular
**When** geoeffnet
**Then** ist das erste Feld auto-fokussiert, Tab navigiert zwischen Feldern, Enter auf dem letzten Feld speichert sofort (kein Submit-Button) (UX-DR58, UX-DR62)

**Given** die Dropdown-Felder
**When** geoeffnet
**Then** unterstuetzen sie Fuzzy-Search-Filtering fuer schnelle Auswahl (UX-DR60)

**Given** ein Trade wurde erfolgreich getaggt
**When** die Submission abgeschlossen ist
**Then** erscheint ein Success-Toast (bottom-right, gruen, 3s) und der naechste ungetaggte Trade wird automatisch angezeigt (UX-DR34, UX-DR51)

**Given** Form-Labels
**When** gerendert
**Then** sind sie uppercase, 11px, --text-muted, letter-spacing 0.05em, ueber dem Feld, mit explizitem `<label for>` (UX-DR61)

**Given** eine Validierungsverletzung
**When** ein Feld den Fokus verliert (blur)
**Then** erscheint ein roter Rahmen + Fehlertext unterhalb des Feldes (UX-DR59)

### Story 3.2: Trigger-Spec JSONB & Auto-Befuellung

As a Chef,
I want every trade to have a structured trigger specification,
so that I can trace exactly why each trade was entered.

**Acceptance Criteria:**

**Given** die trades-Tabelle
**When** inspiziert
**Then** hat die trigger_spec-Spalte einen GIN-Index fuer effiziente Facet-Queries (FR16)

**Given** ein Bot-Trade wird aus einem genehmigten Proposal erstellt
**When** der Trade in die DB geschrieben wird
**Then** wird die trigger_spec automatisch aus dem Proposal befuellt (FR17)

**Given** ein manueller Trade wird ueber das Tagging-Formular getaggt
**When** gespeichert wird
**Then** wird eine konforme trigger_spec (JSONB) aus den Form-Daten generiert und gespeichert (FR17)

**Given** die trigger_spec
**When** inspiziert
**Then** ist sie konform zum fundamental/trigger-evaluator-Schema mit snake_case Keys (FR16)

### Story 3.3: Lesbare Trigger-Spec-Darstellung

As a Chef,
I want to see the trigger specification as readable text instead of raw JSON,
so that I can quickly understand the trade rationale without parsing technical data.

**Acceptance Criteria:**

**Given** einen Trade mit vollstaendiger trigger_spec
**When** im Drilldown angezeigt
**Then** rendert das trigger_spec_readable-Macro die Spec als natuerlichsprachige Saetze (z.B. "Satoshi (Confidence 72%, Horizon: Swing) empfahl Long BTCUSD — Chef folgte der Empfehlung.") (FR18, UX-DR18)

**Given** einen Trade mit teilweise befuellter trigger_spec
**When** im Drilldown angezeigt
**Then** werden fehlende Felder als "Unbekannt" dargestellt (UX-DR18)

**Given** einen Trade ohne trigger_spec
**When** im Drilldown angezeigt
**Then** wird "Nicht getaggt" angezeigt (UX-DR18)

**Given** das trigger_spec_readable-Macro
**When** inspiziert
**Then** enthaelt es 20-30 Template-Patterns fuer verschiedene Trigger-Typen (UX-DR74)

### Story 3.4: Mistake-Tags & Top-N-Report

As a Chef,
I want to tag trading mistakes and see a report of my most costly errors,
so that I can identify and eliminate recurring behavioral patterns.

**Acceptance Criteria:**

**Given** das Tagging-Formular
**When** Mistake-Tags ausgewaehlt werden
**Then** kann ein Trade null, eine oder mehrere Mistake-Tags tragen (fomo, no-stop, revenge, overrode-own-rules, oversized, ignored-risk-gate) (FR18a)

**Given** Trades mit Mistake-Tags existieren
**When** der Top-N-Mistakes-Report aufgerufen wird mit einem Zeitfenster
**Then** werden Mistakes nach Haeufigkeit und nach aggregierten $-Kosten (Summe P&L aller Trades mit diesem Tag) sortiert angezeigt (FR18b)

**Given** den Mistakes-Report
**When** Facetten aus FR10 angewendet werden
**Then** ist der Report weiter filterbar (FR18b)

---

## Epic 4: Journal-Intelligence — Facetten, Aggregation & Visualisierung

Chef kann gezielte Fragen an sein Journal stellen und bekommt Aggregationen, P&L-Kalender, MAE/MFE und interaktive OHLC-Charts.

### Story 4.1: Facetten-Filter-System

As a Chef,
I want to filter my journal by multiple facets simultaneously,
so that I can quickly find specific trade patterns and answer analytical questions.

**Acceptance Criteria:**

**Given** die Journal-Startseite
**When** Facetten angezeigt werden
**Then** ist das Facet-Framework implementiert und zeigt die initial verfuegbaren Facetten an: Asset-Class, Broker, Horizon (basieren auf Daten aus Epic 2). Das Framework ist so gebaut, dass weitere Facetten automatisch aktiviert werden, sobald die zugehoerigen Spalten/Datenquellen in spaeteren Epics landen: Strategy (Epic 6), Trigger-Source (Epic 5/10), Followed-vs-Override (Epic 7), Confidence-Band (Epic 7), Regime-Tag (Epic 9). FR10 ist final erfuellt, wenn alle 8 Facetten aktiv sind (spaetestens mit Abschluss Epic 9). (FR10, UX-DR47)

**Given** eine noch nicht implementierte Facette (z.B. Strategy vor Abschluss Epic 6)
**When** die Facet-Bar gerendert wird
**Then** wird die Facette ausgeblendet ODER als "keine Werte" disabled angezeigt — kein Fehler, kein leerer Dropdown (Graceful Degradation)

**Given** eine Facette
**When** ein Wert angeklickt wird
**Then** wird die Trade-Liste sofort per HTMX aktualisiert (kein Apply-Button), innerhalb von 500ms (UX-DR37, NFR-P3)

**Given** der facet_chip
**When** aktiv
**Then** ist er in --accent-Farbe hervorgehoben mit Badge-Count und aria-pressed (UX-DR12)

**Given** der facet_bar
**When** >= 1 Filter aktiv ist
**Then** erscheint ein Reset-Link; Arrow-Key-Navigation zwischen Chips ist moeglich (UX-DR13)

**Given** aktive Facetten
**When** die URL inspiziert wird
**Then** sind alle Filter-States in der URL encodiert (?asset_class=crypto&trigger_source=satoshi) via hx-push-url (UX-DR45, UX-DR108)

**Given** Shift+Click auf einen Facet-Wert
**When** bereits ein Wert derselben Facette aktiv ist
**Then** werden beide Werte als Multi-Select kombiniert ("Crypto OR CFDs") (UX-DR38)

### Story 4.2: Aggregation, Hero-Metriken & Query-Prosa

As a Chef,
I want to see aggregated metrics for any facet combination,
so that I can evaluate the statistical performance of trade subsets.

**Acceptance Criteria:**

**Given** eine beliebige Facetten-Kombination
**When** aktiv
**Then** zeigt der Hero-Aggregation-Block: Trade Count, Expectancy (R-Multiple), Winrate (%), Drawdown (R-Multiple) — jeweils in Monospace 28px mit Sparkline darunter (FR13, UX-DR14, UX-DR68)

**Given** die Aggregation
**When** berechnet bei <= 2000 Trades
**Then** erscheint das Ergebnis innerhalb von 800ms (NFR-P4)

**Given** aktive Facetten
**When** die Hero-Aggregation aktualisiert wird
**Then** geschieht dies mit sanftem Opacity-Flash (1→0.5→1), ohne Layout-Jump (UX-DR42)

**Given** aktive Facetten
**When** die query_prose-Komponente rendert
**Then** zeigt sie eine lesbare Beschreibung der Query (z.B. "Crypto-Shorts mit Satoshi-Override") oder "Alle Trades" bei leeren Filtern (UX-DR21)

**Given** die Aggregation
**When** serverseitig gecached
**Then** wird der Cache nur bei neuen Trades/Tags/Approvals invalidiert (UX-DR103)

### Story 4.3: MAE/MFE-Berechnung

As a Chef,
I want to see Maximum Adverse and Favorable Excursion for each trade,
so that I can evaluate my entry timing and stop-loss placement.

**Acceptance Criteria:**

**Given** einen Trade mit bekanntem Zeitraum
**When** der Drilldown geladen wird
**Then** werden MAE und MFE angezeigt — jeweils in Preis-Einheiten und Position-Dollar-Einheiten (FR13a)

**Given** einen Trade
**When** MAE/MFE berechnet werden soll
**Then** werden Intraday-Candle-Daten (1m/5m) via ib_async reqHistoricalData() geholt; bei Fehler Fallback auf Binance/Kraken API oder fundamental/price MCP

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die `ohlc_candles`-Tabelle erstellt mit: id, symbol, timeframe (enum: '1m','5m'), ts (TIMESTAMPTZ), open, high, low, close, volume, cached_at (TIMESTAMPTZ), UNIQUE (symbol, timeframe, ts), `idx_ohlc_candles_symbol_ts` Index

**Given** die Candle-Daten
**When** geholt
**Then** werden sie in der ohlc_candles-Tabelle mit 24h TTL gecached (Cache-Lookup prueft `cached_at > now() - interval '24 hours'`) (NFR-I6)

**Given** die Datenquelle ist nicht erreichbar
**When** MAE/MFE berechnet werden soll
**Then** werden die Felder als NULL angezeigt (Graceful Degradation) mit Timeout <= 15s (NFR-I6)

### Story 4.4: P&L-Kalender-View

As a Chef,
I want a calendar view of my daily P&L,
so that I can spot patterns in my trading performance over time.

**Acceptance Criteria:**

**Given** die Journal-Seite
**When** der Kalender-View aktiviert wird
**Then** wird ein Monatsraster angezeigt mit jeder Zelle als Handelstag (FR13b)

**Given** eine Kalender-Zelle
**When** gerendert via calendar_cell-Macro
**Then** ist sie gruen getintet bei Gewinn, rot bei Verlust, grau bei keinem Trading, und der aktuelle Tag hat einen Accent-Border (UX-DR19, UX-DR72)

**Given** eine Kalender-Zelle
**When** geklickt
**Then** wird die Journal-Liste per HTMX auf diesen Tag gefiltert (FR13b, UX-DR19)

**Given** die Kalender-Zelle
**When** inspiziert
**Then** hat sie role="gridcell" und aria-label mit Datum und P&L (UX-DR19)

### Story 4.5: Interaktiver OHLC-Chart mit lightweight-charts

As a Chef,
I want an interactive OHLC chart with entry/exit markers in the trade drilldown,
so that I can visually analyze the price action around my trades.

**Acceptance Criteria:**

**Given** einen Trade im Drilldown
**When** der Chart-Bereich geladen wird
**Then** wird ein interaktiver OHLC-Chart via lightweight-charts gerendert mit Candlestick-Daten fuer den Trade-Zeitraum (FR13c)

**Given** den OHLC-Chart
**When** gerendert
**Then** sind Entry- und Exit-Zeitpunkte als Marker auf dem Chart sichtbar

**Given** den Chart-Daten-Endpoint GET /trades/{id}/chart_data
**When** aufgerufen
**Then** liefert er JSON mit OHLC-Daten, Entry/Exit-Markern und optionalen Indikatoren

**Given** die Candle-Daten sind nicht verfuegbar
**When** der Chart geladen wird
**Then** wird ein Platzhalter mit "Chart-Daten nicht verfuegbar" in --text-muted angezeigt (UX-DR55)

### Story 4.6: Command Palette

As a Chef,
I want a keyboard-driven command palette for fast navigation and search,
so that I can quickly jump to any view, strategy, or saved query without mouse navigation.

**Acceptance Criteria:**

**Given** eine beliebige Seite
**When** Ctrl+K gedrueckt wird
**Then** oeffnet sich ein 600px zentriertes Overlay mit Suchfeld (UX-DR50)

**Given** die Command Palette ist offen
**When** Text eingegeben wird
**Then** werden Ergebnisse via Fuzzy-Matching ueber Routes, Strategien, Trade-IDs und Facet-Presets angezeigt (UX-DR49)

**Given** ein Ergebnis in der Palette
**When** Enter gedrueckt wird
**Then** navigiert der Browser zur entsprechenden Seite (UX-DR23)

**Given** die Command Palette ist offen
**When** Escape gedrueckt wird
**Then** schliesst sich das Overlay

**Given** die command_palette_item-Eintraege
**When** inspiziert
**Then** haben sie role="option" in einer Listbox mit aria-activedescendant fuer Keyboard-Navigation (UX-DR23)

**Given** gespeicherte Query-Presets
**When** in der Palette gesucht
**Then** erscheinen sie als navigierbare Eintraege (UX-DR106)

### Story 4.7: Daten-Export (CSV)

As a Chef,
I want to export my journal data as CSV,
so that I can analyze trades in external tools like Excel.

**Acceptance Criteria:**

**Given** die Journal-Ansicht mit aktiven Filtern
**When** der Export-Button geklickt wird
**Then** wird eine CSV-Datei mit allen gefilterten Trades heruntergeladen (UX-DR105)

**Given** die exportierte CSV
**When** in Excel geoeffnet
**Then** sind alle Spalten korrekt formatiert und importierbar (UX-DR105)

**Given** die aktive Query
**When** der Star-Icon im Hero-Block geklickt wird
**Then** wird die Filter-Kombination als benannter Preset gespeichert mit Toast-Bestaetigung (UX-DR106)

---

## Epic 5: Fundamental-Integration (MCP-Layer)

Chef sieht im Trade-Drilldown die damalige und aktuelle Fundamental-Einschaetzung von Viktor/Satoshi, mit Staleness-Anzeige und Graceful Degradation bei MCP-Outages.

### Story 5.1: MCP-Fundamental-Abruf mit TTL-Cache

As a Chef,
I want the system to fetch fundamental assessments from Viktor and Satoshi via MCP,
so that I have AI analyst opinions available for my trade decisions.

**Acceptance Criteria:**

**Given** ein Asset-Symbol
**When** eine Fundamental-Einschaetzung angefragt wird
**Then** ruft das System via MCP Viktor (Aktien/SFA) oder Satoshi (Crypto/CFA) ab (FR19)

**Given** ein Fundamental-Ergebnis
**When** gecached
**Then** wird es mit cached_at-Timestamp gespeichert; TTL: 15 Minuten fuer Crypto, 1 Stunde fuer Aktien (FR22, NFR-I2)

**Given** ein gecachtes Ergebnis
**When** im UI angezeigt
**Then** zeigt eine Staleness-Anzeige "Stand: vor X Minuten" den Zeitpunkt der letzten Aktualisierung (FR22)

**Given** den MCP-Client
**When** ein Call ausgefuehrt wird
**Then** wird der 10s-Timeout aus dem MCP-Wrapper (Story 1.6) erzwungen; bei Timeout wird der Cache-Fallback mit Staleness-Banner verwendet (NFR-I1)

### Story 5.2: Fundamental im Trade-Drilldown (Side-by-Side)

As a Chef,
I want to see the fundamental assessment at trade time alongside the current assessment,
so that I can evaluate whether the market thesis has changed since my entry.

**Acceptance Criteria:**

**Given** einen Trade im Drilldown
**When** die Fundamental-Sektion geladen wird
**Then** werden die damalige Einschaetzung (gespeichert zum Trade-Zeitpunkt) und die aktuelle Einschaetzung (live via MCP) side-by-side angezeigt (FR20)

**Given** die damalige Einschaetzung existiert nicht (z.B. alter Import)
**When** angezeigt
**Then** wird "Keine historische Einschaetzung verfuegbar" in --text-muted angezeigt

**Given** die aktuelle Einschaetzung ist nicht verfuegbar (MCP-Outage)
**When** angezeigt
**Then** wird "N/A (letzter Stand: HH:MM)" mit Staleness-Banner angezeigt (UX-DR57)

### Story 5.3: MCP-Graceful-Degradation & Staleness-Banner

As a Chef,
I want the application to remain functional during MCP outages,
so that I can continue reviewing my journal even when AI services are unavailable.

**Acceptance Criteria:**

**Given** der MCP-Server ist nicht erreichbar
**When** Journal, Strategy oder Regime Views geladen werden
**Then** bleiben diese Views voll funktional; betroffene Spalten zeigen "N/A (HH:MM)" (FR23, NFR-R6, UX-DR57)

**Given** ein MCP-Outage
**When** die Seite geladen wird
**Then** erscheint ein staleness_banner unter dem Top-Bar: gelbe Akzent-Leiste mit "Viktor-MCP: letztes Update HH:MM, Cache abgelaufen" (UX-DR20, UX-DR53)

**Given** den Staleness-Banner
**When** die Staleness > 24h betraegt
**Then** wechselt der Banner von gelb auf rot (Critical) mit role="alert" und aria-live="assertive" (UX-DR20)

**Given** den Staleness-Banner
**When** konfiguriert
**Then** pollt er optional via hx-get alle 60 Sekunden den Status (UX-DR20)

### Story 5.4: Taeglicher MCP-Contract-Test

As a Chef,
I want daily verification that the MCP API contract hasn't changed,
so that I'm warned early about breaking changes in the fundamental server.

**Acceptance Criteria:**

**Given** der Contract-Snapshot aus Woche 0 existiert
**When** der taegliche Contract-Test laeuft
**Then** vergleicht er die aktuelle Tool-Schema-Liste gegen den Snapshot (FR24)

**Given** ein Drift wird erkannt
**When** der Test abgeschlossen ist
**Then** erscheint ein UI-Warning-Banner innerhalb von 24h ohne den Trade-Flow zu blockieren (FR24, NFR-R4)

**Given** der Contract-Test
**When** das Ergebnis PASS ist
**Then** wird das Ergebnis im Health-Widget angezeigt mit Timestamp

**Given** der MCP-Server ist nicht erreichbar fuer den Test
**When** der Test ausgefuehrt wird
**Then** wird der Fehler geloggt und beim naechsten Lauf erneut versucht (keine Silent Failure)

---

## Epic 6: Strategy-Management

Chef kann Trading-Strategien definieren, ihre Performance empirisch verfolgen (Expectancy, R-Multiple, Drawdown), Notizen schreiben und den Status zwischen active/paused/retired wechseln.

### Story 6.1: Strategy-Datenmodell & CRUD

As a Chef,
I want to create and manage trading strategies with defined parameters,
so that I can systematically track the performance of each approach.

**Acceptance Criteria:**

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die `strategies`-Tabelle erstellt mit: id, name, asset_class, horizon (horizon_type enum), typical_holding_period, trigger_sources (JSONB array), risk_budget_per_trade, status (strategy_status enum: active/paused/retired), created_at, updated_at (FR33)

**Given** dieselbe Migration
**When** migrate laeuft
**Then** wird die trades-Tabelle per `ALTER TABLE trades ADD COLUMN strategy_id INT REFERENCES strategies(id) ON DELETE SET NULL` erweitert inklusive `idx_trades_strategy_id` Index (schliesst Issue M1 der Readiness-Review)

**Given** die Strategies-Seite
**When** "Neue Strategie" geklickt wird
**Then** oeffnet sich ein Formular mit Pflichtfeldern: Name, Asset-Class, Horizon, Typical-Holding-Period, Trigger-Quelle(n), Risikobudget pro Trade (FR33)

**Given** eine existierende Strategie
**When** der Status-Badge (Active/Paused/Retired) geklickt wird
**Then** wechselt der Status mit einem Klick und zeigt einen Toast zur Bestaetigung (FR38, UX-DR76)

### Story 6.2: Strategy-Liste mit Metriken & Gruppierung

As a Chef,
I want a strategy list with aggregated performance metrics,
so that I can compare strategies at a glance and identify winners and losers.

**Acceptance Criteria:**

**Given** die Strategies-Seite
**When** geladen
**Then** zeigt die linke Pane (320px) eine Liste aller Strategien mit: Anzahl Trades (total + diese Woche), Expectancy, R-Multiple-Verteilung, Drawdown, aktueller Status-Badge (FR34, UX-DR26)

**Given** die Strategy-Liste
**When** der Horizon-Grouping-Toggle aktiviert wird
**Then** werden Strategien nach Horizon gruppiert (intraday / swing / position) (FR35)

**Given** die Strategy-Liste
**When** ein Spalten-Header geklickt wird
**Then** wird nach dieser Metrik sortiert (FR35)

**Given** den Zwei-Pane-Split
**When** eine Strategie in der Liste geklickt wird
**Then** zeigt die rechte Pane (min 800px) die Strategie-Detailansicht (UX-DR26)

### Story 6.3: Strategy-Detailansicht & Expectancy-Analyse

As a Chef,
I want a detailed strategy view with expectancy curves and trade breakdown,
so that I can evaluate strategy effectiveness over time and against AI recommendations.

**Acceptance Criteria:**

**Given** eine Strategie im Detail
**When** angezeigt
**Then** zeigt die rechte Pane: Hero-Aggregation-Block (Expectancy, Winrate, Drawdown, Trade Count), darunter die vollstaendige Trade-Liste dieser Strategie (FR36)

**Given** die Strategy-Detailansicht
**When** die Expectancy-Kurve angezeigt wird
**Then** zeigt sie den Expectancy-Verlauf ueber Zeit als Chart (FR36)

**Given** die Strategy-Detailansicht
**When** der Gefolgt-vs-Ueberstimmt-Breakdown angezeigt wird
**Then** zeigt er die Performance-Aufteilung: Trades wo Chef dem Agent folgte vs. wo er ueberstimmte (FR36)

**Given** die Strategies-Seite
**When** Expectancy pro Horizon angezeigt wird
**Then** werden Aggregationen ueber alle Strategien pro Horizon (intraday/swing/position) sichtbar (FR40)

### Story 6.4: Strategy-Notizen & Versionshistorie

As a Chef,
I want to write notes on my strategies with version history,
so that I can document my evolving thinking about each approach.

**Acceptance Criteria:**

**Given** die Strategy-Detailansicht
**When** eine Freitext-Notiz geschrieben und gespeichert wird
**Then** wird sie mit Zeitstempel als eigener Eintrag in der Versionshistorie gespeichert (FR37)

**Given** mehrere Notizen zu einer Strategie
**When** die Versionshistorie angezeigt wird
**Then** sind alle Notizen chronologisch sortiert mit Zeitstempel sichtbar (FR37)

### Story 6.5: Strategy-Status-Enforcement im Bot-Pfad

As a Chef,
I want paused and retired strategies to be blocked from generating new proposals,
so that I can confidently pause underperforming strategies without worrying about rogue bot trades.

**Acceptance Criteria:**

**Given** eine Strategie mit Status "paused" oder "retired"
**When** der Bot-Execution-Pfad prueft
**Then** werden keine neuen Proposals fuer diese Strategie generiert (FR39)

**Given** eine Strategie wird von "active" auf "paused" gesetzt
**When** bereits ein Pending-Proposal fuer diese Strategie existiert
**Then** bleibt das bestehende Proposal unveraendert (Chef kann es noch manuell ablehnen)

---

## Epic 7: Approval-Pipeline & Risk-Gate

Chef kann Bot-Proposals im Approval-Dashboard sichten, alle entscheidungsrelevanten Infos in einem Viewport sehen (Agent + Fundamental + Risk-Gate + Regime), und sicher genehmigen/ablehnen mit unveraenderlichem Audit-Log.

### Story 7.1: Proposal-Datenmodell & Approval-Dashboard

As a Chef,
I want to see all pending bot proposals in a dashboard,
so that I can efficiently review and act on AI trading recommendations.

**Acceptance Criteria:**

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** werden `proposals`-Tabelle (id, agent_id, strategy_id, symbol, asset_class, side, horizon, entry_price, stop_price, target_price, position_size, risk_budget, trigger_spec JSONB, risk_gate_result, risk_gate_response JSONB, status, created_at, decided_at) und `audit_log`-Tabelle erstellt

**Given** die Approvals-Seite
**When** geladen
**Then** zeigt sie alle offenen Bot-Proposals als Cards mit: Agent-Name, Strategie, Asset, Horizon, vorgeschlagene Position, Risk-Gate-Status-Badge (FR25)

**Given** das Approval-Dashboard
**When** geladen
**Then** erscheint es innerhalb von 2 Sekunden inklusive MCP-Calls bei Cache-Miss (NFR-P5)

### Story 7.2: Risk-Gate-Integration (Rita & Cassandra)

As a Chef,
I want every bot proposal to be automatically risk-assessed,
so that I'm protected from approving dangerously risky trades.

**Acceptance Criteria:**

**Given** ein neues Proposal wird erstellt
**When** es in die Pipeline eintritt
**Then** fuehrt das System automatisch ein Risk-Gate via Rita (Aktien) oder Cassandra (Crypto) per MCP aus mit dreistufigem Ergebnis: GREEN, YELLOW, RED (FR27)

**Given** ein Risk-Gate-Ergebnis RED
**When** das Proposal im Dashboard angezeigt wird
**Then** ist der Approve-Button technisch blockiert (disabled, cursor: not-allowed) — es gibt keinen Workaround (FR28, UX-DR56)

**Given** ein Risk-Gate-Ergebnis YELLOW
**When** das Proposal angezeigt wird
**Then** wird eine Warnung angezeigt aber der Approve-Button bleibt klickbar (UX-DR56)

**Given** die Risk-Gate-Response
**When** gespeichert
**Then** wird die volle Response als JSONB im Proposal gespeichert fuer den Audit-Log

### Story 7.3: Proposal-Drilldown & Single-Viewport-Entscheidung

As a Chef,
I want all decision-relevant information in one viewport without scrolling,
so that I can make fast, informed approval decisions.

**Acceptance Criteria:**

**Given** ein Proposal im Dashboard
**When** geklickt
**Then** expandiert der proposal_viewport als Inline-Expansion mit 3-Spalten-Layout (~440px): Agent-Vorschlag | Fundamental-Einschaetzung | Risk-Gate-Status (FR26, UX-DR22, UX-DR27)

**Given** den Proposal-Viewport
**When** bei 1440px x ~850px angezeigt
**Then** sind alle entscheidungsrelevanten Infos sichtbar ohne Scroll: Agent-Proposal, Fundamental (aktuell via MCP, FR21), Risk-Gate, Regime-Kontext (Footer), Action-Buttons (Footer) (UX-DR67, UX-DR99)

**Given** die Fundamental-Einschaetzung im Proposal
**When** nicht verfuegbar (MCP-Outage)
**Then** zeigt die mittlere Spalte den Staleness-State statt einen Fehler (UX-DR22)

**Given** den Proposal-Viewport
**When** das Risk-Gate RED ist
**Then** ist der Approve-Button grau/disabled und der "Decision Point" visuell dominant (UX-DR99)

### Story 7.4: Approve, Reject & Revision-Flow

As a Chef,
I want to approve, reject, or send back proposals with clear audit trails,
so that every decision is documented and I maintain full control over automated trading.

**Acceptance Criteria:**

**Given** ein Proposal mit YELLOW- oder GREEN-Status
**When** Chef "Approve" waehlt
**Then** muss ein Risikobudget als Pflichtfeld gesetzt werden (Default aus Proposal, ueberschreibbar) (FR29, UX-DR63)

**Given** ein Proposal
**When** Chef die Fundamental-Einschaetzung ueberstimmen will
**Then** setzt ein optionaler Override-Checkbox overrode_fundamental=true (FR31, UX-DR63)

**Given** ein Proposal
**When** Chef "Reject" waehlt
**Then** erscheint ein optionales Begruendungs-Feld; das Proposal verschwindet sofort aus der Pending-Liste mit Toast "Rejected" (FR30, UX-DR64)

**Given** ein Proposal
**When** Chef "Revision" waehlt
**Then** wird das Proposal mit optionaler Notiz an den Agent zurueckgeschickt; Status wechselt auf "revision" (FR30, UX-DR65)

**Given** die Approval-Action-Buttons
**When** inspiziert
**Then** sind sie keyboard-accessible: A fuer Approve (primary, filled), R fuer Reject (secondary, outlined), mit sichtbaren Shortcut-Badges (UX-DR43, UX-DR44, UX-DR66)

### Story 7.5: Unveraenderlicher Audit-Log

As a Chef,
I want an immutable audit trail for every approval decision,
so that I can always reconstruct why a trade was approved and under what conditions.

**Acceptance Criteria:**

**Given** ein Proposal wird genehmigt oder abgelehnt
**When** die Entscheidung gespeichert wird
**Then** wird ein Audit-Log-Eintrag erstellt mit: Zeitstempel, genehmigtes Risikobudget, Risk-Gate-Snapshot (volle Response), Override-Flags, Strategie-Version, Fundamental-Einschaetzung (FR32, NFR-R8)

**Given** die audit_log-Tabelle
**When** ein UPDATE oder DELETE versucht wird
**Then** wird die Operation via PostgreSQL BEFORE UPDATE OR DELETE Trigger mit RAISE EXCEPTION 'audit log is append-only' verhindert (NFR-S3)

**Given** den Audit-Log
**When** inspiziert
**Then** ist jede historische Approval-Entscheidung allein aus dem Log reproduzierbar (NFR-R8)

---

## Epic 8: Bot-Execution (cTrader)

Genehmigte Bot-Proposals werden idempotent auf dem cTrader-Demo-Account ausgefuehrt, mit vollem Execution-Status-Tracking.

### Story 8.1: cTrader-Client & Idempotente Order-Execution

As a Chef,
I want approved proposals to be executed on the cTrader demo account,
so that AI-recommended trades are placed automatically after my approval.

**Acceptance Criteria:**

**Given** ein genehmigtes Proposal
**When** die Execution getriggert wird
**Then** verbindet sich das System via OpenApiPy (Protobuf/SSL) mit dem cTrader-Demo-Account und platziert die Order (FR6)

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die trades-Tabelle per `ALTER TABLE trades ADD COLUMN agent_id TEXT` erweitert inklusive `idx_trades_agent_id` Index (schliesst Issue M1 der Readiness-Review; agent_id ist TEXT als Multi-Agent-Konzession aus dem MVP-Scope)

**Given** ein genehmigtes Proposal
**When** die Order gesendet wird
**Then** wird eine Client-Order-ID als Idempotenz-Schluessel verwendet; ein Retry nach Netzausfall erzeugt keine Doppel-Order (FR6, NFR-R3)

**Given** ein Netzwerkfehler bei der Order-Platzierung
**When** ein Retry ausgefuehrt wird
**Then** nutzt das System Exponential Backoff (1s Start, 60s Max, max 5 Retries) (NFR-I3)

**Given** die cTrader-API Rate-Limits
**When** ein 429-Fehler auftritt
**Then** wartet das System den Backoff ab und versucht erneut

### Story 8.2: Execution-Status-Tracking & Journal-Verknuepfung

As a Chef,
I want to see the execution status of every bot trade,
so that I know whether approved trades were successfully placed and filled.

**Acceptance Criteria:**

**Given** eine platzierte Bot-Order
**When** der Status sich aendert
**Then** wird der Execution-Status aktualisiert: submitted / filled / partial / rejected / cancelled (FR7)

**Given** eine ausgefuehrte (filled) Bot-Order
**When** der Trade in die trades-Tabelle geschrieben wird
**Then** wird die trigger_spec automatisch aus dem genehmigten Proposal befuellt (FR17)

**Given** einen Bot-Trade im Journal
**When** der Status-Indikator angezeigt wird
**Then** reflektiert er den aktuellen Execution-Status mit passendem status_badge (UX-DR77)

---

## Epic 9: Regime-Awareness & Kill-Switch

Das System erzeugt taegliche Regime-Snapshots und pausiert bei Crash-Regimen automatisch kurzfristige Strategien — mit manueller Override-Moeglichkeit und Audit-Trail.

### Story 9.1: Regime-Snapshot-Datenmodell & Taegliche Erfassung

As a Chef,
I want daily regime snapshots capturing market conditions,
so that I have a historical record of the market environment around my trades.

**Acceptance Criteria:**

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die `regime_snapshots`-Tabelle erstellt mit: id, fear_greed_index, vix, per_broker_pnl (JSONB), created_at (FR41)

**Given** der taegliche Scheduled Job
**When** ausgefuehrt
**Then** wird ein Regime-Snapshot erstellt mit aktuellem Fear & Greed Index, VIX-Level und Per-Broker-P&L (FR41)

**Given** der Snapshot-Job
**When** er ausfaellt (z.B. Datenquelle nicht erreichbar)
**Then** wird der Fehler geloggt und beim naechsten Durchlauf erneut versucht (kein Silent Failure)

### Story 9.2: Horizon-bewusster Kill-Switch

As a Chef,
I want automatic strategy pausing in crash regimes based on horizon,
so that short-term strategies are protected while long-term positions ride through volatility.

**Acceptance Criteria:**

**Given** Fear & Greed Index < 20
**When** der Kill-Switch evaluiert
**Then** werden alle Strategien mit Horizon in {intraday, swing<5d} automatisch auf "paused" gesetzt (FR42)

**Given** Fear & Greed Index < 20
**When** der Kill-Switch evaluiert
**Then** werden Strategien mit Horizon {swing>=5d, position} NICHT automatisch pausiert (FR43)

**Given** Fear & Greed Index >= 20 (wieder normal)
**When** der Kill-Switch re-evaluiert
**Then** werden zuvor automatisch pausierte Strategien wieder auf "active" gesetzt

### Story 9.3: Kill-Switch-Override & Regime-Seite

As a Chef,
I want to manually override the kill-switch and see current regime status,
so that I can make informed decisions about continuing to trade in volatile markets.

**Acceptance Criteria:**

**Given** eine automatisch pausierte Strategie
**When** Chef den Kill-Switch manuell ueberschreibt
**Then** wird die Strategie re-aktiviert und ein Audit-Log-Eintrag "manual override of kill-switch" erstellt (FR44)

**Given** die Regime-Seite (/regime)
**When** geladen
**Then** zeigt sie: aktueller F&G-Index, VIX-Level, Liste der durch Kill-Switch pausierten Strategien, Override-Historie (FR45, UX-DR75)

**Given** die Regime-Informationen
**When** im Footer des Approval-Viewports angezeigt
**Then** sind F&G, VIX und Kill-Switch-Status sichtbar als Kontext fuer Approval-Entscheidungen (UX-DR75)

---

## Epic 10: Gordon Trend-Radar

Chef bekommt jeden Montag den aktuellen Gordon-Trend-Radar mit Wochen-Diff und kann aus HOT-Picks direkt Strategie-Kandidaten erstellen.

### Story 10.1: Gordon-Weekly-Fetch & Snapshot-Speicherung

As a Chef,
I want weekly Gordon trend radar data fetched automatically,
so that I start each trading week with current market intelligence.

**Acceptance Criteria:**

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die `gordon_snapshots`-Tabelle erstellt mit: id, snapshot_data (JSONB), hot_picks (JSONB), created_at

**Given** Montag morgen (06:00 UTC)
**When** der Gordon-Weekly-Job laeuft
**Then** wird der aktuelle Trend-Radar via MCP (Gordon-Agent) abgerufen und als Snapshot gespeichert (FR46, NFR-I4)

**Given** der Gordon-Job
**When** der MCP-Call fehlschlaegt
**Then** wird der Fehler geloggt und eine Staleness-Warnung im UI angezeigt

### Story 10.2: Wochen-Diff & HOT-Picks-Anzeige

As a Chef,
I want to see what changed in the trend radar compared to last week,
so that I can quickly identify new opportunities and fading trends.

**Acceptance Criteria:**

**Given** aktuelle und vorherige Woche Snapshots existieren
**When** die Trends-Seite (/trends) geladen wird
**Then** zeigt sie: Hero-Block mit Weekly-Delta, F&G, VIX, Kill-Switch-Status, darunter HOT-Picks als kompakte Liste (FR47, UX-DR28)

**Given** die HOT-Picks-Liste
**When** angezeigt
**Then** sind Eintraege farblich kategorisiert: neu (gruen), weggefallen (rot), unveraendert (neutral) (FR47)

**Given** die Trends-Seite
**When** geladen
**Then** ist der initiale Scan in 2 Sekunden moeglich ohne Scrollen (UX-DR36)

### Story 10.3: Strategie-Kandidat aus HOT-Pick erstellen

As a Chef,
I want to create a strategy candidate directly from a Gordon HOT-pick,
so that I can quickly act on trend intelligence without manual data entry.

**Acceptance Criteria:**

**Given** einen Gordon-HOT-Pick in der Trends-Ansicht
**When** "Strategie erstellen" geklickt wird
**Then** oeffnet sich das Strategy-Formular mit vorausgefuelltem Symbol, Horizon und Trigger-Quelle (=Gordon) (FR48)

**Given** das vorausgefuellte Formular
**When** Chef die restlichen Felder vervollstaendigt und speichert
**Then** wird eine neue Strategie erstellt und verlinkt mit dem Gordon-Snapshot

---

## Epic 11: IB Quick-Order

Chef kann direkt aus ctrader Bracket-Orders (Limit + Trailing Stop-Loss) bei IB platzieren, mit Bestaetigungs-UI, Auto-Tagging und klarer Fehler-Unterscheidung (transient vs terminal).

### Story 11.1: Quick-Order-Formular & Validierung

As a Chef,
I want a quick order form to place IB stock orders with trailing stops,
so that I can trade directly from ctrader without switching to TWS.

**Acceptance Criteria:**

**Given** das Journal oder eine Watchlist
**When** Chef "Quick Order" waehlt
**Then** oeffnet sich ein Formular mit: Symbol (vorausgefuellt aus Kontext), Side (Buy/Sell), Quantity, Limit-Preis, Trailing-Stop-Amount (absolut $ oder prozentual) (FR53)

**Given** das Quick-Order-Formular
**When** inspiziert
**Then** hat es <= 6 Felder mit Auto-Focus, Tab-Navigation und Inline-Validierung auf Blur (UX-DR58, UX-DR59, UX-DR62)

**Given** ein ungueltige Eingabe (z.B. negativer Preis)
**When** das Feld den Fokus verliert
**Then** erscheint ein roter Rahmen + Fehlertext unterhalb (UX-DR59)

### Story 11.2: Bestaetigungs-UI & Bracket-Order-Submission

As a Chef,
I want a confirmation screen before order submission and atomic bracket order execution,
so that I can review all parameters and have automatic stop-loss protection from the start.

**Acceptance Criteria:**

**Given** ein ausgefuelltes Quick-Order-Formular
**When** "Weiter" geklickt wird
**Then** zeigt eine Bestaetigungs-Zusammenfassung: Symbol, Seite, Menge, Limit, Trailing-Stop-Betrag, berechnetes initiales Stop-Level, geschaetztes Risiko in $ — alles in einem Viewport ohne Scrollen (FR54, NFR-R3b)

**Given** die Bestaetigung
**When** der explizite Bestaetigungs-Klick erfolgt
**Then** sendet das System eine Bracket Order via ib_async: Parent (Limit) + Child (Trailing Stop-Loss), atomar (transmit=False auf Parent, transmit=True auf letzter Child) mit einer ctrader-generierten orderRef (FR55)

**Given** die Order
**When** gesendet
**Then** wird die orderRef als Idempotenz-Schluessel verwendet; ein Retry kann keine Duplikat-Order erzeugen (NFR-R3a)

**Given** keine Bestaetigung (One-Click)
**When** das Formular angezeigt wird
**Then** ist keine One-Click-Platzierung moeglich — der Bestaetigungs-Schritt ist verpflichtend (FR54)

### Story 11.3: Order-Status-Tracking & Auto-Tagging

As a Chef,
I want my quick orders to be automatically tracked and tagged in the journal,
so that I don't need to manually enter trade details after placing an order.

**Acceptance Criteria:**

**Given** eine platzierte Quick-Order
**When** der Status sich aendert
**Then** wird er im Journal aktualisiert: submitted / filled / partial / rejected / cancelled (FR56)

**Given** eine Quick-Order bei Platzierung
**When** der Trade im Journal erstellt wird
**Then** wird er automatisch mit Strategie, Trigger-Quelle und Horizon aus dem Quick-Order-Formular getaggt (auto-tagged, kein Post-hoc-Tagging noetig) (FR57)

### Story 11.4: Fehler-Handling — Transient vs Terminal

As a Chef,
I want clear distinction between retryable and fatal order errors,
so that I know when to wait and when to act.

**Acceptance Criteria:**

**Given** ein transienter Fehler (Netzausfall, TWS-Reconnect)
**When** die Order-Submission fehlschlaegt
**Then** wird automatisch ein Retry ausgefuehrt (max 3x, mit Exponential Backoff) (FR58)

**Given** ein terminaler Fehler (Margin-Fehler, ungueltiges Symbol, Markt geschlossen)
**When** die Order-Submission fehlschlaegt
**Then** sieht Chef eine klare Fehlermeldung als persistierender Error-Toast (rot, manuell zu schliessen) mit spezifischem Grund (FR58, UX-DR52)

**Given** einen transienten Fehler waehrend des Retry
**When** der Retry erfolgreich ist
**Then** wird ein Success-Toast angezeigt und der Order-Status normal weiterverfolgt

---

## Epic 12: System-Health & Scheduled Operations

Chef sieht den Systemzustand auf einen Blick (Broker-Status, MCP-Status, Job-Zeitstempel, Contract-Test, Backup-Status) und weiss, dass taegliche Backups und alle Scheduled Jobs zuverlaessig laufen.

### Story 12.1: Scheduled-Jobs-Framework & Ausfuehrungs-Logging

As a Chef,
I want all scheduled jobs to run reliably and log their execution,
so that I can trust that background processes are working correctly.

**Acceptance Criteria:**

**Given** die App startet mit neuer Migration
**When** migrate laeuft
**Then** wird die `job_executions`-Tabelle erstellt mit: id, job_name, status (success/failure), started_at, completed_at, error_message

**Given** die App laeuft im Single-Process-Modus
**When** APScheduler im FastAPI-Lifespan konfiguriert ist
**Then** sind folgende Jobs registriert: IB Flex Nightly, Regime-Snapshot (taeglich), Gordon-Weekly (Montag 06:00 UTC), MCP-Contract-Test (taeglich), DB-Backup (taeglich 04:00 UTC) (FR49, NFR-M6)

**Given** ein Scheduled Job laeuft
**When** er abgeschlossen ist (Erfolg oder Fehler)
**Then** wird ein job_executions-Eintrag mit Status und Zeitstempel geschrieben (FR49)

**Given** ein Job schlaegt fehl
**When** der Fehler geloggt wird
**Then** enthaelt der Log-Eintrag die error_message und der naechste planmaessige Lauf wird nicht blockiert

### Story 12.2: Health-Widget & System-Status-Anzeige

As a Chef,
I want a health dashboard showing system status at a glance,
so that I can quickly verify all integrations and background processes are working.

**Acceptance Criteria:**

**Given** die Settings-Seite oder den Health-Bereich
**When** geladen
**Then** zeigt das Health-Widget: IB-Verbindungsstatus (Dot: green/yellow/red), cTrader-Verbindungsstatus (Dot), MCP-Status (Dot), Zeitstempel der letzten erfolgreichen Ausfuehrung jedes Scheduled Jobs, aktuelles MCP-Contract-Test-Ergebnis (FR50, UX-DR79)

**Given** die Health-Status-Dots im Top-Bar
**When** mit Hover inspiziert
**Then** zeigt ein Tooltip "Statusname: Statusmeldung" (UX-DR79)

**Given** das Health-Widget
**When** aktualisiert
**Then** zeigt es Daten mit <= 5s Refresh-Latenz (NFR-M3)

**Given** die Settings-Seite
**When** geladen
**Then** zeigt sie ausserdem: Taxonomie-Editor, MCP-Konfigurations-Uebersicht, Audit-Log-Ansicht, DB-Backup-Download-Link (UX-DR80)

### Story 12.3: Taegliche PostgreSQL-Backups & Recovery

As a Chef,
I want daily database backups with documented recovery,
so that my trading data is protected against data loss.

**Acceptance Criteria:**

**Given** der taegliche Backup-Job (04:00 UTC)
**When** ausgefuehrt
**Then** wird ein PostgreSQL-Dump erstellt und im Backup-Verzeichnis gespeichert (FR52)

**Given** das neueste Backup
**When** inspiziert
**Then** ist es nicht aelter als 24 Stunden (NFR-R5)

**Given** das Health-Widget
**When** geladen
**Then** zeigt es den Zeitstempel des letzten erfolgreichen Backups sichtbar an (NFR-R5)

**Given** die Settings-Seite
**When** "Database Backup" geklickt wird
**Then** kann das aktuelle Backup heruntergeladen werden (UX-DR107)

**Given** die Recovery-Prozedur
**When** im Project-Knowledge dokumentiert
**Then** beschreibt sie Schritt-fuer-Schritt wie ein Backup wiederhergestellt wird (FR52)
