---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
status: 'complete'
completedAt: '2026-04-12'
lastUpdated: '2026-04-13'
lastUpdateReason: 'IB Quick-Order (FR53–58) als Decision #9 ergänzt; FR-Coverage von 52→58 / 8→9 Areas; stale DuckDB-Hinweise bereinigt'
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-ctrader.md
  - _bmad-output/planning-artifacts/product-brief-ctrader-distillate.md
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
workflowType: 'architecture'
project_name: 'ctrader3'
user_name: 'Chef'
date: '2026-04-12'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

58 FRs in 9 Capability-Areas, die drei architektonische Schichten bilden:

1. **Data Ingestion, Order Placement & Persistence (FR1–7, FR14–18b, FR49–52, FR53–58):** Zwei Broker-Datenquellen (IB Flex XML + Live-Stream, cTrader Protobuf), **IB Quick-Order-Submission via `ib_async` Bracket Orders mit Trailing Stop-Loss (Aktien-only)**, eine Taxonomie-Quelle (`taxonomy.yaml`), ein MCP-Contract-Snapshot, und Scheduled Jobs für Nightly-Reconciliation, Regime-Snapshots und Backups. Zentral: JSONB `trigger_spec` als strukturiertes Provenance-Schema. **Architektur-Implikation:** Broker-Abstraktionsschicht, idempotente Ingestion-Pipeline (mit `orderRef`-basierter Order-Idempotenz für Quick-Orders), PostgreSQL JSONB als First-Class-Concern, dedizierter `order_service` für Order-Lifecycle.

2. **Business Logic & Orchestration (FR25–32, FR33–40, FR41–48):** Approval-Pipeline als State-Machine mit technisch erzwungenen Gates (Rita/Cassandra RED-Blockade), Strategy-Lifecycle-Management (active/paused/retired mit Bot-Execution-Enforcement), Regime-Kill-Switch mit Horizon-Bewusstsein (Bot-Strategien only — manuelle Quick-Orders sind exempt), Gordon-Trend-Loop mit Diff-Logik. **Architektur-Implikation:** Explizites State-Machine-Pattern für Proposals, Service-Layer für Strategy- und Regime-Management, Event-basiertes Audit-Logging.

3. **Presentation & Query (FR8–13c, FR19–24):** Unified Journal mit Facettenfilter (8 Pflicht-Facetten), Drilldown mit MCP-Side-by-Side, P&L-Kalender, MAE/MFE, Aggregations-Queries, Strategy-Review mit Expectancy-Kurven und Horizon-Gruppierung, **Quick-Order-Formular inline aus Journal/Watchlist**. **Architektur-Implikation:** Server-Rendered HTML via HTMX-Fragmente, JSONB-basierte Facetten-Queries, MCP-Result-Caching mit Staleness-Anzeige, Template-basierter `trigger_spec`-Renderer, Quick-Order als HTMX-Modal/Inline-Fragment.

**Non-Functional Requirements:**

- **Performance (NFR-P1–P6):** Localhost-kalibriert auf ≤2000 Trades. Journal <1.5s, Facettenfilter <500ms, Aggregation <800ms. MCP-Calls sind der Performance-Bottleneck (Cache-Miss <3s, Cache-Hit <500ms). PostgreSQL-Indizes auf JSONB-Felder und Facetten-Spalten werden entscheidend.
- **Reliability (NFR-R1–R8):** Duplikat-Erkennung via Composite-Keys (`permId` für IB, eigene ID für cTrader), idempotente Order-Submits via Client-Order-ID, Dual-Source-Reconciliation (Flex als Source-of-Truth), Graceful Degradation bei MCP-Outages. Append-Only Audit-Log mit Snapshot-Semantik (volle Risk-Gate- und Fundamental-Responses).
- **Integration (NFR-I1–I6):** MCP-Timeout ≤10s, TTL-Cache (15min Crypto / 1h Aktien), Rate-Limit-Awareness mit exponentiellem Backoff, Contract-Testing gegen eingefrorenen Snapshot. Intraday-Candle-Daten für MAE/MFE (Quelle: Architektur-Entscheidung offen).
- **Security (NFR-S1–S5):** Localhost-only Binding, `.env`-Secrets, append-only Audit-Log per DB-Constraint, restriktive Filesystem-Permissions, keine Telemetrie.
- **Maintainability (NFR-M1–M6):** `ruff` für Lint/Format, `pytest` für Tests, strukturiertes JSON-Logging mit Rotation, versionierte idempotente Migrations, Single-Process-Architektur.

**Scale & Complexity:**

- Primäre Domäne: Server-Rendered Web Application mit heterogenen externen Integrationen
- Komplexitätsstufe: Medium-High
- Geschätzte architektonische Hauptkomponenten: ~12 (Broker-Clients ×2, MCP-Client, Ingestion-Pipeline, Trade-Repository, Strategy-Service, Approval-State-Machine, Regime-Service, Scheduler, Query/Aggregation-Engine, Template-Renderer, Audit-Logger)

### Technische Constraints & Dependencies

**Locked Technical Decisions:**
- Python 3.12+ / `uv` / FastAPI + HTMX + Tailwind (kein Node, kein React)
- PostgreSQL (geändert von DuckDB am 2026-04-12 — Concurrent-Write-Sicherheit, vorhandene Ops-Erfahrung)
- `ib_async` + Flex Queries für IB / OpenApiPy für cTrader
- `fundamental` MCP-Server als harte externe Dependency
- APScheduler im FastAPI-Prozess für Scheduled Jobs
- Kein ORM — direktes SQL via `asyncpg` oder `psycopg3`
- Alpine.js nur für Command Palette

**Harte externe Dependencies:**
1. **`fundamental` MCP-Server** — 5 Tools, 5 Agent-Workflows. Contract wird in Woche 0 eingefroren. Breakage = UI-Warnung, nicht Trade-Blockade.
2. **Interactive Brokers TWS/Gateway** — lokaler Proxy, nächtliche Reconnects, Flex Query Web Service.
3. **cTrader Demo-Account** — Protobuf/SSL, Rate-Limits, OAuth2.

**Geänderte Implikationen durch PostgreSQL:**
- Connection-Pooling notwendig (z.B. `asyncpg` Pool oder `psycopg_pool`)
- DB ist externer Prozess — Health-Check im Health-Widget erweitern
- JSONB-Queries profitieren von PostgreSQL's reifem `@>`, `->`, `->>` Operator-Set und GIN-Indizes
- Backup-Strategie: `pg_dump` oder bestehende Infrastruktur von Chef
- Migrations-Runner: SQL-Dialekt ist PostgreSQL, nicht DuckDB

### Cross-Cutting Concerns

1. **Trigger-Provenance-Schema (`trigger_spec` JSONB)** — Durchschneidet Ingestion (Schreiben bei Bot-Trades + Post-hoc-Tagging), Business Logic (Facetten-Queries, Aggregation), Presentation (Natursprache-Rendering). Braucht ein zentrales Schema-Definition + Renderer + Query-Builder.

2. **MCP-Integration-Layer** — Einheitliches Pattern für alle MCP-Calls: Timeout, Caching mit TTL, Staleness-Tracking, Graceful Degradation (UI zeigt "nicht verfügbar" statt Fehler). Braucht einen MCP-Client-Wrapper mit diesen Policies.

3. **Audit-Logging** — Append-Only mit Snapshot-Semantik. Betrifft Approval-Pipeline, Kill-Switch-Overrides, und Contract-Test-Ergebnisse. Braucht ein zentrales Audit-Service-Pattern.

4. **Idempotenz** — Durchschneidet: Flex-Query-Import, Live-Sync, Bot-Order-Submits, Scheduled Jobs, Migrations. Jede Schreiboperation muss bei Wiederholung identisches Ergebnis liefern.

