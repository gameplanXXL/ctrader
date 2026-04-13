# CLAUDE.md — ctrader

## Projektbeschreibung

**ctrader** ist eine persönliche Trading-Plattform für Christian ("Chef"). Sie vereint ein Trade-Journal für manuelles Aktien- und Options-Trading bei Interactive Brokers mit einer human-gated AI-Agent-Farm für Crypto- und CFD-Trading über cTrader — beides in einer UI, mit dem Anspruch, dass für jeden einzelnen Trade *Gewinn* und *Auslöser* vollständig nachvollziehbar sind.

Das Projekt ist der dritte Anlauf nach zwei abgebrochenen Vorversuchen (archiviert unter `/home/cneise/Project/ALT/ctrader` und `/home/cneise/Project/ALT/ctrader2`). Beide Vorprojekte sind an Scope-Explosion gescheitert — ctrader adressiert das mit expliziter Descope-Ladder, wöchentlichen Checkpoints und einem terminalen Abbruch-Kriterium.

**Maßgebende Dokumente:**
- `_bmad-output/planning-artifacts/product-brief-ctrader.md` — Executive Brief
- `_bmad-output/planning-artifacts/product-brief-ctrader-distillate.md` — Detail Pack für PRD- und Architektur-Arbeit

## Kritische Regeln

### 1. IMMER committen und pushen

**Alle Änderungen MÜSSEN sofort committed und gepusht werden.**

- Nach jeder abgeschlossenen Änderung: `git add <files>`, `git commit`, `git push`
- Keine Änderungen dürfen nur lokal verbleiben
- Commit-Messages müssen aussagekräftig sein und beschreiben, **was** und **warum** geändert wurde
- Vor dem Beginn neuer Arbeiten: `git pull` ausführen, um auf dem aktuellen Stand zu sein
- Für größere Features: Feature-Branches verwenden und über Pull Requests mergen
- `.env` NIEMALS committen — steht in `.gitignore` und bleibt dort

### 2. Datenbank-Änderungen NUR über Migrationen

**Alle DuckDB-Schema-Änderungen MÜSSEN über versionierte Migrations-Skripte erfolgen. Direkte Schema-Änderungen sind verboten.**

- Jede Schema-Änderung (Tabellen, Spalten, Indizes, Constraints) erfordert eine Migration
- Migrationen müssen idempotent und möglichst reversibel sein
- Migrationen werden versioniert und in Git eingecheckt
- Seed-Daten ebenfalls über Migrationen oder dedizierte Seed-Skripte

### 3. Scope-Disziplin respektieren

ctrader ist bewusst eng geschnitten. Bevor ein neues Feature, eine neue Abhängigkeit oder ein Refactoring vorgeschlagen wird:

- Prüfen, ob es im **MVP-Scope** laut Brief steht (Slice A Wochen 1–4 oder Slice B Wochen 5–8)
- Phase-2-Features werden nicht heimlich in den MVP geschoben — auch nicht als "Architektur muss das vorsehen"
- Die einzige Multi-Agent-Konzession im MVP ist die `agent_id`-Spalte. Sonst YAGNI.
- Bei Engpässen: Descope-Ladder aus dem Brief konsultieren, nicht improvisieren

### 4. Locked Technical Decisions

Folgende Entscheidungen stehen fest und werden **nicht** ohne expliziten Nutzer-Auftrag neu eröffnet:

