# ctrader Database Recovery

Story 11.3 / FR52 / NFR-R5 — step-by-step procedure to restore a
PostgreSQL backup produced by the daily `db_backup` scheduled job.

## Voraussetzungen

- PostgreSQL läuft und ist erreichbar (Host, Port, Superuser-Zugang)
- Backup-File `ctrader-YYYY-MM-DD.sql.gz` aus `data/backups/`
- ctrader App ist **gestoppt** während der Recovery
  (`docker compose stop ctrader`)
- Operator hat eine Kopie der `.env` (für `DATABASE_URL`)

## Schritte

### 1. Backup auswählen und entpacken

```bash
# Neuestes Backup identifizieren
ls -lt data/backups/ctrader-*.sql.gz | head -1

# Entpacken (in ein Scratch-Verzeichnis, nicht überschreiben)
gunzip -k data/backups/ctrader-2026-04-12.sql.gz
# → data/backups/ctrader-2026-04-12.sql
```

### 2. Downtime ankündigen / App stoppen

```bash
docker compose stop ctrader
```

Das Stop-Signal flusht alle offenen asyncpg-Verbindungen. **Erst
weitermachen**, wenn `docker compose ps ctrader` den Container als
`Exited` zeigt.

### 3. Bestehende Datenbank droppen (ACHTUNG: destruktiv)

```bash
# Connection-Kontext aus .env ziehen
source .env

# Drop + re-create (in einer Admin-Session)
psql "$DATABASE_URL" -c "DROP DATABASE ctrader"
psql "$DATABASE_URL" -c "CREATE DATABASE ctrader OWNER ctrader"
```

> ⚠ **Kein Rückweg ab hier.** Wenn irgendein Schritt ab diesem Punkt
> fehlschlägt, ist die alte DB unwiderruflich weg — nur das Backup
> bringt sie zurück. Mach einen Dry-Run auf einer Test-Instanz, bevor
> du das auf dem echten System machst.

### 4. Backup einspielen

```bash
psql "$DATABASE_URL" -f data/backups/ctrader-2026-04-12.sql
```

`psql` sollte ohne Fehler durchlaufen. Migrationen müssen **nicht**
neu angewandt werden — der Dump enthält das vollständige Schema.

### 5. ctrader App neu starten

```bash
docker compose start ctrader
docker compose logs -f ctrader
```

Warte auf `{"event": "Application startup complete."}`.

### 6. Integritäts-Check

```bash
# Health-API pingen
curl -sS http://127.0.0.1:8000/api/health | jq

# Anzahl Trades als sanity check
docker compose exec postgres psql -U ctrader -d ctrader \
    -c "SELECT COUNT(*) FROM trades"
```

Die Zahlen müssen zum Snapshot-Zeitpunkt des Backups passen. Wenn
nicht: **sofort stoppen** und manuell forensieren — niemals blind
weitermachen.

### 7. Aufräumen

```bash
# Entpacktes SQL-File löschen
rm data/backups/ctrader-2026-04-12.sql
```

## Geschätzte Downtime

| Backup-Größe | Dauer   |
|--------------|---------|
| < 100 MB     | 2–5 min |
| 100 MB – 1 GB | 10–30 min |
| > 1 GB       | evaluiere pg_restore statt psql |

## Wenn etwas schiefgeht

- **`DROP DATABASE ctrader` schlägt fehl wegen aktiver Connections**:
  → `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'ctrader'`
- **`psql -f ...` schlägt bei einem Statement fehl**: den Dump
  **manuell** öffnen und den problematischen Block prüfen. `\set ON_ERROR_STOP on`
  hätte den Load abgebrochen, ohne das hier bist du bei einem partiellen
  Restore — das ist ein manueller Rescue-Job.
- **App startet nicht**: check `docker compose logs ctrader`; häufig
  sind Environment-Variablen aus `.env` nicht mehr gesetzt.

## Test-Recovery

Chef sollte diese Prozedur **mindestens einmal** im Laufe des
MVP-8-Wochen-Zyklus auf einer Test-DB durchspielen, um sicherzustellen
dass die Backups wirklich restaurierbar sind (NFR-R5). Ein nie getestetes
Backup ist ein Schrödinger-Backup.