5. **Staleness & Graceful Degradation** — Jede externe Datenquelle (MCP, IB, cTrader) kann ausfallen. Das UI muss jeden Zustand ehrlich zeigen ("Stand: XX:XX", "Nicht verfügbar"). Kein Silent Failure.

6. **URL-State-Management** — Facetten, Pagination, Expansion, Zeitraum — alles als Query-Parameter. Braucht ein konsistentes URL-Encoding/Decoding-Pattern auf Server-Seite.

## Starter Template Evaluation

### Primary Technology Domain

Server-Rendered Web Application (Python/FastAPI + HTMX) mit heterogenen externen Integrationen (Broker-APIs, MCP-Server). Stack ist durch Locked Technical Decisions vollständig festgelegt.

### Starter Options Considered

Vier verfügbare FastAPI+HTMX+Tailwind-Starter wurden recherchiert und evaluiert:

| Starter | Abgelehnt weil |
|---|---|
| `fastapi-quickstart` (Achronus) | Verwendet Flowbite — widerspricht Handroll Design System |
| `fastHTMX` (stevenmfowler) | DaisyUI — "Dark Notion"-Ästhetik, nicht "Dark Cockpit" |
| `fastapi-htmx-tailwind-example` (volfpeter) | MongoDB, falscher Domain (IoT Dashboard) |
| `fastapi-htmx-daisyui` (sunscrapers) | DaisyUI, TODO-App-Niveau, keine DB-Schicht |

Zusätzlich evaluierte Libraries: `fasthx` (PyPI) und `fastapi-htmx` (maces) als potenzielle HTMX-Helper-Dependencies — Entscheidung offen bis Implementation.

### Selected Approach: Bootstrap from Scratch

**Rationale:** Kein verfügbarer Starter passt zu ctraders Anforderungsprofil (Handroll Design System, PostgreSQL mit Raw SQL ohne ORM, Domain-spezifische Broker/MCP-Integrationen). Einen Starter anzupassen wäre aufwändiger als sauberes Scaffolding.

**Initialization Command:**

```bash
uv init ctrader
cd ctrader
uv add fastapi uvicorn[standard] jinja2 python-multipart
uv add asyncpg apscheduler httpx structlog pydantic pydantic-settings
uv add --dev pytest pytest-asyncio ruff
```

**Architektonische Entscheidungen durch das Scaffolding:**

**Language & Runtime:**
- Python 3.12+ mit `uv` als Package-Manager
- Type Hints durchgängig, `mypy` optional

**Styling Solution:**
- Tailwind CSS via Standalone-Binary (kein Node-Toolchain)
- Eigene Design-Tokens als CSS Custom Properties (`design-tokens.css`)
- 13 Jinja2-Makros als Handroll Component System

**Build Tooling:**
- Kein Build-Step außer `tailwindcss --watch` in Dev-Mode
- Tailwind CLI produziert eine einzige CSS-Output-Datei

**Testing Framework:**
- `pytest` + `pytest-asyncio` für Unit- und Integration-Tests
- Contract-Tests gegen MCP-Snapshot als eigene Test-Suite

**Code Organization:**
- Router → Service → Repository-Pattern (ohne ORM)
- `asyncpg` Connection-Pool für PostgreSQL
- Eigener Migrations-Runner (`app/db/migrate.py`)

**Development Experience:**
- `uvicorn --reload` + `tailwindcss --watch` für Hot-Reload
- `ruff` für Lint + Format (ein Tool)
- Strukturiertes JSON-Logging via `structlog`

**Projektstruktur:**

```
ctrader/
├── app/
│   ├── main.py                    # FastAPI app + Lifespan (APScheduler, DB-Pool)
│   ├── config.py                  # pydantic-settings, .env-Loading
│   ├── db/
│   │   ├── pool.py                # asyncpg Connection-Pool
│   │   ├── migrate.py             # Eigener Migrations-Runner
│   │   └── queries/               # SQL-Dateien oder Query-Funktionen
│   ├── routers/                   # FastAPI-Routen
│   ├── services/                  # Business Logic
│   ├── clients/                   # Externe Integrationen (MCP, IB, cTrader)
│   ├── models/                    # Pydantic-Modelle (kein ORM)
│   ├── jobs/                      # APScheduler Job-Funktionen
│   ├── static/css/                # design-tokens.css + Tailwind Output
│   └── templates/
│       ├── components/            # 13 Jinja2-Makros
│       ├── layouts/               # base.html, dense.html
│       └── views/                 # Seiten-Templates
├── migrations/                    # 001_initial_schema.sql, etc.
├── tests/
├── taxonomy.yaml
├── pyproject.toml
└── .env                           # Secrets (in .gitignore)
```

**Note:** Projekt-Initialisierung mit diesem Setup ist die erste Implementation-Story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
1. PostgreSQL mit `asyncpg` als Storage-Layer (geändert von DuckDB)
2. MCP-Anbindung via HTTP/SSE (fundamental läuft als eigenständiger Service)
3. Docker Compose als Deployment-Strategie
4. Append-Only Audit-Log via PostgreSQL DB-Trigger

**Important Decisions (Shape Architecture):**
5. In-Memory TTL-Cache für MCP-Ergebnisse
6. `pytailwindcss` für Tailwind-Compilation ohne Node
7. Hybrid MAE/MFE-Datenquelle (IB Historical + fundamental/price)
8. Chart-Rendering via `lightweight-charts` (TradingView Open-Source, Apache 2.0) — ersetzt Screenshot-Upload (FR13c) durch dynamische OHLC-Charts mit Entry/Exit-Markern und Indikatoren
9. **IB Quick-Order via `ib_async` Bracket Order mit Trailing Stop-Loss** (FR53–58) — Aktien-only im MVP, dedizierter `order_service.py`, Endpoint unter `routers/trades.py` (`POST /trades/quick-order`), erweiterte `trades`-Tabelle mit Order-Lifecycle-Spalten, Kill-Switch-Exemption für manuelle Quick-Orders

**Deferred Decisions (Post-MVP):**
- Redis-Cache falls In-Memory nicht skaliert (unwahrscheinlich bei Single-User)
- Kubernetes/Swarm falls Multi-Service-Orchestrierung nötig wird
- Eigene Intraday-Datenquelle falls fundamental/price unzureichend für Crypto-MAE/MFE

### Data Architecture

**Database: PostgreSQL via `asyncpg`**
- Driver: `asyncpg` — Binary-Protocol, eingebauter Connection-Pool, automatische JSONB ↔ dict Konversion
- Connection-Pool: `asyncpg.create_pool()` im FastAPI-Lifespan-Event, Pool-Size kalibriert auf Single-User (min=2, max=10)
- Schema-Modellierung: Raw SQL, kein ORM. Pydantic-Modelle für Validation und Serialisierung, SQL-Queries in `app/db/queries/`
- JSONB: `trigger_spec`-Spalte mit GIN-Index für Facetten-Queries (`@>`, `->`, `->>`). PostgreSQL's JSONB ist die reifste Implementation und unterstützt alle Query-Patterns aus FR10/FR13
- Migrations: Eigener Runner (`app/db/migrate.py`), Sequential-Nummerierung (`001_*.sql`), Tracking in `schema_migrations`-Tabelle, idempotent

**Caching: In-Memory TTL-Cache**
- Implementation: `cachetools.TTLCache` oder eigene dict-basierte Lösung mit Zeitstempel-Tracking
- TTLs: 15 Minuten für Crypto-Assets (Satoshi/Cassandra), 1 Stunde für Aktien (Viktor/Rita), 24 Stunden für historische Candle-Daten (MAE/MFE)
- Staleness-Tracking: Jeder Cache-Eintrag speichert `cached_at`-Zeitstempel für die UI-Anzeige ("Stand: vor X Minuten")
- Cache verschwindet bei Restart — akzeptabel für Single-User-Localhost