- **Sprache:** Python 3.12+
- **Dependency-Manager:** `uv`
- **Frontend:** FastAPI + HTMX + Tailwind. Kein Node, kein React, kein eigener Build-Step.
- **Storage:** PostgreSQL (bestehende Instanz, Chef betreibt bereits mehrere). Entscheidung am 2026-04-12 von DuckDB auf PostgreSQL geändert — Gründe: automatisiertes Daytrading mit ~10 Trades/Tag, Concurrent-Write-Sicherheit, Migrationsvermeidung, vorhandene Ops-Erfahrung.
- **Chart-Rendering:** lightweight-charts (TradingView Open-Source, Apache 2.0, 35KB). Dynamische OHLC-Charts mit Entry/Exit-Markern und Indikatoren im Trade-Drilldown. Kein TradingView Widget, kein Plotly, kein mplfinance. Entscheidung am 2026-04-12 — ersetzt Screenshot-Upload (FR13c) durch interaktive Charts.
- **IB-Integration:** `ib_async` (nicht `ib_insync` — unmaintained seit 2023) + Flex Queries für historische Reconciliation.
- **cTrader-Integration:** OpenApiPy (Protobuf), mögliche partielle Wiederverwendung aus `/home/cneise/Project/ALT/ctrader2` nur nach 1-Tages-Spike-Timebox.
- **Fundamental-/News-Layer:** Harte MCP-Dependency auf `/home/cneise/Project/fundamental`. Keine Re-Implementierung.

## Harte Dependency: `fundamental`

ctrader konsumiert das bestehende MCP-Server-Projekt unter `/home/cneise/Project/fundamental` als Client:

- **SFA-Modul** (Stock Fundamental Analysis): Agents **Viktor** (Analyst) + **Rita** (Risk Manager)
- **CFA-Modul** (Crypto Fundamental Analysis): Agents **Satoshi** (Analyst) + **Cassandra** (Risk Manager)
- **Daytrading-Analyst:** **Gordon** liefert wöchentliche Trend-Radar-Berichte
- **MCP-Tools:** `fundamentals`, `price`, `news`, `search`, `crypto`
- **Reusable Libraries** (via MCP): `trigger-evaluator.ts` (JSONB-Schema für Trigger-Specs), `fear-greed-client.ts` (Regime-Kill-Switch), `watchlist-schema.ts`

Vor Beginn von Woche 1 wird ein **versionierter MCP-Contract-Snapshot** eingefroren. Jede Arbeitszeit, die in `fundamental` fließt, läuft gegen das ctrader-8-Wochen-Budget.

Start des MCP-Servers: `cd /home/cneise/Project/fundamental && make start`

## Projektstruktur

```
ctrader/
├── _bmad/                  # BMad-Framework (Module, Agents, Workflows, Tasks)
├── _bmad-output/           # Generierte Artefakte
│   ├── planning-artifacts/ # Product Brief, Distillate, PRD, Epics
│   ├── implementation-artifacts/
│   └── test-artifacts/
├── .claude/                # Claude Code Skills, Agents, Commands
├── docs/                   # Projekt-Dokumentation
├── src/                    # (noch leer — wird in Woche 0 bootstrapped)
├── CLAUDE.md               # Diese Datei
├── .gitignore
└── (Woche 0) pyproject.toml, app/, migrations/, taxonomy.yaml
```

## Umgebung & Sprache

- **Kommunikationssprache:** Deutsch
- **Dokumentationssprache:** Deutsch
- **User:** Christian, adressiert als "Chef"
- **BMad-Konfiguration:** `_bmad/bmm/config.yaml`
- **Skill-Level:** intermediate

## Git-Konventionen

- Commit-Messages auf Deutsch oder Englisch (konsistent bleiben)
- Aussagekräftige Messages: **was** und **warum**, nicht nur **welche Dateien**
- `_bmad-output/planning-artifacts/` wird committed (Briefs, PRDs, Distillates)
- `_bmad-output/implementation-artifacts/` und `_bmad-output/test-artifacts/` nach Bedarf committen
- Keine generierten Build-Artefakte committen (siehe `.gitignore`)
- Keine Secrets, keine `.env`-Dateien, keine API-Keys

## Wichtige Hinweise

- BMad-Agenten und Workflows liegen unter `_bmad/`
- Bei Fragen zum Workflow: `/bmad-help`
- Wöchentlicher Rhythmus und Descope-Ladder stehen im Product Brief und sind **verbindlich**
- Terminal-Kill-Kriterium: Wenn Slice A (Journal + IB) Ende Woche 4 nicht vollständig benutzbar ist, wird ctrader offiziell gestoppt
