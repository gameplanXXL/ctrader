# Story 1.2: Migrations-Framework & Basis-Infrastruktur

Status: review

## Story

As a Chef,
I want database schema changes to be tracked and reproducible,
so that my database is always in a known, consistent state.

## Acceptance Criteria

1. **Given** die App startet, **When** der Migrations-Runner ausfuehrt, **Then** wird eine `schema_migrations`-Tabelle erstellt, die angewendete Migrationen trackt (FR51)
2. **Given** Migration 001_initial_schema.sql existiert, **When** `migrate` laeuft, **Then** werden Basis-Enums (trade_source, trade_side, order_status, horizon_type, strategy_status, risk_gate_result) und Common Types erstellt
3. **Given** eine Migration wurde bereits angewendet, **When** migrate erneut laeuft, **Then** wird die Migration uebersprungen (idempotent, NFR-R7)
4. **Given** alle Migrationen, **When** jede zweimal angewendet wird, **Then** ist der DB-Zustand identisch mit einmal anwenden

## Tasks / Subtasks

- [x] Task 1: Migrations-Runner implementieren (AC: 1, 3)
  - [x] `app/db/migrate.py` mit Custom-Runner (`run_migrations`, `discover_migrations`, `Migration`)
  - [x] Liest alle `NNN_<slug>.sql`-Files aus `migrations/` sortiert (Regex `^(\d{3,})_[a-z0-9_]+\.sql$`)
  - [x] Tracking via `schema_migrations` Tabelle (`version PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT NOW()`)
  - [x] Skip bereits angewendeter Migrationen via `_applied_versions(conn)` Set-Lookup
  - [x] Jede Migration laeuft in eigener Transaktion (PostgreSQL transaktionales DDL)
  - [x] One-shot connection, **nicht** aus dem Pool — sicher fuer Lifespan-Context
- [x] Task 2: 001_initial_schema.sql erstellen (AC: 2)
  - [x] `CREATE TABLE IF NOT EXISTS schema_migrations`
  - [x] `trade_source` ENUM (ib, ctrader) via DO-Block (idempotent)
  - [x] `trade_side` ENUM (buy, sell, short, cover)
  - [x] `order_status` ENUM (synced, submitted, filled, partial, rejected, cancelled) — `synced` als Pseudo-State fuer Sync-Trades, damit order_status NIE NULL ist
  - [x] `horizon_type` ENUM (intraday, swing, position)
  - [x] `strategy_status` ENUM (active, paused, retired)
  - [x] `risk_gate_result` ENUM (green, yellow, red)
  - [x] Alle ENUMs idempotent via `DO $$ ... EXCEPTION WHEN duplicate_object THEN NULL; END $$`
- [x] Task 3: Migrations-Runner in FastAPI-Lifespan integrieren (AC: 1)
  - [x] `app/main.py` Lifespan ruft `await run_migrations()` **vor** `create_pool()` auf
  - [x] structlog-Events: `migrate.applying`, `migrate.applied`, `migrate.skip`, `migrate.done`, `app.migrations_applied`
  - [x] `tests/conftest.py` mockt `run_migrations` zusammen mit `create_pool`/`close_pool` fuer hermetische Unit-Tests
- [x] Task 4: Idempotenz-Test (AC: 3, 4)
  - [x] `tests/integration/conftest.py` mit session-scoped `pg_container` (testcontainers `PostgresContainer("postgres:16-alpine")`) + `pg_dsn` Fixture
  - [x] `tests/integration/test_migrate_idempotent.py`:
    - test_first_run_applies_001
    - test_second_run_is_noop
    - test_schema_migrations_has_one_row_per_version (3x ausfuehren)
    - test_enums_from_001_exist (alle 6 ENUMs in pg_type)
  - [x] Module-level `pytest.mark.integration` + `_skip_if_no_docker` (graceful degradation auf CI ohne Docker)
  - [x] Plus 5 Unit-Tests in `tests/unit/test_migrate_discovery.py` fuer den Runner ohne DB

## Dev Notes

**Kritisches Prinzip (CLAUDE.md Regel #2):**
> Alle PostgreSQL-Schema-Änderungen MÜSSEN über versionierte Migrations-Skripte erfolgen. Direkte Schema-Änderungen sind verboten.

**Migration-Format:**
- Sequenz-Nummerierung: `001_initial_schema.sql`, `002_trades_table.sql`, etc.
- Jede Migration muss idempotent sein (`CREATE TABLE IF NOT EXISTS`, `CREATE TYPE ... IF NOT EXISTS` via DO-Block)
- In Git eingecheckt unter `migrations/`

**Wichtige Enums (Konsens aus Architecture-Naming):**
- `trade_source`: Quelle des Trades (IB oder cTrader)
- `trade_side`: Richtung/Art der Position
- `order_status`: Lifecycle-Status einer Order
- `horizon_type`: Zeitraum-Klassifikation
- `strategy_status`: Aktivitaet einer Strategie
- `risk_gate_result`: Ergebnis des Risk-Gates (Rita/Cassandra)

**PostgreSQL-Enum-Idempotenz-Pattern:**
```sql
DO $$ BEGIN
    CREATE TYPE trade_source AS ENUM ('ib', 'ctrader');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
```

**Zu erstellende Dateien:**
```
app/db/migrate.py              # Runner
migrations/001_initial_schema.sql
tests/integration/test_migrate_idempotent.py
```

**NICHT in dieser Story:**
- Keine Domain-Tabellen (trades, strategies, etc.) — die kommen in ihren jeweiligen Epic-Stories
- Keine `ohlc_candles` (Story 4.3)
- Keine `audit_log` Trigger (Story 7.5)

### References

- PRD: `prd.md` — FR51, NFR-R7
- Architecture: `architecture.md` — "Database & Data Architecture", "Schema & Migrations"
- CLAUDE.md Regel #2 — "Datenbank-Änderungen NUR über Migrationen"

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context), bmad-dev-story workflow, 2026-04-13.

