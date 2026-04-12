# Story 12.3: Taegliche PostgreSQL-Backups & Recovery

Status: ready-for-dev

## Story

As a Chef,
I want daily database backups with documented recovery,
so that my trading data is protected against data loss.

## Acceptance Criteria

1. **Given** der taegliche Backup-Job (04:00 UTC), **When** ausgefuehrt, **Then** wird ein PostgreSQL-Dump erstellt und im Backup-Verzeichnis gespeichert (FR52)
2. **Given** das neueste Backup, **When** inspiziert, **Then** ist es nicht aelter als 24 Stunden (NFR-R5)
3. **Given** das Health-Widget, **When** geladen, **Then** zeigt es den Zeitstempel des letzten erfolgreichen Backups sichtbar an (NFR-R5)
4. **Given** die Settings-Seite, **When** "Database Backup" geklickt wird, **Then** kann das aktuelle Backup heruntergeladen werden (UX-DR107)
5. **Given** die Recovery-Prozedur, **When** im Project-Knowledge dokumentiert, **Then** beschreibt sie Schritt-fuer-Schritt wie ein Backup wiederhergestellt wird (FR52)

## Tasks / Subtasks

- [ ] Task 1: DB-Backup-Service
  - [ ] `app/services/db_backup.py` — `create_backup()`
  - [ ] Verwendet `pg_dump` subprocess oder asyncpg-COPY
  - [ ] Output: `data/backups/ctrader-YYYY-MM-DD.sql.gz`
- [ ] Task 2: Backup-Job-Registration
  - [ ] In Story 12.1 Scheduler: `db_backup_job`
  - [ ] Cron: daily 04:00 UTC
- [ ] Task 3: Backup-Rotation
  - [ ] Behalte letzte 7 taegliche Backups
  - [ ] Loesche aeltere
- [ ] Task 4: Filesystem-Permissions (NFR-S5)
  - [ ] `data/backups/` mit 0700
  - [ ] Einzelne Backup-Files mit 0600
- [ ] Task 5: Health-Widget-Integration (AC: 3)
  - [ ] Last-Backup-Timestamp in Story 12.2 Health-Widget
- [ ] Task 6: Download-Endpoint (AC: 4)
  - [ ] GET `/settings/backup/download`
  - [ ] Liefert das neueste Backup als file download
  - [ ] Auth: Localhost only (NFR-S2)
- [ ] Task 7: Recovery-Dokumentation
  - [ ] `docs/recovery.md` mit Schritt-fuer-Schritt-Anleitung
  - [ ] `pg_restore` Kommandos
  - [ ] Downtime-Estimation

## Dev Notes

**Backup-Creation via pg_dump:**
```python
import subprocess
from datetime import datetime
from pathlib import Path
import gzip

async def create_backup(db_url: str, backup_dir: Path = Path("data/backups")) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    output_file = backup_dir / f"ctrader-{timestamp}.sql.gz"

    # pg_dump via subprocess
    with gzip.open(output_file, 'wb') as f:
        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            db_url,
            "--format=plain",
            "--no-owner",
            "--no-acl",
            stdout=subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        f.write(stdout)

    # Set restrictive permissions
    output_file.chmod(0o600)
    return output_file
```

**Backup-Rotation:**
```python
def rotate_backups(backup_dir: Path, keep: int = 7):
    backups = sorted(backup_dir.glob("ctrader-*.sql.gz"))
    for old in backups[:-keep]:
        old.unlink()
```

**Recovery-Dokumentation (docs/recovery.md):**
```markdown
# ctrader Database Recovery

## Voraussetzungen
- PostgreSQL laeuft und ist erreichbar
- Backup-File (*.sql.gz) ist verfuegbar

## Schritte

1. **Backup entpacken:**
   ```bash
   gunzip ctrader-2026-04-12.sql.gz
   ```

2. **Bestehende Datenbank droppen (VORSICHT):**
   ```bash
   psql -U postgres -c "DROP DATABASE ctrader"
   psql -U postgres -c "CREATE DATABASE ctrader OWNER ctrader_user"
   ```

3. **Backup einspielen:**
   ```bash
   psql -U ctrader_user -d ctrader -f ctrader-2026-04-12.sql
   ```

4. **ctrader App neu starten:**
   ```bash
   docker compose restart ctrader
   ```

5. **Integritaets-Check:**
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```

## Geschaetzte Downtime
- Backup-Groesse < 100MB: ca. 2-5 Minuten
- Backup-Groesse 100MB - 1GB: ca. 10-30 Minuten
```

**Download-Endpoint:**
```python
@router.get("/settings/backup/download")
async def download_latest_backup(request: Request):
    # Localhost-only (bereits durch NFR-S2 127.0.0.1 binding)
    backup_dir = Path("data/backups")
    latest = sorted(backup_dir.glob("ctrader-*.sql.gz"))[-1]
    return FileResponse(
        latest,
        filename=latest.name,
        media_type="application/gzip",
    )
```

**File Structure:**
```
app/
├── services/
│   └── db_backup.py             # NEW
├── jobs/
│   └── db_backup.py             # NEW - scheduled wrapper
└── routers/
    └── settings.py              # NEW - /settings/backup/download

docs/
└── recovery.md                  # NEW

data/
└── backups/                     # NEW (0700)
    └── ctrader-YYYY-MM-DD.sql.gz  # 0600
```

### References

- PRD: FR52, NFR-R5, NFR-S5
- UX-Spec: UX-DR107 (DB-Backup-Download)
- Dependency: Story 12.1 (Scheduler), Story 12.2 (Health-Widget integration)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
