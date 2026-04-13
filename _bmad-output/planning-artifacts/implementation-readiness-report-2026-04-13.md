---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
workflowCompletedAt: '2026-04-13'
overallStatus: 'READY with Minor Warnings'
workflowStartedAt: '2026-04-13'
project_name: ctrader3
inputDocuments:
  prd: _bmad-output/planning-artifacts/prd.md
  architecture: _bmad-output/planning-artifacts/architecture.md
  epics: _bmad-output/planning-artifacts/epics.md
  ux: _bmad-output/planning-artifacts/ux-design-specification.md
  brief: _bmad-output/planning-artifacts/product-brief-ctrader.md
  briefDistillate: _bmad-output/planning-artifacts/product-brief-ctrader-distillate.md
priorReport: stale (entfernt am 2026-04-13)
prdRequirementCounts:
  functionalRequirements: 62
  nonFunctionalRequirements: 33
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-13
**Project:** ctrader3

## Document Inventory

### PRD
- **Whole:** `prd.md` (97 KB, aktualisiert 2026-04-13 — PostgreSQL-Cleanup + FR13c lightweight-charts + IB Quick-Order FR53–58 + asyncpg-Driver-Fix)
- **Sharded:** keine

### Architecture
- **Whole:** `architecture.md` (57 KB, aktualisiert 2026-04-13 — Decision #9 IB Quick-Order + stale DuckDB-Warnungen bereinigt + FR-Coverage 52→58 / 8→9 Areas)
- **Sharded:** keine

### Epics & Stories
- **Whole:** `epics.md` (93 KB, aktualisiert 2026-04-12)
- **Sharded:** keine
- **⚠️ Hinweis:** Wurde vor den PostgreSQL/lightweight-charts/Quick-Order-Änderungen erstellt — ist möglicherweise nicht mehr konsistent mit PRD und Architecture.

### UX Design Specification
- **Whole:** `ux-design-specification.md` (74 KB, aktualisiert 2026-04-12)
- **Sharded:** keine
- **⚠️ Hinweis:** Ebenfalls vor FR13c-Umstellung und Quick-Order-UI erstellt — muss gegengeprüft werden.

### Product Brief (Supporting)
- `product-brief-ctrader.md` (17 KB, v2, 2026-04-10)
- `product-brief-ctrader-distillate.md` (23 KB, 2026-04-10)

### Wireframes (Supporting, Excalidraw)
- `wireframe-journal-startseite.excalidraw.json` + `.png` (noch untracked)
- `wireframe-approval-viewport.excalidraw.json`
- `wireframe-strategy-review.excalidraw.json`
- `wireframe-trade-drilldown.excalidraw.json`

### Prior Readiness Report
- Entfernt am 2026-04-13 (war stale, vor PostgreSQL/Quick-Order-Änderungen erstellt).

## Critical Issues

**Keine Duplikate** (kein Dokument liegt gleichzeitig als whole + sharded vor).

**Keine fehlenden Pflicht-Dokumente** (PRD, Architecture, Epics, UX-Spec alle vorhanden).

**Potenzielle Konsistenz-Drifts für spätere Schritte:**
1. `epics.md` wurde am 2026-04-12 vor den großen PRD/Architecture-Änderungen erstellt — muss auf FR53–58, PostgreSQL-Impact und lightweight-charts-FR13c gegengeprüft werden.
2. `ux-design-specification.md` wurde ebenfalls am 2026-04-12 erstellt — muss auf Quick-Order-UI (FR53–58) und OHLC-Chart-Integration (FR13c) geprüft werden.
3. Der alte Readiness-Report wurde vom Chef entfernt.

## PRD Analysis

### Functional Requirements

Die PRD enthält **62 FRs** in **9 Capability-Areas + Power-User-UX**, organisiert wie folgt:

**1. Trade Data Ingestion** (FR1–FR7, 7 FRs)
- **FR1:** Historischer Import IB-Aktien-Trades über Flex Query.
- **FR2:** Historischer Import IB-Single-Leg-Options-Trades über Flex Query. Multi-Leg explizit Phase 2.
- **FR3:** Automatischer Live-Sync der IB-Executions ohne manuellen Anstoß.
- **FR4:** Duplikat-Erkennung bei wiederholtem Sync über eindeutige Broker-ID.
- **FR5:** Reconciliation Live-Sync vs. Flex-Nightly mit Flex als Source-of-Truth.
- **FR6:** Idempotente cTrader-Demo-Bot-Order-Ausführung.
- **FR7:** Execution-Status-Tracking für Bot-Trades (submitted/filled/partial/rejected/cancelled).

**2. Trade Journal & Drilldown** (FR8–FR13c, 9 FRs)
- **FR8:** Unified chronologische Trade-Liste (IB + cTrader).
- **FR9:** Drilldown mit P&L, Zeitstempel, Broker, Strategie, Trigger-Provenance, damaligem Fundamental-Kontext.
- **FR10:** Facettenfilter mit 8 Pflicht-Facetten (Asset-Class, Broker, Strategie, Trigger-Quelle, Horizon, Gefolgt-vs-Überstimmt, Confidence, Regime-Tag).
- **FR11:** Untagged-Trades-Widget auf Journal-Startseite mit Zähler.
- **FR12:** P&L-Anzeige inkl. Gebühren/Funding, Expectancy-at-Entry, R-Multiple (NULL bei fehlendem Stop, nie "0").
- **FR13:** Aggregation pro Facetten-Kombination (Count, Expectancy, Winrate, R-Verteilung).
- **FR13a:** MAE/MFE pro Trade in Preis- und Dollar-Einheiten, Basis Intraday-Candles.
- **FR13b:** P&L-Kalender-View (Monatsraster, klickbar).
- **FR13c:** Dynamischer OHLC-Chart mit Entry/Exit-Markern via lightweight-charts (ersetzt Screenshot-Upload).

**3. Taxonomy & Trigger-Provenance** (FR14–FR18b, 7 FRs)
- **FR14:** Taxonomie-Loading aus `taxonomy.yaml`.
- **FR15:** Post-hoc-Tagging (Strategie, Trigger-Typ, Horizon, Exit-Grund, Notizen).
- **FR16:** Strukturierte `trigger_spec` (JSONB) konform zum `fundamental/trigger-evaluator`-Schema.
- **FR17:** Automatisches Trigger-Spec-Füllen bei Bot-Trades / manuelles bei post-hoc.
- **FR18:** Lesbare Trigger-Spec-Darstellung (kein Raw-JSON im User-Facing-UI).
- **FR18a:** Orthogonale Mistakes-Facette (fomo, no-stop, revenge, etc.), mehrere Tags pro Trade möglich.
- **FR18b:** Top-N-Mistakes-Report nach Häufigkeit und $-Kosten, filterbar.

**4. Fundamental Intelligence Integration** (FR19–FR24, 6 FRs)
- **FR19:** MCP-Abfrage Viktor (Aktien) / Satoshi (Crypto) pro Asset.
- **FR20:** Side-by-Side damalige + aktuelle Fundamental-Einschätzung im Trade-Drilldown.
- **FR21:** Fundamental neben Agent-Vorschlag im Proposal-Drilldown.
- **FR22:** TTL-Cache mit Staleness-Anzeige pro Asset-Class.
- **FR23:** Klarer UI-Zustand bei MCP-Outages, keine Blockade anderer Views.
- **FR24:** Täglicher MCP-Contract-Test ohne Trade-Flow-Blockade.

**5. Bot Execution & Approval Pipeline** (FR25–FR32, 8 FRs)
- **FR25:** Approval-Dashboard mit Pending-Proposals (Agent, Strategie, Asset, Horizon, Position, Risk-Gate-Status).
- **FR26:** Single-Viewport-Proposal-Drilldown mit Agent-Vorschlag, Fundamental, Risk-Gate, Regime-Kontext.
- **FR27:** Automatisches Risk-Gate via Rita/Cassandra mit 3-stufigem Ergebnis (GREEN/YELLOW/RED).
- **FR28:** Technische RED-Blockade des Approval-Buttons, kein Workaround.
- **FR29:** Approval bei YELLOW/GREEN mit explizitem Risikobudget-Pflichtfeld.
- **FR30:** Proposal ablehnen oder zur Revision zurückschicken.
- **FR31:** Fundamental-Override bei YELLOW/GREEN mit `overrode_fundamental=true`-Flag.
- **FR32:** Unveränderlicher Audit-Log pro Approval mit vollständigem Snapshot.

**6. Strategy Management & Review** (FR33–FR40, 8 FRs)
- **FR33:** Strategy-Template mit Pflichtfeldern (Name, Asset-Class, Horizon, Holding-Period, Trigger-Quellen, Risikobudget).
- **FR34:** Strategy-Liste mit Aggregations-Metriken (Trade-Count, Expectancy, R-Verteilung, Drawdown, Status).
- **FR35:** Gruppierung nach Horizon, beliebige Sortierung.
- **FR36:** Strategy-Detail mit Expectancy-Kurve, Trade-Liste, Gefolgt-vs-Überstimmt-Breakdown.
- **FR37:** Freitext-Notizen mit Versionshistorie pro Strategie.
- **FR38:** Status-Lifecycle (active/paused/retired).
- **FR39:** Paused/Retired-Blockade im Bot-Execution-Pfad.
- **FR40:** Expectancy-Aggregationen pro Horizon über alle Strategien hinweg.

**7. Market Regime & Trend Awareness** (FR41–FR48, 8 FRs)
- **FR41:** Täglicher Regime-Snapshot (F&G + VIX + Per-Broker-P&L).
- **FR42:** Horizon-bewusster Kill-Switch bei F&G < 20 für Intraday/Short-Swing.
- **FR43:** Keine automatische Pause für Long-Horizon-Strategien.
- **FR44:** Manueller Kill-Switch-Override mit Audit-Log-Eintrag.
- **FR45:** Regime-Seite mit aktuellem Stand und pausierten Strategien.
- **FR46:** Wöchentlicher Gordon-Trend-Radar-Snapshot (Montag).
- **FR47:** Gordon-Diff zwischen Wochen, farblich kategorisiert (neu/weggefallen/unverändert).
- **FR48:** Strategie-Kandidat aus HOT-Pick mit vorausgefülltem Template.

**8. Operations, Health & Data Integrity** (FR49–FR52, 4 FRs)
- **FR49:** Scheduled Jobs (Flex Nightly, Regime, Gordon, Contract-Test, PG-Backup) mit Status-Logging.
- **FR50:** Health-Widget mit Broker-Status, MCP-Status, Job-Timestamps, Contract-Test-Ergebnis.
- **FR51:** Versionierte, idempotente PostgreSQL-Migrations in Transaktionen mit `schema_migrations`-Tracking.
- **FR52:** Tägliche `pg_dump`-Backups mit dokumentierter Recovery-Prozedur.

**9. IB Quick-Order (Aktien mit Trailing Stop-Loss)** (FR53–FR58, 6 FRs)
- **FR53:** Quick-Order aus Journal/Watchlist (Symbol, Side, Qty, Limit, Trailing-Stop-Amount absolut/prozentual).
- **FR54:** Bestätigungs-Zusammenfassung mit allen Parametern, expliziter Click-to-Confirm, keine One-Click-Platzierung.
- **FR55:** Bracket-Order-Submission via `ib_async` (Parent Limit + Child Trailing Stop, atomar mit transmit-Flags), `orderRef` als Idempotenz-Key.
- **FR56:** Order-Status-Tracking (submitted/filled/partial/rejected/cancelled) mit Journal-Aktualisierung.
- **FR57:** Auto-Tagging bei Quick-Order-Platzierung (Strategie, Trigger-Quelle, Horizon aus Formular), kein Post-hoc-Tagging.
- **FR58:** UI-Unterscheidung transient vs. terminal Errors, Auto-Retry mit Backoff bei transient (max 3×).

**Power-User-UX** (FR59–FR62, 4 FRs — nachträglich aus UX-Spec in PRD überführt am 2026-04-12)
- **FR59:** Command Palette (Ctrl+K) mit Fuzzy-Search über Views, Strategien, Trade-IDs, Query-Presets.
- **FR60:** CSV-Export der aktuellen Journal-Ansicht inkl. aktiver Filter.
- **FR61:** Benannte Query-Presets (z.B. "Satoshi Overrides Lost") über Command Palette abrufbar.
- **FR62:** Bookmarkbare URLs mit vollständigem Filter-State, Browser-Back als State-Management.

**FR-Zählung-Anmerkung:** Die PRD zählt "62 FRs" (FR1–FR52 + FR53–FR58 + FR59–FR62 = 52+6+4=62). Physikalisch vorhanden sind 67 nummerierte Items (wegen FR13a/b/c und FR18a/b als Sub-Items). Für Traceability verwende ich die PRD-eigene Zählung (62).

**Scope-Einschränkungen (bindend) für FR53–58:**
- Nur Aktien (Options-Order-Platzierung ist Phase 2)
- Kein nachträgliches Editieren von Order-Parametern aus ctrader (dafür TWS)
- Kein Take-Profit als dritte Bracket-Leg (Trailing Stop serverseitig bei IB)

### Non-Functional Requirements

Die PRD enthält **33 NFRs** in 5 Kategorien. Scalability, Accessibility, Internationalization und Compliance sind bewusst leer (Single-User, kein Bedarf).

**Performance (NFR-P1–P6, 6 NFRs)**
- **NFR-P1:** Journal-Startseite lädt vollständig in ≤ 1.5 s bei ≤ 2000 Trades.
- **NFR-P2:** Trade-Drilldown lädt in ≤ 3 s (Cache-Miss) / ≤ 500 ms (Cache-Hit).
- **NFR-P3:** Facettenfilter-Update in ≤ 500 ms bei ≤ 2000 Trades.
- **NFR-P4:** Aggregations-Anzeige in ≤ 800 ms bei ≤ 2000 Trades.
- **NFR-P5:** Approval-Dashboard + Proposal-Drilldown in ≤ 2 s (Cache-Miss, inkl. MCP-Calls).
- **NFR-P6:** Kognitives Kriterium — Trade-Drilldown in ≤ 3 Klicks, 3-Facetten-Query in ≤ 4 Klicks.

**Security & Privacy (NFR-S1–S5, 5 NFRs)**
- **NFR-S1:** API-Credentials ausschließlich in `.env` / Env-Vars, .gitignore-enforced.
- **NFR-S2:** FastAPI bindet nur an `127.0.0.1`, kein `0.0.0.0`.
- **NFR-S3:** Append-Only Audit-Log per DB-Constraint, testbar durch Negative-Test.
- **NFR-S4:** Keine Telemetrie, kein externes Error-Tracking im MVP.
- **NFR-S5:** PostgreSQL Least-Privilege DB-User, restriktive Filesystem-Permissions auf Backup-Verzeichnis.

**Reliability & Data Integrity (NFR-R1–R8 + R3a/R3b, 10 NFRs)**
- **NFR-R1:** Deterministische Duplikat-Erkennung via `permId`.
- **NFR-R2:** IB-Live-Sync übersteht TWS-Reconnects mit State-Recovery; Flex-Nightly als Source-of-Truth.
- **NFR-R3:** Idempotente Bot-Orders via Client-Order-ID, testbar durch Replay.
- **NFR-R3a:** Idempotente IB-Quick-Orders via `orderRef`, Replay-Test verpflichtend.
- **NFR-R3b:** Quick-Order-Bestätigungs-UI ohne Scrollen, alle Parameter in einem Viewport.
- **NFR-R4:** Täglicher MCP-Contract-Test, UI-Warnbanner binnen 24h bei Drift.
- **NFR-R5:** Tägliche `pg_dump`-Backups, Recovery mindestens einmal getestet.
- **NFR-R6:** Graceful Degradation bei MCP-Outage, Approval blockiert bei Risk-Gate-Timeout.
- **NFR-R7:** Migrations-Idempotenz testbar (zweimal angewandt = einmal).
- **NFR-R8:** Audit-Log-Vollständigkeit testbar durch Reproduzierbarkeits-Test.

**Integration & External Dependencies (NFR-I1–I6, 6 NFRs)**
- **NFR-I1:** MCP-Call-Timeout ≤ 10 s, kein Auto-Retry.
- **NFR-I2:** MCP-TTL-Cache (15 min Crypto, 1 h Aktien) mit Staleness-Anzeige.
- **NFR-I3:** Broker-API-Rate-Limit-Backoff (1 s → 60 s, max 5 Retries).
- **NFR-I4:** Gordon-Trend-Loop 8/8 Wochen erfolgreich.
- **NFR-I5:** MCP-Contract-Test PASS oder dokumentierte Drifts, kein silent fail.
- **NFR-I6:** Intraday-Candle-Datenquelle quellen-agnostisch, Timeout ≤ 15 s, 24h Cache-TTL, graceful null-Degradation.

**Maintainability & Operability (NFR-M1–M6, 6 NFRs)**
- **NFR-M1:** Code-Base lint-/format-clean unter `ruff`.
- **NFR-M2:** Unit-Tests für die 10 kritischsten Business-Logik-Pfade.
- **NFR-M3:** Health-Widget-Refresh-Latenz ≤ 5 s.
- **NFR-M4:** Strukturierte JSON-Logs, Rotation (100 MB × 5).
- **NFR-M5:** Migrations-History vollständig committet, keine Squash-Ops im MVP.
- **NFR-M6:** ctrader läuft als Single-Process (FastAPI + APScheduler).

### Additional Requirements (Constraints & Locked Decisions)

Zusätzlich zu FRs/NFRs stehen in der PRD folgende **bindende Constraints**:

**Technical Stack (Locked):**
- Python 3.12+ / `uv` Dependency-Manager
- FastAPI + HTMX + Tailwind (kein Node, kein React, kein eigener Build-Step)
- PostgreSQL als Storage (geändert von DuckDB am 2026-04-12)
- `asyncpg` als DB-Client (Binary-Protocol, eingebauter Pool)
- `lightweight-charts` für FR13c (lokal gehostetes JS-File, kein Node-Build)
- `ib_async` (nicht `ib_insync`) + Flex Queries für IB
- OpenApiPy (Protobuf) für cTrader
- `fundamental` MCP-Server als harte externe Dependency

**Domain-Constraints:**
- Single-User-Localhost, kein Multi-User, keine Compliance-Schicht
- Demo-Account only im MVP (cTrader)
- Nur Aktien für Quick-Order (Options Phase 2)
- Multi-Leg Options-Spreads Phase 2
- Trailing Stop serverseitig bei IB, kein lokales Monitoring

**Descope-Ladder (definiert vorab):**
- Stufe 1 (Woche 4): News/Trend-Integration raus, nur SFA/CFA-Fundamental
- Stufe 2 (Woche 5): cTrader Read-Only Spike
- Stufe 3 (Woche 6): Strategy Review auf statische Metriken
- Stufe 4 (Woche 7): Optionen komplett raus
- FR59–FR62 haben Descope-Priorität 1 (als erste rauscutbar)

**Terminal Kill-Kriterium:** Wenn Slice A (Journal + IB) Ende Woche 4 nicht vollständig benutzbar ist, wird ctrader als Projekt gestoppt.

### PRD Completeness Assessment

**Vollständigkeit: ✅ Hoch.** Die PRD ist umfassend dokumentiert mit:
- 62 FRs in 9 Capability-Areas + Power-User-UX, jede testbar und implementation-agnostic formuliert
- 33 NFRs mit konkreten messbaren Schwellwerten (Zeiten, Counts, Percentiles)
- 6 User-Journeys mit kritischen Momenten und Requirements-Mapping
- 4 Innovation-Claims mit Validation-Tests
- Domain-spezifische Constraints (Broker-APIs, MCP-Contract, Market-Data-Determinismus, Secrets, Ops)
- Vollständiger Technical Stack
- Explizite Scope-Grenzen (In-Scope / Out-of-Scope / Phase 2)
- Descope-Ladder + Terminal-Kill-Kriterium als Governance-Mechanismen
- Risk-Watch-Liste (9 priorisierte Einträge)

**Klarheit: ✅ Hoch.** Jede FR ist eindeutig formuliert, Wiederholungen vermieden, Querverweise auf Abhängigkeiten präsent (z.B. FR24 ↔ NFR-R4, FR51 ↔ NFR-R7, FR13a ↔ NFR-I6).

**Traceability: ✅ Gut.** FRs sind nummeriert und in Capability-Areas gruppiert. Journey-Requirements-Summary-Tabelle mappt Journeys auf Capability-Cluster. Innovation-Claims referenzieren konkrete FRs.

**Potenzielle Lücken / Findings für spätere Steps:**

1. **FR59–FR62 wurden nachträglich ergänzt** (am 2026-04-12 aus der UX-Spec in die PRD überführt). Die Architecture.md (heute auf FR53–FR58 aktualisiert) berücksichtigt FR59–FR62 nicht explizit. → **Step 3 (Architecture-Analyse)**.

2. **FR-Zählung-Inkonsistenz:** PRD sagt selbst "62 FRs", physikalisch sind es 67 (wegen FR13a/b/c und FR18a/b). Nicht dramatisch, aber für die Architecture-Coverage-Tabelle ist die PRD-Zählung maßgeblich.

3. **IB Quick-Order in Journey-Liste:** Journey 6 (Quick-Order mit Trailing Stop-Loss) wurde in die PRD aufgenommen — muss mit der Journey Requirements Summary konsistent sein. Schneller Check in Step 3.

4. **Audit-Log-Scope:** FR32 schreibt den Audit-Log nur für Bot-Approvals vor. Quick-Orders (FR53–FR58) erzeugen **keinen** Audit-Log-Eintrag. Das ist konsistent (Quick-Orders sind manuelle Entscheidungen), aber sollte in Step 3 gegen die Architecture-Entscheidungen gecheckt werden.

5. **Kill-Switch-Exemption für Quick-Orders:** Die PRD formuliert FR42/FR43 (Kill-Switch) und FR53–58 (Quick-Order) als zwei unabhängige Bereiche. Die explizite Exemption-Aussage ("Quick-Orders sind NICHT vom Kill-Switch betroffen") steht nur in der Architecture.md (Decision #9), nicht in der PRD selbst. → **Kleiner Drift**, in Step 3 zu flaggen und eventuell in PRD nachdokumentieren.

Kein Show-Stopper für IR. Alle FRs und NFRs sind extrahiert und bereit für die Traceability-Prüfung gegen Epics (Step 3) und UX-Spec (Step 4).

## Epic Coverage Validation

### Epic List (12 Epics)

| Epic | Titel | FRs |
|---|---|---|
| **Epic 1** | Projekt-Bootstrap & Design-System | FR14, FR51 |
| **Epic 2** | Trade-Journal & IB-Import | FR1, FR2, FR3, FR4, FR5, FR8, FR9, FR11, FR12 |
| **Epic 3** | Trade-Tagging & Trigger-Provenance | FR15, FR16, FR17, FR18, FR18a, FR18b |
| **Epic 4** | Journal-Intelligence (Facetten, Aggregation, Chart) | FR10, FR13, FR13a, FR13b, FR13c, **FR59, FR60, FR61, FR62** |
| **Epic 5** | Fundamental-Integration (MCP-Layer) | FR19, FR20, FR22, FR23, FR24 |
| **Epic 6** | Strategy-Management | FR33, FR34, FR35, FR36, FR37, FR38, FR39, FR40 |
| **Epic 7** | Approval-Pipeline & Risk-Gate | FR21, FR25, FR26, FR27, FR28, FR29, FR30, FR31, FR32 |
| **Epic 8** | Bot-Execution (cTrader) | FR6, FR7 |
| **Epic 9** | Regime-Awareness & Kill-Switch | FR41, FR42, FR43, FR44, FR45 |
| **Epic 10** | Gordon Trend-Radar | FR46, FR47, FR48 |
| **Epic 11** | **IB Quick-Order** | **FR53, FR54, FR55, FR56, FR57, FR58** |
| **Epic 12** | System-Health & Scheduled Operations | FR49, FR50, FR52 |

### Coverage Matrix

| FR | Epic | Status |
|---|---|---|
| FR1–FR5 | Epic 2 | ✅ Covered |
| FR6, FR7 | Epic 8 | ✅ Covered |
| FR8, FR9, FR11, FR12 | Epic 2 | ✅ Covered |
| FR10, FR13, FR13a, FR13b, FR13c | Epic 4 | ✅ Covered (FR13c als OHLC-Chart via lightweight-charts, Story 4.5) |
| FR14 | Epic 1 | ✅ Covered |
| FR15, FR16, FR17, FR18, FR18a, FR18b | Epic 3 | ✅ Covered |
| FR19, FR20, FR22, FR23, FR24 | Epic 5 | ✅ Covered |
| FR21 | Epic 7 | ✅ Covered |
| FR25–FR32 | Epic 7 | ✅ Covered |
| FR33–FR40 | Epic 6 | ✅ Covered |
| FR41–FR45 | Epic 9 | ✅ Covered |
| FR46, FR47, FR48 | Epic 10 | ✅ Covered |
| FR49, FR50, FR52 | Epic 12 | ✅ Covered |
| FR51 | Epic 1 | ✅ Covered |
| **FR53–FR58** | **Epic 11** | **✅ Covered (Stories 11.1–11.4)** |
| **FR59** | **Epic 4 Story 4.6** | **✅ Covered (Command Palette)** |
| **FR60** | **Epic 4 Story 4.7** | **✅ Covered (CSV-Export)** |
| **FR61** | **Epic 4 Story 4.7** | **✅ Covered (Query-Presets)** |
| **FR62** | **Epic 4 Story 4.1** | **✅ Covered (bookmarkbare URLs via hx-push-url)** |

### Missing Requirements

**Keine.** Alle 62 FRs aus der PRD sind in den Epics abgedeckt. Die Coverage ist **vollständig**.

### Coverage Statistics

- **Total PRD FRs:** 62 (PRD-Zählung FR1–FR52 + FR53–FR58 + FR59–FR62)
- **FRs covered in epics:** 62
- **Coverage percentage:** **100% ✅**
- **Uncovered FRs:** 0
- **Extra FRs in epics (nicht in PRD):** 0

### Positive Findings

1. **Epic 11 (IB Quick-Order) ist vollständig spezifiziert** mit 4 Stories:
   - Story 11.1: Quick-Order-Formular & Validierung (FR53)
   - Story 11.2: Bestätigungs-UI & Bracket-Order-Submission (FR54, FR55, NFR-R3b)
   - Story 11.3: Order-Status-Tracking & Auto-Tagging (FR56, FR57)
   - Story 11.4: Fehler-Handling — Transient vs Terminal (FR58, UX-DR52)

2. **FR13c ist in epics.md korrekt als lightweight-charts-OHLC-Chart umgesetzt** (Story 4.5: "Interaktiver OHLC-Chart mit lightweight-charts"). Der Screenshot-Upload-Ansatz ist vollständig abgelöst.

3. **FR51/FR52 sind in epics.md schon auf PostgreSQL umgestellt** (Story 1.1 spezifiziert explizit "asyncpg Pool min=2, max=10"). Der Content der epics.md ist aktueller als das mtime-Datum suggeriert.

4. **NFR-R3a und NFR-R3b (IB-Quick-Order-Idempotenz + Viewport-Regel) sind in epics.md als separate NFRs dokumentiert** und in Story 11.2 referenziert.

5. **FR59–FR62 (Power-User-UX) sind konkret gemappt** — jede FR hat eine konkrete Story-Referenz in Epic 4.

### Minor Drifts (nicht blockend, aber für Cleanup markieren)

1. **UX-DR107 (epics.md Zeile 455):** Formulierung "DuckDB-Export als downloadbares Backup in Settings" ist stale. Der Content ist noch valide (DB-Export/Backup-Feature), aber die Begrifflichkeit sollte auf "PostgreSQL-Dump" oder neutral "DB-Backup" aktualisiert werden. **Not blocking.**

2. **UX-DR109 (epics.md Zeile 459):** Listet "Trade-Screenshots-Integration" als Out-of-Scope. Das ist seit der FR13c-Umstellung auf lightweight-charts obsolet — Screenshots wurden durch dynamische OHLC-Charts ersetzt. Die UX-DR-Aussage ist technisch noch korrekt (Screenshots sind nicht im MVP), aber die Formulierung ist irreführend. **Not blocking.**

3. **Coverage-Map PRD-Zählung:** Die FR-Coverage-Map in epics.md (Zeilen 468–535) listet alle 62 FRs korrekt, aber es gibt keine explizite Summen-Bemerkung ("62 FRs in 12 Epics"). Das ist eine kosmetische Lücke.

**Fazit Epic Coverage:** ✅ **Ready for Implementation.** Keine blockierenden Gaps. Die zwei Minor-Drifts sind für einen Cleanup-Commit optional, aber der Sprint kann ohne Fix starten.

## UX Alignment Assessment

### UX Document Status

✅ **Gefunden:** `ux-design-specification.md` (74 KB, 14-Step-Workflow vollständig, `workflowCompletedAt: 2026-04-12`).

Die UX-Spec deckt ab:
- Executive Summary mit 5 Nutzungs-Modi (entsprechend Journeys J1–J5)
- Design Challenges, Opportunities, Emotional Response
- Design System Foundation (Handroll, Dark Cockpit)
- **13 Components als Jinja2-Makros** (Tier 1–3 mit Implementation-Roadmap)
- 5 User Journey Flows (J1–J5)
- UX Consistency Patterns (Button-Hierarchie, Feedback, Forms, Navigation, Search, Inline-Expansion, Data-Display, Keyboard-Shortcuts)
- Responsive Design & Accessibility

### UX ↔ PRD Alignment

**Gut abgedeckt:**
- FR10 (Facettenfilter) → umfangreich in Design Challenges, Pattern, Journey 4 detailliert
- FR9 (Trade-Drilldown) → Inline-Expansion-Pattern
- FR26 (Proposal-Viewport) → eigener Component `proposal_viewport(...)` mit Detail-Spec
- FR18 (Trigger-Provenance lesbar) → `trigger_spec_readable(...)` Component
- FR13b (P&L-Kalender) → `calendar_cell(...)` Component
- FR25–FR32 (Approval-Pipeline) → Journey 2 komplett ausgearbeitet
- FR15 (Post-hoc-Tagging) → Journey 1
- FR46–FR48 (Gordon-Diff) → Journey 5

**Echte UX-Drifts gegenüber PRD:**

| # | Drift | Betroffene FRs | Schwere |
|---|---|---|---|
| 1 | **Journey 6 (Quick-Order) fehlt vollständig.** Die UX-Spec kennt nur J1–J5. | FR53–FR58 | ⚠ **Medium** |
| 2 | **Keine Components `quick_order_form` / `quick_order_preview` im Component-Inventar.** Tier-1/2/3 zählen 13 Components, keiner davon ist für Quick-Order. | FR53, FR54 | ⚠ **Medium** |
| 3 | **Kein expliziter OHLC-Chart-Component für FR13c.** `lightweight-charts` taucht in Zeile 259 nur als Sparkline-Option auf, nicht als dedizierter OHLC-Chart mit Entry/Exit-Markern. Die Implementation-Roadmap hat kein Chart-Component. | FR13c | ⚠ **Medium** |
| 4 | **Screenshot-Accessibility-Regel obsolet.** Zeile 689: "Alt-Texte für funktionale Bilder (Screenshots in Trade-Drilldowns)" — FR13c wurde am 2026-04-13 von Screenshot-Upload auf dynamische OHLC-Charts umgestellt, es gibt keine Screenshots mehr. | FR13c | ⚪ Minor |
| 5 | **DuckDB-Referenzen in UX-Pattern-Begründungen.** Zeile 269: "DuckDB-Datei ist extern lesbar (mit DuckDB-CLI...)". Zeile 304: "...als DuckDB-Datei + Export-Buttons...". | FR51, FR52, NFR-S5 | ⚪ Minor |

### UX ↔ Architecture Alignment

**Architecture hat alle UX-Drifts antizipiert:**

Die Architecture.md (Decision #9 IB Quick-Order, erstellt am 2026-04-13) spezifiziert bereits explizit:
- `templates/components/quick_order_form.html` (FR53)
- `templates/components/quick_order_preview.html` (FR54)
- `templates/components/trade_chart.html` (FR13c mit lightweight-charts)
- `app/static/js/lightweight-charts.standalone.production.js` (lokal gehostet)
- `POST /trades/quick-order`, `GET /trades/quick-order/form`, `POST /trades/quick-order/preview` als HTMX-Endpoints

**Das heißt:** Architecture ist vollständig, Epics sind vollständig, aber UX-Spec ist das schwächste Glied.

### Warnings

**W1 — UX-Spec ist unvollständig gegenüber FR53–FR58 (Quick-Order).** Die Component-Spezifikation und Journey 6 fehlen. **Impact auf Implementation:** Epic 11 Stories (11.1–11.4) enthalten ausreichend Detail, damit die Implementation starten kann — die UX-Spec ist nicht strikt blockierend, aber der UX-Style-Guide-Charakter der Spec fehlt für die Quick-Order-Komponenten. Risiko: Inkonsistenter Look zwischen Quick-Order-UI und dem Rest der App.

**W2 — UX-Spec ist unvollständig gegenüber FR13c (OHLC-Chart).** Obwohl lightweight-charts einmal erwähnt wird, fehlt ein dediziertes `trade_chart`-Component-Design. **Impact auf Implementation:** Story 4.5 muss diese Lücke selbst schließen. Risiko: keine konsistenten Design-Tokens für Chart-Farben (Gain/Loss/Marker), keine Entry/Exit-Marker-Spezifikation.

**W3 — UX-Spec hat 3 stale Referenzen auf DuckDB/Screenshots.** Nicht blockierend, aber für Traceability sollten diese bei der nächsten UX-Spec-Iteration gepatcht werden.

### Empfehlung

**Nicht-blockierende UX-Spec-Ergänzungen vor Sprint-Start (niedrig-Aufwand, hoch-Wert):**

1. **Quick-Order-Components zum Tier-2-Inventar hinzufügen:**
   - `quick_order_form(context)` — Inline-Form aus Journal/Watchlist, Tier 2 (Woche 3)
   - `quick_order_preview(order_spec)` — Bestätigungs-Zusammenfassung mit allen Parametern in einem Viewport (NFR-R3b)
2. **Journey 6 "IB Quick-Order" zur Journey-Liste hinzufügen** mit Klick-Budget und kritischem Element (Bestätigungs-UI muss alle Zahlen ohne Scrollen zeigen).
3. **`trade_chart(candles, markers)` Component zum Tier-2-Inventar hinzufügen** (Woche 3) für FR13c mit spezifizierten Marker-Styles (grün/rot) und Design-Token-Bindung.
4. **Stale DuckDB/Screenshot-Referenzen patchen** (Zeilen 259/269/304/689).

**Aufwand:** ~30–60 Minuten für den UX-Spec-Patch. **Wert:** Style-Konsistenz und vollständige Traceability.

**Alternative:** UX-Spec kann als "Tier-3-Drift-akzeptiert" markiert werden und im Implementation-Flow (Story 11.1, Story 4.5) treffen die Entwickler eigene UX-Entscheidungen, die dann post-hoc in die UX-Spec zurückfließen. **Das ist pragmatisch, aber weniger sauber.**

**Fazit UX Alignment:** ⚠ **Ready with Warnings.** Die UX-Spec-Drifts sind **nicht blockierend für Sprint-Start**, weil Epics und Architecture die Details tragen. Aber für einen sauberen Zustand vor Epic 11 und Story 4.5 empfiehlt sich ein UX-Spec-Patch.

## Epic Quality Review

**Standard:** `create-epics-and-stories`-Best-Practices (User-Value-Fokus, Epic-Independence, keine Forward-Dependencies, saubere Story-Sizing, vollständige Acceptance Criteria in Given/When/Then-Format).

**Scope der Review:** 12 Epics, ~50 Stories (stichprobenartig geprüft).

### A) User-Value-Fokus pro Epic

| Epic | Titel | User-Value-Check | Bewertung |
|---|---|---|---|
| **Epic 1** | Projekt-Bootstrap & Design-System | "Chef hat eine laufende Anwendung mit ... navigierbarer Seitenstruktur" | ✅ **Borderline OK** — ist Bootstrap, aber formuliert als "Chef sieht etwas", enthält Design-Tokens + Top-Bar + Seiten-Shells. Für Greenfield akzeptabel. |
| **Epic 2** | Trade-Journal & IB-Import | Chef kann Trades importieren und durchblättern | ✅ **Stark** |
| **Epic 3** | Trade-Tagging & Trigger-Provenance | Chef kann Trades taggen und Provenance lesbar sehen | ✅ **Stark** |
| **Epic 4** | Journal-Intelligence | Chef kann Fragen stellen und visuelle Antworten bekommen | ✅ **Stark** |
| **Epic 5** | Fundamental-Integration (MCP) | Chef sieht Viktor/Satoshi im Drilldown | ✅ **Stark** |
| **Epic 6** | Strategy-Management | Chef kann Strategien definieren und Performance verfolgen | ✅ **Stark** |
| **Epic 7** | Approval-Pipeline & Risk-Gate | Chef kann Bot-Proposals sicher genehmigen | ✅ **Stark** |
| **Epic 8** | Bot-Execution (cTrader) | Genehmigte Proposals werden ausgeführt | ✅ **OK** (nur 2 Stories, aber klarer Wert) |
| **Epic 9** | Regime-Awareness & Kill-Switch | System schützt Chef vor Crash-Regimen | ✅ **Stark** |
| **Epic 10** | Gordon Trend-Radar | Chef bekommt Montag den Trend-Radar | ✅ **Stark** |
| **Epic 11** | **IB Quick-Order** | Chef kann direkt aus ctrader IB-Orders platzieren | ✅ **Stark** |
| **Epic 12** | System-Health & Scheduled Operations | Chef sieht System-Gesundheit auf einen Blick | ✅ **OK** — leichte Operations-Tendenz, aber Health-Widget liefert User-Value ("kann ich arbeiten oder hängt was?") |

**Fazit A:** ✅ **Alle 12 Epics bestehen den User-Value-Test.** Kein Epic ist ein reiner technischer Milestone. Epic 1 und Epic 12 sind grenzwertig, aber vertretbar.

### B) Epic Independence Check

**Erwartete Abhängigkeitskette** (jeder Epic kann Output früherer Epics nutzen, aber nicht später Epics erfordern):

```
Epic 1 (Bootstrap) ──────┐
                         ├─► Epic 2 (Journal & Import)
                         │   └─► Epic 3 (Tagging) ──► Epic 4 (Intelligence)
                         │       └─► Epic 5 (Fundamental) ──► Epic 7 (Approval)
                         │                                    └─► Epic 8 (cTrader Execution)
                         │       └─► Epic 6 (Strategy) ──┬────┘
                         │                              ├─► Epic 9 (Regime/Kill-Switch)
                         │                              └─► Epic 10 (Gordon)
                         │
                         ├─► Epic 11 (Quick-Order — braucht Journal-Kontext aus Epic 2)
                         │
                         └─► Epic 12 (Health — kann parallel laufen)
```

**Verifiziert durch Stichproben:**
- ✅ Story 8.1 nutzt nur Proposal-Datenmodell aus Epic 7 (vorheriger Epic) — keine Forward-Dependency
- ✅ Story 4.5 (OHLC-Chart) nutzt Trade-Drilldown aus Epic 2 — vorheriger Epic
- ✅ Story 11.1 (Quick-Order-Formular) nutzt Journal/Watchlist-Kontext aus Epic 2 — vorheriger Epic, **keine Abhängigkeit von Epic 12**
- ✅ Story 9.2 (Kill-Switch) nutzt Strategy-Status aus Epic 6 — vorheriger Epic

**Keine Forward-Dependencies gefunden.** Die Epic-Reihenfolge ist sauber aufsteigend.

**Fazit B:** ✅ **Alle 12 Epics sind unabhängig im Sinne der Best Practices.** Die Dependency-Kette ist natürlich: späte Epics bauen auf frühen Epics, aber nie umgekehrt.

### C) Story Quality Assessment (Stichproben)

**Geprüfte Stories:** Story 1.1, 2.1, 2.4, 3.1, 4.1, 4.5, 4.6, 4.7, 7.2, 8.1, 8.2, 11.1, 11.2, 11.3, 11.4, 12.3.

**C.1 Acceptance Criteria Format:**
- ✅ **Alle** geprüften Stories verwenden das **Given/When/Then**-BDD-Format
- ✅ Jedes AC referenziert konkrete FR-Nummern (z.B. "(FR55)", "(FR57)", "(NFR-R3b)")
- ✅ Erfolgspfade und Fehlerpfade sind separat gelistet (z.B. Story 11.4: transient vs terminal)
- ✅ UX-DR-Referenzen sind present (z.B. "(UX-DR77)", "(UX-DR52)")

**C.2 Story Sizing:**
- ✅ Stories sind **klein genug** für "1 Tag bis 3 Tage Aufwand" — z.B. Story 11.1 ist "Quick-Order-Formular & Validierung", nicht "Komplettes IB-Order-Module"
- ✅ Keine Story ist Epic-groß
- ✅ Story-Titel sind user-centric formuliert

**C.3 Independence:**
- ✅ Story 2.3 (Journal-Startseite) kann **unabhängig** von Story 2.4 (Drilldown) getestet werden
- ✅ Story 4.5 (Chart) kann unabhängig von Story 4.3 (MAE/MFE) laufen — gleiche Datenquelle, aber separate Features
- ⚠ **Minor:** Story 8.1 (cTrader-Client) enthält das inline-ALTER-TABLE für `agent_id` (Zeile 1544): *"Given die App startet mit neuer Migration ... Then wird die trades-Tabelle per ALTER TABLE trades ADD COLUMN agent_id erweitert"*. Das ist technisch ein Schema-Change, der **im selben Story-Commit** passiert. Begründung im Story: "schließt Issue M1 der Readiness-Review". **Akzeptabel**, da die Migration idempotent ist und logisch zu Epic 8 gehört (agent_id wird erst im Bot-Execution-Kontext sinnvoll benötigt). Minor-Style-Concern: könnte sauberer in einer separaten Migration-Story in Epic 1 oder als Story 8.0 adressiert werden.

**C.4 Database Creation Timing:**
- ✅ Story 1.2 erstellt das **Migrations-Framework**, nicht alle Tabellen upfront
- ✅ Story 2.1 erstellt das Trade-Datenmodell (wenn Trades importiert werden)
- ✅ Story 6.1 erstellt das Strategy-Datenmodell (wenn Strategien definiert werden)
- ✅ Story 7.1 erstellt das Proposal-Datenmodell (wenn Proposals verwaltet werden)
- ✅ Story 9.1 erstellt das Regime-Snapshot-Datenmodell (wenn Snapshots erfasst werden)
- ✅ Story 11.x nutzt die Migration 005 (`quick_order_columns`) — die wird in Story 11.x oder als Teil von Epic 1 Migration-Runner ausgeführt

**C.5 Special Checks (Greenfield):**
- ✅ Architecture sagt "Bootstrap from Scratch" → kein Starter-Template-Zwang
- ✅ Story 1.1 ist ein korrekt formuliertes Greenfield-Setup (FastAPI + Docker Compose + PostgreSQL)
- ✅ Story 1.4 (Design-System/Tailwind) ist früh dran — vor Journal-Views
- ✅ Story 12.1 (Scheduled-Jobs-Framework) ist in Epic 12, das parallel laufen kann

### D) Findings by Severity

#### 🔴 Critical Violations
**Keine.**

#### 🟠 Major Issues
**Keine.**

#### 🟡 Minor Concerns
1. **Story 8.1 inline ALTER TABLE:** Der Schema-Change für `agent_id` liegt mitten in Story 8.1 statt in einer dedizierten Migration-Story. Technisch korrekt (idempotent, logisch mit cTrader-Context verknüpft), aber stilistisch könnte es sauberer sein.  
   **Empfehlung:** Als-is akzeptabel, nicht blockierend.

2. **Epic 8 hat nur 2 Stories:** Das ist die kleinste Epic in der Liste. Könnte als Sub-Area von Epic 7 gesehen werden. Wegen klarer Broker-API-Domain-Trennung (cTrader vs. Approval-UI) aber vertretbar.  
   **Empfehlung:** Als-is lassen.

3. **Epic 12 hat leichte Operations-Tendenz:** Health-Widget liefert User-Value, aber Story 12.3 (PostgreSQL-Backups) ist eher Infra.  
   **Empfehlung:** Als-is lassen — User-Value ist "Chef weiß, dass Backups laufen".

### E) Best Practices Compliance Checklist

Pro Epic verifiziert:

| Check | Status |
|---|---|
| Epic delivers user value | ✅ 12/12 |
| Epic can function independently | ✅ 12/12 (natürliche Abhängigkeitskette, keine Forward-Dependencies) |
| Stories appropriately sized | ✅ Stichproben bestanden, keine Epic-großen Stories |
| No forward dependencies | ✅ Keine in Stichproben gefunden |
| Database tables created when needed | ✅ Inkrementelle Schema-Evolution pro Epic |
| Clear acceptance criteria | ✅ Given/When/Then durchgängig |
| Traceability to FRs maintained | ✅ AC-Zeilen referenzieren FR-Nummern explizit |

**Fazit Epic Quality:** ✅ **Ready for Implementation.** Die Epics sind hochwertig strukturiert. Stichproben-basierte Prüfung hat keine kritischen oder größeren Verstöße gefunden. Die drei Minor-Concerns sind vertretbar.

## Summary and Recommendations

### Overall Readiness Status

**✅ READY with Minor Warnings**

ctrader ist **bereit für Sprint-Start**. Alle vier Planungs-Dokumente (PRD, Architecture, Epics, UX-Spec) sind vorhanden, die 62 FRs sind zu 100% in den 12 Epics abgedeckt, die Epic-Qualität ist hoch, und es gibt keine blockierenden Inkonsistenzen. Die wenigen identifizierten Drifts liegen in der UX-Spec (W1–W3) und sind **nicht blockierend**, weil Epics und Architecture die Details tragen.

### Document Alignment Matrix

| Dimension | PRD | Architecture | Epics | UX-Spec |
|---|---|---|---|---|
| **FR-Coverage** | 62 FRs dokumentiert | **nennt 58 FRs** ⚠ stale | 62 FRs abgedeckt ✅ | kennt FR53–58 nicht ⚠ |
| **PostgreSQL** | ✅ konsistent | ✅ konsistent | ✅ konsistent | 3 Stellen stale (DuckDB) ⚠ |
| **asyncpg** | ✅ konsistent | ✅ konsistent | ✅ konsistent | n/a |
| **lightweight-charts** | ✅ FR13c umgestellt | ✅ Decision #8 | ✅ Story 4.5 | 1 Erwähnung (nur Sparkline) ⚠ |
| **IB Quick-Order** | ✅ FR53–58 | ✅ Decision #9 | ✅ Epic 11 (4 Stories) | ❌ fehlt komplett |
| **Kill-Switch-Exemption für Quick-Order** | ⚠ nur implizit | ✅ explizit in Decision #9 | (vererbt) | n/a |

### Critical Issues Requiring Immediate Action

**Keine.** Alle identifizierten Issues sind Minor oder Style-Concerns, nicht blockierend.

### Non-Critical Findings (prioritized)

**P1 — Architecture-Drift bei FR-Count (fast-Fix):**
- Architecture.md sagt "58 FRs in 9 Capability-Areas", ist aber seit FR59–62 (Power-User-UX) nicht aktualisiert.
- **Impact:** Kosmetisch, keine Implementation-Blockade.
- **Empfehlung:** Beim nächsten Architecture-Touch die FR-Zählung auf 62/10 Areas anheben (Power-User-UX als 10. Area).

**P2 — UX-Spec-Drifts (medium-Aufwand, hoch-Wert):**
- W1: Journey 6 (Quick-Order) fehlt in der UX-Spec
- W2: Components `quick_order_form`, `quick_order_preview`, `trade_chart` fehlen im Tier-2-Inventar
- W3: 3 stale DuckDB-Referenzen (Zeilen 259/269/304) + Screenshot-Accessibility-Regel (Zeile 689)
- **Impact:** Style-Konsistenz-Risiko. Epic 11 und Story 4.5 können trotzdem implementiert werden, weil Epics genug Detail tragen.
- **Empfehlung:** Ein UX-Spec-Patch vor Epic 11-Start ist niedrig-Aufwand (~30–60 min) und schließt die Traceability-Lücke.

**P3 — Kill-Switch-Exemption in PRD nachdokumentieren (low-Aufwand):**
- Die PRD formuliert FR42/FR43 (Kill-Switch) und FR53–58 (Quick-Order) als unabhängige Bereiche, ohne explizit zu sagen "Kill-Switch greift nicht bei Quick-Orders". Diese Aussage steht nur in Architecture Decision #9.
- **Impact:** Niemand liest die Architecture beim Verstehen der FRs.
- **Empfehlung:** Kurzer PRD-Satz in FR42 oder FR53 ("Manuelle Quick-Orders sind vom Kill-Switch exempt").

**P4 — Minor stale Referenzen in epics.md:**
- UX-DR107 (Zeile 455): "DuckDB-Export als downloadbares Backup"
- UX-DR109 (Zeile 459): "Trade-Screenshots-Integration" als NICHT im MVP
- **Impact:** Niedrig, historische Artefakte.
- **Empfehlung:** Bei nächstem Epic-Touch patchen.

**P5 — Story 8.1 inline ALTER TABLE (Style-Concern):**
- Inline-Schema-Change im Story statt dedizierter Migration-Story.
- **Impact:** Vertretbar, nicht blockierend.
- **Empfehlung:** Als-is akzeptieren.

### Recommended Next Steps

**Option A — Clean Slate vor Sprint-Start (empfohlen, ~1-2 Stunden):**
1. **P1 Architecture-FR-Count-Fix** (5 min): `architecture.md` — "58 FRs" → "62 FRs", "9 Capability-Areas" → "10 Capability-Areas", FR-Coverage-Table-Zeile für FR59–62 ergänzen.
2. **P3 PRD Kill-Switch-Exemption-Satz** (10 min): In FR42 oder FR53 einen expliziten Satz zur Exemption ergänzen.
3. **P2 UX-Spec-Patch** (30–60 min): Journey 6 + 3 neue Components (`quick_order_form`, `quick_order_preview`, `trade_chart`) + stale DuckDB/Screenshot-Referenzen patchen.
4. **P4 epics.md UX-DR107/109 Cleanup** (5 min): DuckDB → PostgreSQL, Screenshots-Hinweis aktualisieren.
5. Commit + Push als "docs: Post-IR-Cleanup — Traceability und Konsistenz".
6. **Dann Sprint-Start** mit sauberer Baseline.

**Option B — Direkt mit Sprint starten, Drifts pragmatisch im Flow fixen:**
1. Sprint-Start auf Epic 1.
2. UX-Spec-Drifts werden bei Story 11.1 und Story 4.5 ad-hoc adressiert (Epic/Architecture tragen genug Detail).
3. Architecture-FR-Count-Fix beim nächsten Architecture-Touch.
4. **Vorteil:** schneller Start. **Nachteil:** Style-Konsistenz-Risiko, Traceability-Lücken bleiben.

**Meine Empfehlung: Option A.** Der Aufwand ist gering (~1-2 Stunden), und eine saubere Baseline vor dem 8-Wochen-Sprint reduziert das Risiko, dass sich die Drifts durch den Sprint ziehen und später noch mehr Aufwand verursachen.

### Final Note

Dieses Assessment hat **keine kritischen Blocker** gefunden und **5 Minor-Findings** (P1–P5) dokumentiert, die in 1–2 Stunden behebbar sind. Die Planungs-Artefakte von ctrader sind in einem reifen, implementierbaren Zustand. Die größte Leistung liegt darin, dass trotz mehrerer großer Änderungen innerhalb von zwei Tagen (PostgreSQL-Umstellung, lightweight-charts, IB Quick-Order) die Epic-Coverage zu 100% vollständig geblieben ist.

**Zusammenfassung: 5 Issues in 3 Kategorien (Architecture-Traceability, UX-Konsistenz, Epic-Cleanup). Alle sind Minor. Sprint kann nach Option A starten.**

---

**Assessment Date:** 2026-04-13
**Assessor:** John (BMad PM Agent)
**PRD Version:** 2026-04-13 (asyncpg-Fix, IB Quick-Order, lightweight-charts, PostgreSQL)
**Architecture Version:** 2026-04-13 (Decision #9 IB Quick-Order)
**Epics Version:** 2026-04-12 (alle 62 FRs abgedeckt, Epic 11 vollständig)
**UX-Spec Version:** 2026-04-12 (Stand vor IB-Quick-Order und lightweight-charts-Upgrade)