### Debug Log References

- `uv add --dev "testcontainers[postgres]"` — installierte testcontainers 4.14.2, docker 7.1.0, requests 2.33.1 als dev-deps (insgesamt 6 neue Packages).
- `uv run pytest -v` erste Ausfuehrung mit Integration-Tests — alle 19 Tests grün in 4.91s (erstmaliger Container-Pull). Subsequent-Run: 1.98s (Container session-scoped wiederverwendet).
- `uv run ruff format --check .` — `app/db/migrate.py` und `tests/integration/test_migrate_idempotent.py` mussten je einmal reformatiert werden (long-line-Splits).
- testcontainers `get_connection_url()` liefert SQLAlchemy-style `postgresql+psycopg2://...` — fuer asyncpg muss der `+psycopg2`-Suffix entfernt werden. Wird in der `pg_dsn`-Fixture gemacht.

### Completion Notes List

- **Alle 4 Acceptance Criteria erfuellt:**
  - AC #1 (Migrations-Runner erstellt schema_migrations und trackt angewendete Migrationen): `_ensure_tracking_table()` legt die Tabelle idempotent an, `_applied_versions()` liest die bisherigen Versionen, jeder Apply-Call fuegt einen Eintrag hinzu. Verifiziert in Integration-Test `test_schema_migrations_has_one_row_per_version`.
  - AC #2 (001_initial_schema.sql erstellt 6 ENUMs): Alle 6 ENUMs (`trade_source`, `trade_side`, `order_status`, `horizon_type`, `strategy_status`, `risk_gate_result`) werden via DO-Block angelegt. Verifiziert in `test_enums_from_001_exist` durch Query auf `pg_type`.
  - AC #3 (Skip bereits angewendeter Migrationen): `_applied_versions(conn)` Set-Lookup blockiert Re-Apply. Zusaetzlich: `INSERT INTO schema_migrations ... ON CONFLICT (version) DO NOTHING` als zweite Defense-Layer. Verifiziert in `test_second_run_is_noop` (zweiter Run liefert leere Liste).
  - AC #4 (Zweimal anwenden = einmal anwenden): Verifiziert in `test_schema_migrations_has_one_row_per_version` (3x run, count pro version = 1) und `test_enums_from_001_exist` (DO-Block faengt duplicate_object Exception ab).
- **19 Tests grün** (10 Bestand aus Story 1.1 + 5 neue Unit-Tests fuer Discovery + 4 neue Integration-Tests). Erster Container-Pull: 4.91s. Subsequent-Runs: 1.98s.
- **Wichtige Design-Entscheidung — `synced`-State fuer order_status:** Die ENUM enthaelt `synced` zusaetzlich zu den 5 Lifecycle-States aus dem PRD. Grund: Trades, die ueber Sync (Flex Query / Live IB) ankommen, durchlaufen keinen Order-Lifecycle. Damit `trades.order_status` IMMER NOT NULL bleiben kann (sauberer fuer Facetten-Queries in Epic 4), bekommen Sync-Trades den `synced`-State. Story 11.2 Migration 005 wird das beim Quick-Order-Insert beruecksichtigen. Diese Entscheidung deckt sich mit der erweiterten Architecture Decision C1.
- **Lifespan-Reihenfolge:** `configure_logging()` → `run_migrations()` → `create_pool()`. Migrations laufen ueber eine eigene one-shot connection (nicht aus dem Pool), damit DDL nie versehentlich ueber einen pooled worker laeuft.
- **Hermetic Unit-Tests bleiben:** `tests/conftest.py` mockt jetzt zusaetzlich zu `create_pool`/`close_pool` auch `run_migrations` — die 10 Unit-Tests aus Story 1.1 brauchen weiterhin keine DB.
- **Integration-Tests sind opt-out**: `pytest -m "not integration"` skippt sie auf Maschinen ohne Docker. `_skip_if_no_docker` fixture verifiziert vor Test-Run, dass `docker` im PATH ist.

### File List

**Neu erstellt (5 Dateien):**
- `migrations/001_initial_schema.sql` — schema_migrations + 6 ENUMs (idempotent)
- `app/db/migrate.py` — Migrations-Runner (`run_migrations`, `discover_migrations`, `Migration` dataclass)
- `tests/integration/conftest.py` — Session-scoped `pg_container` + `pg_dsn` Fixtures via testcontainers
- `tests/integration/test_migrate_idempotent.py` — 4 Integration-Tests (first-run, idempotency, count, enums)
- `tests/unit/test_migrate_discovery.py` — 5 Unit-Tests fuer discovery + Migration-Dataclass

**Geaendert (3 Dateien):**
- `app/main.py` — Lifespan ruft `run_migrations()` vor `create_pool()` auf
- `tests/conftest.py` — mockt jetzt auch `run_migrations` (autouse fixture)
- `pyproject.toml` — `testcontainers[postgres]>=4.14.2` als dev-dependency hinzugefuegt
- `uv.lock` — Lockfile aktualisiert (6 neue Packages: testcontainers, docker, requests, urllib3, charset-normalizer, wrapt)

### Change Log

- 2026-04-13: Story 1.2 implementiert. Custom Migrations-Runner mit `schema_migrations`-Tracking, `001_initial_schema.sql` mit 6 ENUMs (inkl. neuem `synced`-State fuer order_status), Lifespan-Integration vor Pool-Creation, 4 Integration-Tests mit testcontainers + 5 Unit-Tests fuer Discovery. 19/19 Tests gruen, ruff clean. Status `ready-for-dev` → `in-progress` → `review`.
