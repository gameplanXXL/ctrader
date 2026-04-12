# Story 1.1: FastAPI-Projekt-Scaffolding mit Docker Compose & PostgreSQL

Status: ready-for-dev

## Story

As a Chef,
I want a running ctrader application with database connectivity,
so that I have the foundation for all subsequent features.

## Acceptance Criteria

1. **Given** das Projekt ist geklont und .env konfiguriert, **When** `docker compose up` ausgefuehrt wird, **Then** startet die FastAPI-App auf 127.0.0.1:8000 und verbindet sich mit PostgreSQL via asyncpg Pool (min=2, max=10)
2. **Given** die App laeuft, **When** GET / aufgerufen wird, **Then** wird ein 200-Response zurueckgegeben
3. **Given** die Docker-Compose-Datei, **When** inspiziert, **Then** enthaelt sie genau 2 Services: ctrader und postgres
4. **Given** den Python-Code, **When** `ruff check` und `ruff format --check` ausgefuehrt werden, **Then** werden keine Fehler gemeldet (NFR-M1)
5. **Given** den App-Prozess, **When** er an das Netzwerk bindet, **Then** hoert er ausschliesslich auf 127.0.0.1 (NFR-S2)
6. **Given** ein beliebiges App-Event, **When** geloggt wird, **Then** ist das Log strukturiertes JSON via structlog mit Rotation (max 100MB/File, 5 Rotationen) (NFR-M4)

## Tasks / Subtasks

- [ ] Task 1: uv Projekt initialisieren (AC: 1)
  - [ ] `uv init` ausfuehren
  - [ ] `pyproject.toml` mit Python 3.12+ requirement
  - [ ] Dependencies hinzufuegen: fastapi, uvicorn, asyncpg, structlog, jinja2, pytailwindcss, ruff, pytest, pytest-asyncio
- [ ] Task 2: FastAPI-App mit Lifespan (AC: 1, 2)
  - [ ] `app/main.py` mit FastAPI-Instance
  - [ ] Lifespan-Manager fuer asyncpg Pool (min=2, max=10)
  - [ ] Root-Route GET / mit 200-Response
  - [ ] Uvicorn-Start-Script mit Bind auf 127.0.0.1:8000
- [ ] Task 3: Docker Compose Setup (AC: 1, 3)
  - [ ] `docker-compose.yml` mit 2 Services (ctrader + postgres)
  - [ ] Multi-Stage Dockerfile (Tailwind-Build → Runtime mit uv + uvicorn)
  - [ ] Volumes fuer logs und mcp-snapshots
  - [ ] `env_file: .env` in ctrader-Service
- [ ] Task 4: structlog Konfiguration (AC: 6)
  - [ ] `app/logging.py` mit structlog + JSON-Formatter
  - [ ] FileHandler mit Rotation (100MB/File, 5 Rotationen)
  - [ ] StreamHandler fuer stdout (Docker logs)
- [ ] Task 5: Ruff-Konfiguration (AC: 4)
  - [ ] Ruff-Config in `pyproject.toml` (Default-Profil)
  - [ ] `ruff check` und `ruff format --check` als Part des CI-Workflows
- [ ] Task 6: Smoke-Test (AC: 1, 2, 5)
  - [ ] Test: App startet und bindet an 127.0.0.1
  - [ ] Test: GET / liefert 200
  - [ ] Test: asyncpg Pool connected

## Dev Notes

**Tech Stack:**
- Python 3.12+ mit `uv` als Dependency-Manager
- FastAPI + uvicorn
- `asyncpg` (nicht SQLAlchemy/ORM) mit Connection Pool
- `structlog` fuer strukturierte JSON-Logs
- `ruff` fuer Linting + Formatting
- Docker Compose fuer lokales Deployment

**File Structure (initial):**
```
ctrader/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app + Lifespan
│   ├── logging.py        # structlog setup
│   └── db/
│       ├── __init__.py
│       └── pool.py       # asyncpg pool management
├── migrations/           # leer, kommt in Story 1.2
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── Dockerfile            # Multi-Stage
├── docker-compose.yml    # ctrader + postgres
├── .env.example
└── .gitignore
```

**Wichtige Constraints:**
- **NFR-S1:** Keine Credentials im Code — alles via `.env`
- **NFR-S2:** FastAPI MUSS auf 127.0.0.1 binden, NIE auf 0.0.0.0
- **NFR-M6:** Single-Process — FastAPI + APScheduler im gleichen Process (keine separate Worker-Queue)
- **.env NIEMALS committen** (.gitignore enforcement)

**asyncpg Pool Initialisierung (Beispiel):**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=2,
        max_size=10,
    )
    yield
    await app.state.db_pool.close()
```

### References

- PRD: `_bmad-output/planning-artifacts/prd.md` — NFR-S1, NFR-S2, NFR-M1, NFR-M4, NFR-M6
- Architecture: `_bmad-output/planning-artifacts/architecture.md` — "Frontend Architecture", "Infrastructure & Deployment", "Week-0 Critical Deliverables"
- CLAUDE.md: "Locked Technical Decisions"

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