**Audit-Log: Append-Only via DB-Trigger**
- PostgreSQL `BEFORE UPDATE OR DELETE`-Trigger auf `approval_audit_log`-Tabelle, der `RAISE EXCEPTION 'audit log is append-only'` wirft
- Technisch unumgehbar, selbst bei Application-Bugs oder direktem DB-Zugriff
- Implementation als dedizierte Migration (z.B. `003_audit_log_trigger.sql`)

**OHLC-Daten & Chart-Rendering (FR13c — geändert von Screenshot zu dynamischem Chart):**
- Chart-Library: `lightweight-charts` v5 (TradingView Open-Source, Apache 2.0, 35KB Standalone JS)
- Eingebunden als lokale Datei in `app/static/js/lightweight-charts.standalone.production.js` (kein CDN, kein Node)
- OHLC-Datenquellen:
  - IB-Aktien/Optionen: `ib_async` `reqHistoricalData()` (1-Minute-Bars für Trade-Zeitraum)
  - Crypto/CFDs: Binance API oder Kraken API (kostenlos, 1-Minute-OHLCV)
  - Fallback: `fundamental/price` MCP-Tool (Verfügbarkeit in Woche 0 verifizieren)
- OHLC-Cache: Historische Candles in PostgreSQL-Tabelle `ohlc_candles` mit 24h TTL (Candles ändern sich nicht nachträglich)
- Entry/Exit-Marker: Via `SeriesMarkers` API — grüner Marker bei Entry, roter bei Exit
- Indikatoren: Server-seitig berechnet via `pandas-ta`, als JSON an Client geliefert, via `lightweight-charts` als Overlay-Lines gerendert
- Chart-Endpoint: `GET /trades/{id}/chart_data` liefert JSON `{ ohlc: [...], markers: [...], indicators: {...} }`
- Graceful Degradation: Wenn keine OHLC-Daten verfügbar → Chart-Bereich zeigt "Keine Candle-Daten verfügbar" statt leerem Container

### IB Quick-Order Architecture (FR53–58)

**Service: `order_service.py`** (dedizierter Service, getrennt von `trade_service`)
- Verantwortung: Quick-Order-Validation, Bracket-Order-Konstruktion, Submission via `clients/ib.py`, Status-Tracking, Auto-Tagging des resultierenden Trades
- Symmetrisch zu `approval_service.py` (das die cTrader-Bot-Order-Routing macht), aber für manuelle IB-Aktien-Orders
- **Begründung Service-Trennung:** Order-Lifecycle hat eigene Fehlerfälle (Margin-Rejection, ungültiges Symbol, Markt geschlossen) und eigene Idempotenz-Anforderungen (`orderRef`); Vermischung mit `trade_service` (Sync, Reconciliation, MAE/MFE) macht Debugging später schwerer

**Client-Erweiterung: `clients/ib.py`**
- Neue Funktion: `place_bracket_order(symbol, side, qty, limit_price, trailing_stop_amount, order_ref) -> OrderSubmitResult`
- Verwendet `ib_async`'s `bracketOrder()` Convenience-Methode
- Parent-Order: Limit Buy/Sell mit `transmit=False`
- Child-Order: Trailing Stop mit `transmit=True` (atomare Submission)
- `orderRef` wird auf beide Orders gesetzt (Idempotenz-Key)
- Fehler-Klassifikation: transient (Reconnect/Timeout → Retry) vs terminal (Margin/Symbol/Market-Closed → UI-Banner)
- **Trailing Stop wird serverseitig von IB verwaltet** — kein lokales Trailing-Monitoring nötig

**Router-Erweiterung: `routers/trades.py`**
- Neuer Endpoint: `POST /trades/quick-order` (HTMX-Form-Submit aus Journal/Watchlist)
- Neuer Endpoint: `GET /trades/quick-order/form` (HTMX-Fragment mit Pre-fill aus Kontext)
- Neuer Endpoint: `POST /trades/quick-order/preview` (Bestätigungs-Zusammenfassung mit berechnetem Risiko)
- **Begründung Router-Wahl:** Quick-Order ist UI-mental-model "Trade aus Journal aufgeben", nicht "neue Order-Domain". URL bleibt im Journal-Bereich.

**Datenmodell: Erweiterung der `trades`-Tabelle** (kein separates `ib_orders`)
- Neue Spalten:
  - `order_status` (ENUM: `submitted`, `filled`, `partial`, `rejected`, `cancelled`, `synced`) — `synced` für Trades, die nicht über Quick-Order kamen
  - `order_ref` (TEXT, UNIQUE-Constraint, NULL für synced trades) — Idempotenz-Key
  - `limit_price` (NUMERIC, NULL bei Market-Orders/synced)
  - `trailing_stop_amount` (NUMERIC, NULL für synced)
  - `trailing_stop_unit` (ENUM: `absolute`, `percent`, NULL für synced)
  - `submitted_at` (TIMESTAMPTZ, NULL für synced)
- **Begründung:** Rejected Orders sind Provenance-Daten ("warum hast du diese Order abgebrochen?") — gehören ins Journal. Trade ist Trade, egal welcher Lifecycle-Status.

**Auto-Tagging-Flow:**
- Bei erfolgreichem `POST /trades/quick-order` füllt `order_service` direkt die `trigger_spec` (JSONB), `strategy_id`, `horizon` und `trigger_source` aus dem Quick-Order-Formular-Kontext
- `status = 'tagged'` (nicht `'untagged'`) — kein Post-hoc-Tagging nötig
- Der bei Fill resultierende Trade wird über `order_ref` mit dem Submission-Eintrag gemerged (`UPDATE` auf bestehende Row, kein neuer INSERT)

**Kill-Switch-Exemption (FR42 vs FR53–58):**
- Der horizon-bewusste Regime-Kill-Switch (FR42) blockiert ausschließlich **Bot-Strategien** (`approval_service` → cTrader-Execution)
- Manuelle Quick-Orders sind **explizit exempt** — Chef hat aktiv auf "Order senden" geklickt und trägt die Verantwortung selbst
- `regime_service` wird im `order_service`-Pfad **nicht** konsultiert
- Im UI: Wenn aktiver Kill-Switch das Marktregime als RED markiert, zeigt das Quick-Order-Formular einen **Warnbanner** ("⚠ Aktuelles Regime: Fear & Greed = 18, Bot-Strategien pausiert"), aber **kein Block**. Reine Information.

**Idempotenz (NFR-R3a):**
- `orderRef` wird von `order_service` als UUID v4 generiert und sowohl in der `trades`-Tabelle als UNIQUE-Constraint gespeichert als auch an `ib_async` übergeben
- Ein Retry nach TWS-Reconnect oder Netzausfall kollidiert auf dem UNIQUE-Constraint und wird als "schon gesendet, Status abrufen" behandelt
- Test-Case: Replay des `place_bracket_order`-Calls mit identischem `order_ref` darf maximal einen DB-Eintrag und maximal eine IB-Order erzeugen

**Tests:**
- `tests/unit/services/test_order_service.py` — Validation, Bracket-Order-Konstruktion, Auto-Tagging-Logik
- `tests/integration/clients/test_ib_order_idempotency.py` — Replay-Test mit identischem `order_ref` (gegen IB Paper-Account, manuell triggerbar)

### Authentication & Security

**Keine Änderungen zu Locked Decisions — Zusammenfassung:**
- Kein Auth-System: FastAPI bindet an `127.0.0.1`, Localhost-Zugriff ist der Auth-Layer
- Secrets: `.env`-Datei mit `pydantic-settings`, `.gitignore`-enforced
- Audit-Log: Append-Only per DB-Trigger (siehe Data Architecture)
- Filesystem-Permissions: `0600` für Dateien, `0700` für Verzeichnisse
- Keine Telemetrie, kein externes Error-Tracking

