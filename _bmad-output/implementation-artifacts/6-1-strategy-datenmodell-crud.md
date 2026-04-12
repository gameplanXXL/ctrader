# Story 6.1: Strategy-Datenmodell & CRUD

Status: ready-for-dev

## Story

As a Chef,
I want to create and manage trading strategies with defined parameters,
so that I can systematically track the performance of each approach.

## Acceptance Criteria

1. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die `strategies`-Tabelle erstellt mit: id, name, asset_class, horizon (horizon_type enum), typical_holding_period, trigger_sources (JSONB array), risk_budget_per_trade, status (strategy_status enum: active/paused/retired), created_at, updated_at (FR33)
2. **Given** dieselbe Migration, **When** migrate laeuft, **Then** wird die trades-Tabelle per `ALTER TABLE trades ADD COLUMN strategy_id INT REFERENCES strategies(id) ON DELETE SET NULL` erweitert inklusive `idx_trades_strategy_id` Index (schliesst Issue M1 der Readiness-Review)
3. **Given** die Strategies-Seite, **When** "Neue Strategie" geklickt wird, **Then** oeffnet sich ein Formular mit Pflichtfeldern: Name, Asset-Class, Horizon, Typical-Holding-Period, Trigger-Quelle(n), Risikobudget pro Trade (FR33)
4. **Given** eine existierende Strategie, **When** der Status-Badge (Active/Paused/Retired) geklickt wird, **Then** wechselt der Status mit einem Klick und zeigt einen Toast zur Bestaetigung (FR38, UX-DR76)

## Tasks / Subtasks

- [ ] Task 1: Migration 008_strategies_table.sql (AC: 1, 2)
  - [ ] CREATE TABLE strategies mit allen Feldern
  - [ ] ALTER TABLE trades ADD COLUMN strategy_id
  - [ ] CREATE INDEX idx_trades_strategy_id
- [ ] Task 2: Pydantic-Models (AC: 1)
  - [ ] `app/models/strategy.py` mit Strategy, StrategyCreate, StrategyUpdate
- [ ] Task 3: Strategy-Service (AC: 1, 3, 4)
  - [ ] `app/services/strategy.py`
  - [ ] CRUD: create, get, list, update, update_status
- [ ] Task 4: Strategy-Form (AC: 3)
  - [ ] `app/templates/fragments/strategy_form.html`
  - [ ] 6 Pflichtfelder
  - [ ] Dropdown-Sources: asset_class, horizon aus taxonomy.yaml; trigger_sources multi-select
- [ ] Task 5: POST /strategies Endpoint (AC: 3)
  - [ ] Router in `app/routers/strategies.py`
  - [ ] Validation, INSERT, Redirect zu Strategy-List
- [ ] Task 6: Status-Toggle (AC: 4)
  - [ ] Click-Handler auf status_badge
  - [ ] POST `/strategies/{id}/status` mit new_status
  - [ ] HX-Trigger Toast on success
- [ ] Task 7: status_badge Macro (AC: 4, UX-DR76)
  - [ ] `app/templates/components/status_badge.html` (ersetzt Stub)
  - [ ] Farben: active=green, paused=yellow, retired=gray
  - [ ] Click-to-toggle mit HTMX

## Dev Notes

**strategies Schema (Konsens aus Architecture):**
```sql
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    asset_class TEXT NOT NULL,
    horizon horizon_type NOT NULL,
    typical_holding_period TEXT,
    trigger_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_budget_per_trade NUMERIC NOT NULL,
    status strategy_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Issue M1 Fix: Add strategy_id to trades
ALTER TABLE trades ADD COLUMN strategy_id INT REFERENCES strategies(id) ON DELETE SET NULL;
CREATE INDEX idx_trades_strategy_id ON trades(strategy_id);
```

**trigger_sources JSONB-Format:**
```json
["viktor", "satoshi", "manual"]
```

**status_badge Macro:**
```jinja2
{% macro status_badge(status, interactive=false, strategy_id=none) %}
  {% set classes = {
    'active': 'bg-[var(--color-green)]/20 text-[var(--color-green)]',
    'paused': 'bg-[var(--color-yellow)]/20 text-[var(--color-yellow)]',
    'retired': 'bg-[var(--text-muted)]/20 text-[var(--text-muted)]',
  } %}
  <span class="status-badge {{ classes[status] }}"
    {% if interactive %}
        hx-post="/strategies/{{ strategy_id }}/status-toggle"
        hx-swap="outerHTML"
    {% endif %}
    aria-label="Status: {{ status }}">
    ● {{ status | capitalize }}
  </span>
{% endmacro %}
```

**Status-Transitions (FR38):**
- active → paused (manuell oder durch Kill-Switch, FR42)
- paused → active
- paused → retired (final)
- active → retired (direkt moeglich)
- retired → no transitions (final state)

**File Structure:**
```
migrations/
└── 008_strategies_table.sql       # NEW
app/
├── models/
│   └── strategy.py                # NEW
├── services/
│   └── strategy.py                # NEW
├── routers/
│   └── strategies.py              # NEW
└── templates/
    ├── components/
    │   └── status_badge.html      # UPDATE
    └── fragments/
        └── strategy_form.html     # NEW
```

### References

- PRD: FR33, FR38
- UX-Spec: UX-DR76 (status_badges)
- Issue M1 aus Readiness-Report: strategy_id hier ergaenzen (nicht in Story 2.1)
- Dependency: Story 1.3 (taxonomy), Story 2.1 (trades-Tabelle)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
