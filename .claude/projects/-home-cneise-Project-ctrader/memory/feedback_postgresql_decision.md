---
name: PostgreSQL statt DuckDB
description: Chef hat am 2026-04-12 die Locked Decision von DuckDB auf PostgreSQL geändert — nicht erneut hinterfragen
type: feedback
---

Storage-Entscheidung wurde bewusst von DuckDB auf PostgreSQL geändert.

**Why:** Automatisiertes Daytrading mit ~10 Trades/Tag erwartet, Concurrent-Write-Sicherheit bei parallelem Live-Sync + Bot-Execution + Scheduled Jobs, Migrationsaufwand in Zukunft vermeiden. Chef betreibt bereits mehrere PostgreSQL-Instanzen — Ops-Overhead ist kein Problem.

**How to apply:** PostgreSQL als Storage planen, nicht DuckDB. CLAUDE.md ist bereits aktualisiert. PRD und Brief referenzieren noch DuckDB — das Architektur-Dokument überschreibt diese Stellen. Keine erneute Diskussion ob DuckDB besser wäre.