### API & Communication Patterns

**MCP-Client: HTTP/SSE-Transport**
- `fundamental` MCP-Server läuft als eigenständiger Prozess (außerhalb von ctrader's Docker Compose oder auf dem Host)
- ctrader verbindet sich als MCP-Client via HTTP/SSE (Streamable HTTP Transport)
- MCP-Client-Wrapper in `app/clients/mcp.py` mit einheitlichem Pattern: Timeout (≤10s), TTL-Cache, Staleness-Tracking, Graceful Degradation
- Bei MCP-Outage: UI zeigt "Nicht verfügbar, Stand XX:XX", Approval-Flow blockiert bei Risk-Gate-Timeout (kein stilles Durchwinken)
- Contract-Test: Täglicher Vergleich der MCP-Tool-Schemas gegen eingefrorenen Woche-0-Snapshot

**HTMX-Endpoint-Struktur:**
- Jede View hat zwei Endpoint-Typen: Full-Page-Render (GET `/trades`) und Fragment-Update (GET `/trades?hx=true` oder dedizierte Fragment-Routen)
- Facettenfilter-Updates via HTMX `hx-get` mit Query-Parametern, Server rendert nur das betroffene Fragment (Aggregation + Tabelle)
- URL-State via `hx-push-url` — jeder HTMX-Request aktualisiert die Browser-URL

**Error-Handling:**
- Broker-Fehler: Unterscheidung transient (Retry mit exponentiellem Backoff) vs terminal (UI-Banner + Log)
- MCP-Fehler: Timeout → Cache-Fallback mit Staleness-Anzeige, kein Retry
- DB-Fehler: Propagation als HTTP 500 mit strukturiertem Log-Eintrag, UI zeigt Toast
- HTMX-Fragment-Fehler: Server liefert Error-Fragment statt leerer Response

### Frontend Architecture

**Keine SPA — Server-Rendered mit HTMX:**
- Jinja2-Templates mit 13+1 Makros (13 aus UX-Spec + `query_prose` aus Design-Direction)
- HTMX für Fragment-Updates ohne Page-Reload
- Alpine.js ausschließlich für Command Palette (`Ctrl+K`) und Multi-Select-Facettenfilter
- Tailwind CSS via `pytailwindcss` (Python-Wrapper, `uv`-managed, kein Node)
- Design-Tokens als CSS Custom Properties in `design-tokens.css`
- Dark-Cockpit-Theme, kein Light-Mode im MVP

**Tailwind-Build-Pipeline:**
- `pytailwindcss` als Dev-Dependency
- Dev-Mode: `tailwindcss --watch` parallel zu `uvicorn --reload`
- Production: `tailwindcss --minify` als Docker-Build-Stage
- Output: Eine einzige CSS-Datei in `app/static/css/main.css`

### Infrastructure & Deployment

**Docker Compose:**
- `docker-compose.yml` mit zwei Services: `ctrader` (FastAPI + APScheduler) und `postgres` (oder Referenz auf bestehende externe Instanz)
- `ctrader`-Container: Multi-Stage-Build (Tailwind-Build → Runtime mit `uv` + `uvicorn`)
- Volumes: `./data/logs` (Log-Rotation), `./data/mcp-snapshots` (Contract-Snapshot)
- PostgreSQL: Bestehende Instanz als `external` Service oder eigener Container — Entscheidung bei Chef
- Environment: `.env`-File via `env_file` in Docker Compose
- Restart-Policy: `unless-stopped` für beide Services

**Observability:**
- `structlog` mit JSON-Format, Output in Datei + stdout (Docker-Logs)
- FastAPI-Middleware für Request-Logging (Method, Path, Status, Duration)
- Health-Widget im UI (`/settings`): Broker-Status, MCP-Status, Job-Timestamps, DB-Connectivity
- Kein Sentry, kein DataDog — Logs + UI-Health reichen für Single-User

**Backup:**
- PostgreSQL: `pg_dump` als täglicher Scheduled Job (APScheduler, 04:00 UTC) oder bestehende Backup-Infrastruktur von Chef
- Backup-Target: Volume-Mount oder Host-Verzeichnis

### Decision Impact Analysis

**Implementation Sequence:**
1. Docker Compose + PostgreSQL-Setup (Woche 0)
2. `asyncpg` Connection-Pool + Migrations-Runner (Woche 0)
3. MCP-Client mit HTTP/SSE-Transport + Contract-Snapshot (Woche 0)
4. Audit-Log-Trigger-Migration (Woche 6, mit Approval-Pipeline)
5. Tailwind-Build-Pipeline (Woche 0/1)
6. MAE/MFE-Datenquellen-Integration (Woche 3–4)
7. In-Memory-Cache für MCP-Ergebnisse (Woche 4)

**Cross-Component Dependencies:**
- `asyncpg`-Pool wird von allen Services und Jobs genutzt → zentrale Initialisierung im Lifespan
- MCP-Client wird von Journal-Drilldown, Approval-Pipeline, Gordon-Loop und Contract-Test genutzt → zentraler Wrapper mit einheitlichen Policies
- Audit-Log-Trigger muss vor der Approval-Pipeline-Implementation stehen
- Docker Compose bestimmt, wie `fundamental` erreichbar ist (Host-Network oder Service-Discovery)

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**12 kritische Konflikt-Punkte identifiziert**, an denen verschiedene AI-Agents unterschiedliche Entscheidungen treffen könnten: DB-Naming, API-Naming, Code-Naming, Template-Naming, Projekt-Organisation, Test-Organisation, Response-Format, Datenformate, Service-Kommunikation, Logging, Error-Handling, Dependency-Injection.

### Naming Patterns

**Database Naming Conventions:**

| Element | Konvention | Beispiel |
|---|---|---|
| Tabellen | `snake_case`, Plural | `trades`, `strategies`, `approval_audit_log` |
| Spalten | `snake_case` | `trigger_spec`, `opened_at`, `agent_id` |
| Primary Keys | `id` (integer, SERIAL oder BIGSERIAL) | `trades.id` |
| Foreign Keys | `{referenzierte_tabelle_singular}_id` | `strategy_id`, `agent_id` |
| Indizes | `idx_{tabelle}_{spalte(n)}` | `idx_trades_symbol`, `idx_trades_trigger_spec` (GIN) |
| Constraints | `{tabelle}_{typ}_{spalte}` | `trades_unique_perm_id`, `trades_check_side` |
| Enums | PostgreSQL `CREATE TYPE`, snake_case | `CREATE TYPE trade_source AS ENUM ('ib', 'ctrader')` |
| Zeitstempel | `_at`-Suffix, immer `TIMESTAMPTZ` (UTC) | `opened_at`, `approved_at`, `cached_at` |

**API / Route Naming Conventions:**

| Element | Konvention | Beispiel |
|---|---|---|
| Routen | `snake_case`, Plural für Collections | `/trades`, `/strategies`, `/approvals` |
| Ressourcen-Detail | `/{collection}/{id}` | `/trades/42`, `/strategies/7` |
| Fragment-Endpoints | Suffix `_fragment` oder dedizierte Pfade | `/trades/42/detail_fragment` |
| Query-Parameter | `snake_case` | `?asset_class=crypto&trigger_source=satoshi` |
| Actions | Verb als Suffix | `/approvals/42/approve`, `/approvals/42/reject` |

**Python Code Naming Conventions:**

| Element | Konvention | Beispiel |
|---|---|---|
| Module/Dateien | `snake_case.py` | `trade_service.py`, `mcp_client.py` |
| Klassen | `PascalCase` | `TradeService`, `ApprovalStateMachine` |
| Funktionen/Methoden | `snake_case` | `get_trades_by_filter()`, `approve_proposal()` |
| Variablen | `snake_case` | `trade_count`, `risk_gate_result` |
| Konstanten | `UPPER_SNAKE_CASE` | `MCP_TIMEOUT_SECONDS`, `CACHE_TTL_CRYPTO` |
| Pydantic-Modelle | `PascalCase` mit Suffix | `TradeCreate`, `TradeResponse`, `ProposalApproval` |
| Routers | `snake_case`, Datei = Route-Gruppe | `routers/trades.py`, `routers/approvals.py` |

**Jinja2 / Frontend Naming:**

| Element | Konvention | Beispiel |
|---|---|---|
| Template-Dateien | `snake_case.html` | `trade_detail.html`, `facet_bar.html` |
| Makro-Namen | `snake_case` | `{% macro stat_card(label, value, trend) %}` |
| CSS-Klassen | Tailwind-Utilities + eigene mit `ct-` Prefix | `ct-trade-row`, `ct-facet-chip--active` |
| HTML-IDs | `kebab-case` | `id="trade-detail-42"`, `id="facet-bar"` |
| HTMX-Targets | `#kebab-case` | `hx-target="#trade-list"`, `hx-target="#aggregation-block"` |
| Data-Attribute | `data-kebab-case` | `data-trade-id="42"`, `data-facet-name="asset_class"` |
| Fragment-Dateien | Prefix `_` | `_list_fragment.html`, `_aggregation_fragment.html` |

### Structure Patterns

**Projekt-Organisation — Feature-gruppiert innerhalb der Layer:**

```
app/
├── routers/          # Ein Router pro Route-Gruppe
│   ├── trades.py     # GET /trades, GET /trades/{id}, POST /trades/{id}/tag
│   ├── strategies.py
│   ├── approvals.py
│   ├── trends.py
│   ├── regime.py
│   └── settings.py
├── services/         # Business Logic, ein Service pro Domäne
│   ├── trade_service.py
│   ├── strategy_service.py
│   ├── approval_service.py
│   ├── regime_service.py
│   ├── audit_service.py
│   └── taxonomy_service.py
├── clients/          # Externe Integrationen
│   ├── mcp.py        # MCP-Client-Wrapper (Timeout, Cache, Degradation)
│   ├── ib.py         # ib_async + Flex Query
│   └── ctrader.py    # OpenApiPy
├── db/
│   ├── pool.py       # asyncpg Pool-Management
│   ├── migrate.py    # Migrations-Runner
│   └── queries/      # SQL-Queries, gruppiert nach Domäne
│       ├── trades.py
│       ├── strategies.py
│       ├── approvals.py
│       └── regime.py
├── models/           # Pydantic-Modelle, gruppiert nach Domäne
│   ├── trade.py
│   ├── strategy.py
│   ├── approval.py
│   ├── regime.py
│   └── mcp.py
├── jobs/             # APScheduler Job-Funktionen
│   ├── flex_nightly.py
│   ├── regime_snapshot.py
│   ├── gordon_weekly.py
│   ├── contract_test.py
│   └── backup.py
├── templates/
│   ├── components/   # Makros (wiederverwendbar)
│   ├── layouts/      # base.html, dense.html
│   └── views/        # Seiten (eine pro Route-Gruppe)
│       ├── trades/
│       ├── strategies/
│       ├── approvals/
│       ├── trends/
│       ├── regime/
│       └── settings/
├── static/css/
├── main.py
└── config.py
```

**Abhängigkeitsrichtung:** Router → Service → DB/Client. Niemals umgekehrt. Kein SQL im Router, kein Client-Call im Router.

**Test-Organisation — Separater `tests/`-Ordner, Struktur spiegelt `app/`:**

```
tests/
├── unit/
│   ├── services/
│   └── models/
├── integration/
│   ├── db/
│   └── clients/
└── conftest.py       # Fixtures (DB-Pool, Test-Daten)
```

### Format Patterns

**HTMX-Response-Format:**

- Full-Page: Jinja2 rendert komplettes HTML mit Layout via `TemplateResponse`
- Fragment: Nur das betroffene Stück HTML ohne Layout, Fragment-Dateien mit `_`-Prefix
- Error-Fragment: Bei Fehler liefert der Server ein Error-HTML-Fragment, nie leeren Body

**Datenformate:**

| Format | Regel | Beispiel |
|---|---|---|
| Zeitstempel in DB | `TIMESTAMPTZ`, immer UTC | `2026-04-12T14:23:00Z` |
| Zeitstempel in UI | Lokale Zeit (CET/CEST) mit Quelle | "14:23 (vor 2h)" |
| Geldbeträge | `DECIMAL(12,2)` in DB, nie `FLOAT` | `1234.56` |
| R-Multiple | `DECIMAL(6,2)`, `NULL` bei fehlendem Stop | `+0.80R` oder `NULL` |
| P&L | Inklusive Gebühren und Funding-Rates, immer Netto | |
| JSONB-Keys | `snake_case` | `{"trigger_type": "news", "confidence": 0.72}` |

### Communication Patterns

**Service-zu-Service:** Direkte Aufrufe, kein Event-System im MVP. Router → Service → DB/Client.

**Logging-Konventionen:**

- Logger: `structlog.get_logger(__name__)` pro Modul
- Levels: DEBUG (Cache-Hit/Miss, Queries), INFO (Business-Events), WARNING (Degradierte Zustände), ERROR (Intervention nötig)
- Format: Immer mit Kontext-Feldern, nie f-Strings in Log-Messages
- Beispiel: `logger.info("trade_synced", trade_id=42, source="ib", symbol="AAPL")`

### Process Patterns

**Error-Handling-Hierarchie:**

1. **Transiente Fehler** (Retry) — Broker-Disconnects, Netz-Timeouts → Exponentieller Backoff: 1s Start, max 60s, max 5 Retries
2. **Degradierte Zustände** (Graceful Degradation) — MCP-Timeout → Cache-Fallback + Staleness-Banner, Broker offline → UI-Banner
3. **Terminale Fehler** (Log + UI-Banner) — DB-Fehler, ungültige Daten, unerwartete Exceptions

**Dependency-Injection:** Services und Clients werden im FastAPI-Lifespan erstellt und via `Depends()` injiziert. Kein globaler mutabler State.

**Approval-State-Machine:**

```
draft → pending_risk_check → risk_checked → pending_approval → approved | rejected | revision
                                                                    ↓
                                                              executing → filled | failed
```

Jeder Übergang wird im Audit-Log festgehalten. Ungültige Übergänge werfen eine Exception.

### Enforcement Guidelines

**Alle AI-Agents MÜSSEN:**

1. **Snake_case überall** — Python, SQL, JSON-Keys, Query-Parameter. Einzige Ausnahme: PascalCase für Klassen/Pydantic-Modelle.
2. **UTC in der DB, lokal im UI** — Kein `datetime.now()` ohne explizites `timezone.utc`.
3. **Abhängigkeitsrichtung einhalten** — Router → Service → DB/Client. Nie SQL im Router.
4. **Fragmente mit `_` prefixen** — `_list_fragment.html`, nie anders.
5. **SQL lebt in `db/queries/`** — Services rufen Query-Funktionen auf, nie Raw SQL.
6. **Graceful Degradation bei jedem externen Call** — MCP, IB, cTrader. Fallback-State mit Staleness-Information.
7. **Strukturiertes Logging** — Kontext-Feldern statt f-Strings. `logger.info("event_name", key=value)`.
8. **Pydantic für alle Grenzen** — Request-Validation, Response-Serialisierung, Config-Loading. Keine rohen dicts an Router-Grenzen.

**Pattern-Enforcement:** `ruff` prüft Python-Naming, Migrations-Runner prüft Sequential-Nummerierung, dieses Dokument als Referenz bei Code-Review.

## Project Structure & Boundaries

### Complete Project Directory Structure

```
ctrader/
├── docker-compose.yml                    # ctrader + PostgreSQL Services
├── Dockerfile                            # Multi-Stage: Tailwind Build → Runtime
├── .dockerignore
├── pyproject.toml                        # uv Dependencies + Projekt-Metadata
├── uv.lock                              # Lockfile
├── .env.example                          # Template für .env (ohne echte Secrets)
├── .env                                  # Secrets (in .gitignore)
├── .gitignore
├── tailwind.config.js                    # Tailwind-Konfiguration
├── taxonomy.yaml                         # Trigger-Typen, Exit-Gründe, Regime-Tags (Woche 2)
├── mcp_contract_snapshot.json            # Eingefrorener MCP-Contract (Woche 0)
│
├── migrations/                           # PostgreSQL-Migrationen (versioniert, idempotent)
│   ├── 001_initial_schema.sql            # trades, strategies, regime_snapshots
│   ├── 002_taxonomy_seed.sql             # Taxonomie aus taxonomy.yaml laden
│   ├── 003_audit_log.sql                 # approval_audit_log + Append-Only-Trigger
│   ├── 004_gordon_snapshots.sql          # gordon_trend_snapshots Tabelle
│   ├── 005_quick_order_columns.sql       # trades-Tabelle erweitern: order_status, order_ref (UNIQUE), limit_price, trailing_stop_amount, trailing_stop_unit, submitted_at (FR53–58)
│   └── ...
│
├── app/
│   ├── __init__.py
│   ├── main.py                           # FastAPI app, Lifespan (DB-Pool, APScheduler, MCP-Client)
│   ├── config.py                         # pydantic-settings, .env-Loading, alle Konstanten
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── pool.py                       # asyncpg.create_pool(), Health-Check
│   │   ├── migrate.py                    # Migrations-Runner (schema_migrations-Tabelle)
│   │   └── queries/
│   │       ├── __init__.py
│   │       ├── trades.py                 # find_by_filter, find_by_id, upsert_from_flex, upsert_from_live, insert_quick_order, update_order_status, find_by_order_ref
│   │       ├── strategies.py             # find_all, find_by_id, create, update_status, aggregate_metrics
│   │       ├── approvals.py              # find_pending, find_by_id, update_state, insert_audit_entry
│   │       ├── regime.py                 # insert_snapshot, find_latest, find_range
│   │       └── gordon.py                 # insert_snapshot, find_latest_two, find_diff
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── trade.py                      # Trade, TradeCreate, TradeResponse, TradeFilter, TradeAggregation, OrderStatus (enum)
│   │   ├── order.py                      # QuickOrderRequest, QuickOrderPreview, OrderSubmitResult, BracketOrderSpec (FR53–58)
│   │   ├── strategy.py                   # Strategy, StrategyCreate, StrategyMetrics, StrategyStatus
│   │   ├── approval.py                   # Proposal, ProposalState, ApprovalDecision, AuditEntry
│   │   ├── regime.py                     # RegimeSnapshot, KillSwitchState
│   │   ├── trigger_spec.py              # TriggerSpec (JSONB-Schema), TriggerSpecReadable
│   │   ├── mcp.py                        # FundamentalResult, RiskGateResult, GordonTrendRadar
│   │   └── taxonomy.py                   # TriggerType, ExitReason, MistakeTag, HorizonType
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── trade_service.py              # Sync, Reconciliation, Tagging, MAE/MFE
│   │   ├── order_service.py              # IB Quick-Order: Validation, Bracket-Submission, Status-Tracking, Auto-Tagging (FR53–58)
│   │   ├── strategy_service.py           # CRUD, Status-Management, Metriken
│   │   ├── approval_service.py           # State-Machine, Risk-Gate, cTrader-Bot-Order-Routing
│   │   ├── regime_service.py             # Kill-Switch-Logik (Bot-only), Snapshot, Horizon-Bewusstsein
│   │   ├── audit_service.py              # Append-Only Insert, Snapshot-Erstellung
│   │   ├── taxonomy_service.py           # YAML-Loading, Dropdown-Daten
│   │   └── metrics_service.py            # Expectancy, R-Multiple, Winrate, Drawdown (pure)
│   │
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── mcp.py                        # MCP-Client (HTTP/SSE, Timeout, Cache, Degradation)
│   │   ├── ib.py                         # ib_async Live-Sync + Flex Query XML-Parser + place_bracket_order() für Quick-Order (FR55)
│   │   ├── ctrader.py                    # OpenApiPy Client (Handshake, Order, Status)
│   │   └── ohlc.py                       # OHLC-Datenquellen-Abstraktion (IB + Binance/Kraken)
│   │
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── scheduler.py                  # APScheduler-Setup, Job-Registry
│   │   ├── flex_nightly.py               # Täglich 00:15 UTC
│   │   ├── regime_snapshot.py            # Täglich 00:30 UTC
│   │   ├── gordon_weekly.py              # Montag 06:00 UTC
│   │   ├── contract_test.py              # Täglich 03:00 UTC
│   │   └── backup.py                     # Täglich 04:00 UTC
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── trades.py                     # Journal, Drilldown, Tagging, Facetten, Kalender
│   │   ├── strategies.py                 # Strategy CRUD, Review, Status, Horizon
│   │   ├── approvals.py                  # Proposal-Dashboard, Risk-Gate, Approve/Reject
│   │   ├── trends.py                     # Gordon-Diff, HOT-Pick → Strategie-Kandidat
│   │   ├── regime.py                     # Regime-Snapshot, Kill-Switch, Override
│   │   └── settings.py                   # Health, Taxonomie, Broker-Status, Contract-Test
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── logging.py                    # Request-Logging (Method, Path, Status, Duration)
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── design-tokens.css         # CSS Custom Properties
│   │   │   └── main.css                  # Tailwind-Output (generiert)
│   │   └── js/
│   │       ├── htmx.min.js              # HTMX (lokal)
│   │       ├── alpine.min.js            # Alpine.js (lokal)
│   │       └── lightweight-charts.standalone.production.js  # OHLC-Charts (lokal)
│   │
│   └── templates/
│       ├── components/
│       │   ├── stat_card.html
│       │   ├── trade_row.html
│       │   ├── facet_chip.html
│       │   ├── facet_bar.html
│       │   ├── sparkline.html
│       │   ├── status_badge.html
│       │   ├── staleness_banner.html
│       │   ├── trigger_spec_readable.html
│       │   ├── calendar_cell.html
│       │   ├── proposal_viewport.html
│       │   ├── trade_chart.html           # lightweight-charts OHLC mit Markern
│       │   ├── quick_order_form.html      # IB Quick-Order Inline-Form (FR53)
│       │   ├── quick_order_preview.html   # Bestätigungs-Zusammenfassung (FR54)
│       │   ├── command_palette.html
│       │   ├── query_prose.html
│       │   └── toast.html
│       ├── layouts/
│       │   ├── base.html                 # Top-Bar, Navigation, Health-Status, JS
│       │   └── dense.html                # Erweiterung für dichte Views
│       └── views/
│           ├── trades/
│           │   ├── list.html
│           │   ├── _list_fragment.html
│           │   ├── _aggregation_fragment.html
│           │   ├── _detail_fragment.html
│           │   ├── _tag_form_fragment.html
│           │   └── calendar.html
│           ├── strategies/
│           │   ├── list.html
│           │   ├── _list_fragment.html
│           │   ├── detail.html
│           │   └── _notes_fragment.html
│           ├── approvals/
│           │   ├── dashboard.html
│           │   ├── _proposal_fragment.html
│           │   └── _status_fragment.html
│           ├── trends/
│           │   ├── gordon_diff.html
│           │   └── _candidate_form_fragment.html
│           ├── regime/
│           │   └── overview.html
│           └── settings/
│               └── health.html
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── services/
│   │   │   ├── test_metrics_service.py
│   │   │   ├── test_trade_service.py
│   │   │   ├── test_order_service.py     # Quick-Order Validation, Auto-Tagging (FR53–58)
│   │   │   ├── test_approval_service.py
│   │   │   └── test_regime_service.py
│   │   └── models/
│   │       ├── test_trigger_spec.py
│   │       ├── test_order.py             # QuickOrderRequest, BracketOrderSpec
│   │       └── test_taxonomy.py
│   ├── integration/
│   │   ├── db/
│   │   │   ├── test_migrations.py
│   │   │   ├── test_trade_queries.py
│   │   │   └── test_audit_log.py
│   │   └── clients/
│   │       ├── test_mcp_contract.py
│   │       └── test_ib_order_idempotency.py  # Replay mit identischem order_ref (NFR-R3a, manuell triggerbar gegen IB Paper)
│   └── fixtures/
│       ├── sample_trades.py
│       ├── sample_flex_query.xml
│       └── sample_mcp_responses.json
│
└── data/                                 # Docker Volume Mounts (nicht in Git)
    ├── logs/
    ├── ohlc-cache/                        # Gecachte OHLC-Candle-Daten (optional)
    ├── mcp-snapshots/
    └── backups/
```

### Architectural Boundaries

**API Boundaries (Router → FR-Mapping):**

| Route-Gruppe | FR-Abdeckung | Verantwortung |
|---|---|---|
| `routers/trades.py` | FR1–13c, FR14–18b, **FR53–58** | Journal, Drilldown, Tagging, Facetten, Kalender, **Quick-Order-Formular und Submit** |
| `routers/strategies.py` | FR33–40 | Strategy CRUD, Review, Status, Horizon-Gruppierung |
| `routers/approvals.py` | FR25–32 | Proposal-Dashboard, Risk-Gate, Approve/Reject |
| `routers/trends.py` | FR46–48 | Gordon-Diff, HOT-Pick → Strategie-Kandidat |
| `routers/regime.py` | FR41–45 | Regime-Snapshot, Kill-Switch, Override |
| `routers/settings.py` | FR50, FR24 | Health, Contract-Test, Taxonomie |

**Service Boundaries:**

| Service | Verantwortung | Abhängigkeiten |
|---|---|---|
| `trade_service` | Sync, Reconciliation, Tagging, MAE/MFE | `db/queries/trades`, `clients/ib`, `clients/mcp` |
| `order_service` | **Quick-Order-Validation, Bracket-Order-Submission, Status-Tracking, Auto-Tagging (FR53–58)** | `db/queries/trades`, `clients/ib`, `taxonomy_service` |
| `strategy_service` | CRUD, Status, Metriken | `db/queries/strategies`, `metrics_service` |
| `approval_service` | State-Machine, Risk-Gate, Order-Routing (cTrader-Bot) | `db/queries/approvals`, `clients/mcp`, `clients/ctrader`, `audit_service` |
| `regime_service` | Kill-Switch (Bot-only), Snapshots | `db/queries/regime`, `clients/mcp` |
| `audit_service` | Append-Only Inserts | `db/queries/approvals` |
| `taxonomy_service` | YAML → Dropdown-Daten | `taxonomy.yaml` (Filesystem) |
| `metrics_service` | P&L, Expectancy, R-Multiple, Drawdown | Keine — pure Funktionen |

**Data Boundaries:**

| Tabelle | Schreiber | Leser |
|---|---|---|
| `trades` | `trade_service`, **`order_service`** | `routers/trades`, `strategy_service`, `metrics_service` |
| `strategies` | `strategy_service`, `regime_service` | `routers/strategies`, `approval_service` |
| `proposals` | `approval_service` | `routers/approvals` |
| `approval_audit_log` | `audit_service` (append-only) | `routers/approvals` (read-only) |
| `regime_snapshots` | `regime_service` (Job) | `routers/regime`, `approval_service` |
| `gordon_trend_snapshots` | `gordon_weekly` Job | `routers/trends` |

**Hinweis zur `trades`-Tabelle:** Sowohl `trade_service` (für synced IB-Trades und cTrader-Bot-Trades) als auch `order_service` (für IB-Quick-Orders) schreiben in dieselbe Tabelle. Zur Unterscheidung dient `order_status` (`synced` für trade_service-Inserts, `submitted`/`filled`/`rejected`/etc. für order_service). Beim Fill eines Quick-Order-Trades macht der Live-Sync (`trade_service`) ein `UPDATE` auf die existierende Row, gemerged über `order_ref` — kein neuer INSERT.

### Data Flow

```
                  ┌─── Chef klickt "Quick Order" im Journal/Watchlist ───┐
                  │                                                       │
                  ▼                                                       │
       routers/trades.py                                                  │
       POST /trades/quick-order                                           │
                  │                                                       │
                  ▼                                                       │
          order_service.py ──── taxonomy_service (Auto-Tagging)           │
                  │                                                       │
                  ▼                                                       │
          clients/ib.py.place_bracket_order()                             │
          (Parent Limit + Child Trailing Stop, atomar via transmit-Flag)  │
                  │                                                       │
                  ▼                                                       │
              ┌───────┐                                                   │
              │  IB   │ ◄─── Trailing Stop wird serverseitig verwaltet    │
              └───┬───┘                                                   │
                  │                                                       │
                  ├─ permId/Status zurück                                 │
                  ▼                                                       │
          db/queries/trades.update_order_status()                         │
                  │                                                       │
                  └──── 'submitted' → 'filled' (via Live-Sync Merge) ─────┘

IB TWS/Gateway                 cTrader Demo                fundamental MCP
     │                              │                           │
     ├─ Live (ib_async) ──┐         │                           │
     └─ Flex XML (Nightly)─┤    OpenApiPy ──┐         HTTP/SSE ─┤
                           │                │                    │
                     clients/ib.py    clients/ctrader.py   clients/mcp.py
                           │                │              │    │    │
                           └────────┬───────┘          Viktor Satoshi Gordon
                                    │                  Rita  Cassandra
                              trade_service ◄──── mcp (Fundamental)
                                    │
                              ┌─────┴─────┐
                         db/queries    metrics_service
                              │              │
                         PostgreSQL    Pure Berechnung
                              │
                    ┌─────────┼──────────┐
               trades    strategies    proposals
                  ▲           │
                  │           ▼
          (geteilte Tabelle)  routers/
                              strategies
                                  │
                    ┌─────────┴──────────┐
              routers/     routers/     routers/
              trades    strategies    approvals
              (inkl. Quick-Order)
                    │         │           │
              Jinja2 Templates (HTMX Fragments + quick_order_form.html)
                              │
                         Browser (Chef)
```

**Quick-Order-Flow im Detail:** Der Quick-Order-Pfad ist eine separate Schreibroute in dieselbe `trades`-Tabelle. Bei Submission entsteht eine Row mit `order_status='submitted'`, `order_ref` als UUID-Idempotenz-Key, und vollständig befülltem `trigger_spec` (Auto-Tagging). Beim Fill aktualisiert der Live-Sync-Loop (`trade_service`, der über `ib_async`-Events läuft) die existierende Row über `WHERE order_ref = ?` — er erkennt die Row als "schon eingetragen" und führt ein UPDATE statt INSERT durch. Bei Rejection bleibt die Row mit `order_status='rejected'` als Provenance-Eintrag stehen.

### Development Workflow Integration

**Dev-Mode:**
```bash
docker compose up -d postgres
uv run python -m app.db.migrate
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
uv run pytailwindcss --watch &
```

**Production (Docker):**
```bash
docker compose up -d
```

**Tests:**
```bash
uv run pytest tests/unit/
uv run pytest tests/integration/
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** Alle Technologie-Entscheidungen sind konfliktfrei. Python 3.12 + FastAPI + asyncpg + PostgreSQL ist ein bewährter Async-Stack. HTMX + Jinja2 + Tailwind (via pytailwindcss) braucht keinen Node-Build. APScheduler integriert sich über FastAPI-Lifespan. MCP HTTP/SSE über httpx ist nativ unterstützt. Docker Compose ist Standard für PostgreSQL + App.

**Pattern Consistency:** snake_case durchgängig (Python, SQL, JSON-Keys, Query-Parameter). Router → Service → DB/Client Abhängigkeitsrichtung widerspruchsfrei. Fragment-Prefix `_` konsistent. Pydantic an allen Grenzen kompatibel mit asyncpg dict-Output.

**Structure Alignment:** Projektstruktur spiegelt alle Entscheidungen wider. Jeder Service hat korrespondierende Queries, Modelle und Router. Integration-Punkte in `clients/` isoliert.

**Hinweis:** PRD wurde am 2026-04-13 vollständig auf PostgreSQL umgestellt (Commit `417a003`). Architekturdokument und PRD sind jetzt konsistent.

### Requirements Coverage Validation ✅

**Alle 58 FRs architektonisch abgedeckt:**

| Capability Area | FRs | Abdeckung |
|---|---|---|
| Trade Data Ingestion | FR1–7 | `clients/ib.py`, `clients/ctrader.py`, `jobs/flex_nightly.py`, `trade_service.py` |
| Trade Journal & Drilldown | FR8–13c | `routers/trades.py`, `templates/views/trades/`, `metrics_service.py` |
| Taxonomy & Provenance | FR14–18b | `taxonomy_service.py`, `models/trigger_spec.py`, `trigger_spec_readable.html` |
| Fundamental Intelligence | FR19–24 | `clients/mcp.py`, `staleness_banner.html`, `jobs/contract_test.py` |
| Approval Pipeline | FR25–32 | `approval_service.py` (State-Machine), `proposal_viewport.html`, DB-Trigger |
| Strategy Management | FR33–40 | `strategy_service.py`, `routers/strategies.py`, `metrics_service.py` |
| Regime & Trends | FR41–48 | `regime_service.py`, `jobs/gordon_weekly.py`, `jobs/regime_snapshot.py` |
| Operations & Health | FR49–52 | `jobs/scheduler.py`, `routers/settings.py`, `db/migrate.py`, `jobs/backup.py` |
| **IB Quick-Order** (Aktien + Trailing Stop) | **FR53–58** | **`order_service.py`, `clients/ib.py` (Bracket-Order-Erweiterung), `routers/trades.py` (Quick-Order-Endpoint), `templates/components/quick_order_form.html`, `models/order.py`** |

**Alle NFR-Kategorien adressiert:**

| NFR | Umsetzung |
|---|---|
| Performance (P1–P6) | PostgreSQL GIN-Indizes, asyncpg Binary-Protocol, HTMX-Fragment-Updates |
| Security (S1–S5) | Localhost-only, .env-Secrets, Append-Only-DB-Trigger, keine Telemetrie |
| Reliability (R1–R8) | Composite-Keys, Idempotente Upserts, Dual-Source-Recon, Graceful Degradation |
| Integration (I1–I6) | MCP-Timeout ≤10s, TTL-Cache, Contract-Test, Hybrid MAE/MFE |
| Maintainability (M1–M6) | ruff, pytest, structlog, versionierte Migrations, Single-Process |

### Implementation Readiness Validation ✅

**Decision Completeness:** 9 Entscheidungen dokumentiert mit Begründung (inkl. IB Quick-Order vom 2026-04-13). Deferred Decisions explizit benannt. ✅
**Structure Completeness:** ~80 Dateien/Verzeichnisse, FR-Mapping, Data Flow, Dev-Workflow. ✅
**Pattern Completeness:** 7 Naming-Bereiche, 8 Enforcement-Regeln, Code-Beispiele, State-Machine. ✅

### Gap Analysis

**Kritische Gaps: Keine.**

**Wichtige Gaps (Woche-0-Verifikation):**

1. **MCP HTTP/SSE-Transport:** Ob `fundamental` bereits HTTP/SSE unterstützt oder nur stdio, muss im Woche-0-Handshake-Test geklärt werden. Falls nur stdio: Wrapper-Proxy oder Transport-Umstellung nötig.
2. **PostgreSQL-Schema-DDL:** Detailliertes Tabellen-Schema für `001_initial_schema.sql` in Woche 0/1 — PRD liefert Spalten-Skizze, Architektur die Konventionen.
3. ~~PRD/Brief DuckDB-Referenzen~~ — **Erledigt am 2026-04-13** (PRD-Cleanup-Commit `417a003`). PRD ist jetzt vollständig PostgreSQL-konsistent.

**Nice-to-Have (spätere Iteration):**
- Command Palette Index-Endpoint (Detail-Design Woche 6)
- `trigger_spec` JSONB-Schema-Vertrag (abgeleitet aus `fundamental/trigger-evaluator.ts` in Woche 0)

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Projekt-Kontext analysiert (58 FRs, NFRs, UX-Spec)
- [x] Komplexität bewertet (Medium-High)
- [x] Technische Constraints identifiziert
- [x] Cross-Cutting Concerns kartiert (6 identifiziert)

**✅ Architectural Decisions**
- [x] 7 kritische/wichtige Entscheidungen dokumentiert
- [x] Technologie-Stack vollständig spezifiziert
- [x] Integrations-Patterns definiert
- [x] Performance-Considerations adressiert

**✅ Implementation Patterns**
- [x] Naming-Konventionen für 7 Bereiche
- [x] 8 Enforcement-Regeln für AI-Agents
- [x] Abhängigkeitsrichtung definiert
- [x] Error-Handling-Hierarchie dokumentiert

**✅ Project Structure**
- [x] Vollständiger Dateibaum (~80 Dateien)
- [x] Architektonische Boundaries definiert
- [x] FR-zu-Datei-Mapping komplett
- [x] Data Flow dokumentiert

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Vollständige FR-Abdeckung ohne Lücken
- Klare Separation of Concerns (Router → Service → DB/Client)
- PostgreSQL JSONB + GIN-Index als starke Basis für Trigger-Provenance-Queries
- Graceful Degradation als durchgängiges Pattern
- Append-Only Audit-Log auf DB-Ebene erzwungen
- Docker Compose für konsistentes Deployment

**Areas for Future Enhancement:**
- Redis-Cache falls In-Memory bei Skalierung nicht reicht
- PostgreSQL-Schema-Optimierung nach realen Query-Patterns (nach Woche 4)
- Monitoring/Alerting über UI-Health-Widget hinaus (Phase 2)

### Implementation Handoff

**AI-Agent-Guidelines:**
- Architektur-Dokument hat Vorrang vor PRD und Brief bei Widersprüchen (PRD und Architektur sind seit 2026-04-13 konsistent für Storage und Chart-Rendering; bei zukünftigen Drifts gilt Architektur > PRD > Brief)
- Alle 8 Enforcement-Regeln sind bindend
- Naming-Konventionen, Abhängigkeitsrichtung und Pattern-Examples sind Referenz

**Erste Implementation-Priorität (Woche 0):**
1. `uv init` + Dependencies + Docker Compose + PostgreSQL
2. `asyncpg` Pool + Migrations-Runner + `001_initial_schema.sql`
3. MCP HTTP/SSE Handshake-Test + Contract-Snapshot einfrieren
4. FastAPI-Skelett mit "Hello World"-MCP-Call-Seite
5. Tailwind-Build-Pipeline (`pytailwindcss`)
