# Story 1.2: Migrations-Framework & Basis-Infrastruktur

Status: ready-for-dev

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

- [ ] Task 1: Migrations-Runner implementieren (AC: 1, 3)
  - [ ] `app/db/migrate.py` mit Custom-Runner
  - [ ] Liest alle `.sql`-Files aus `migrations/` sortiert
  - [ ] Tracking via `schema_migrations` Tabelle (version, applied_at)
  - [ ] Skip bereits angewendeter Migrationen
- [ ] Task 2: 001_initial_schema.sql erstellen (AC: 2)
  - [ ] `CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT NOW())`
  - [ ] `CREATE TYPE trade_source AS ENUM ('ib', 'ctrader')`
  - [ ] `CREATE TYPE trade_side AS ENUM ('buy', 'sell', 'short', 'cover')`
  - [ ] `CREATE TYPE order_status AS ENUM ('submitted', 'filled', 'partial', 'rejected', 'cancelled')`
  - [ ] `CREATE TYPE horizon_type AS ENUM ('intraday', 'swing', 'position')`
  - [ ] `CREATE TYPE strategy_status AS ENUM ('active', 'paused', 'retired')`
  - [ ] `CREATE TYPE risk_gate_result AS ENUM ('green', 'yellow', 'red')`
  - [ ] Alle mit `IF NOT EXISTS` wo moeglich (idempotent)
- [ ] Task 3: Migrations-Runner in FastAPI-Lifespan integrieren (AC: 1)
  - [ ] Migration-Check bei App-Start im Lifespan-Context
  - [ ] Logging jedes angewendeten Migrations-Schritts via structlog
- [ ] Task 4: Idempotenz-Test (AC: 3, 4)
  - [ ] Integration-Test: `migrate` zweimal ausfuehren
  - [ ] Vergleich: DB-Zustand identisch
  - [ ] Assert: `schema_migrations` keine Duplikate

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

### Debug Log References

### Completion Notes List

### File List
