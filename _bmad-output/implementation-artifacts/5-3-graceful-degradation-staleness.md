# Story 5.3: MCP-Graceful-Degradation & Staleness-Banner

Status: ready-for-dev

## Story

As a Chef,
I want the application to remain functional during MCP outages,
so that I can continue reviewing my journal even when AI services are unavailable.

## Acceptance Criteria

1. **Given** der MCP-Server ist nicht erreichbar, **When** Journal, Strategy oder Regime Views geladen werden, **Then** bleiben diese Views voll funktional; betroffene Spalten zeigen "N/A (HH:MM)" (FR23, NFR-R6, UX-DR57)
2. **Given** ein MCP-Outage, **When** die Seite geladen wird, **Then** erscheint ein `staleness_banner` unter dem Top-Bar: gelbe Akzent-Leiste mit "Viktor-MCP: letztes Update HH:MM, Cache abgelaufen" (UX-DR20, UX-DR53)
3. **Given** den Staleness-Banner, **When** die Staleness > 24h betraegt, **Then** wechselt der Banner von gelb auf rot (Critical) mit `role="alert"` und `aria-live="assertive"` (UX-DR20)
4. **Given** den Staleness-Banner, **When** konfiguriert, **Then** pollt er optional via hx-get alle 60 Sekunden den Status (UX-DR20)

## Tasks / Subtasks

- [ ] Task 1: staleness_banner Macro (AC: 2, 3)
  - [ ] `app/templates/components/staleness_banner.html` (ersetzt Stub)
  - [ ] Parameter: last_update, source, severity ('yellow' | 'red')
  - [ ] Yellow: gelbe Akzent-Leiste
  - [ ] Red: rote Akzent-Leiste, role="alert", aria-live="assertive"
- [ ] Task 2: MCP-Health-Tracker (AC: 1, 2)
  - [ ] `app/services/mcp_health.py` mit globalem State
  - [ ] Tracking: last_successful_call_per_agent, error_count
  - [ ] Updated bei jedem MCP-Call in Story 1.6 Wrapper
- [ ] Task 3: Global-Template-Context (AC: 1, 2)
  - [ ] FastAPI-Dependency `get_mcp_status()` fuer alle Page-Routes
  - [ ] Template-Context enthaelt `mcp_status` dict
  - [ ] base.html rendert staleness_banner wenn `mcp_status.degraded`
- [ ] Task 4: Graceful Degradation in Views (AC: 1)
  - [ ] Journal, Strategy, Regime Views laden auch ohne MCP
  - [ ] Fundamental-Felder zeigen "N/A (HH:MM)" statt Fehler
  - [ ] Try-Catch um jeden MCP-Call mit Fallback
- [ ] Task 5: Polling (AC: 4)
  - [ ] `<div hx-get="/api/mcp-status" hx-trigger="every 60s" hx-swap="outerHTML">`
  - [ ] Endpoint returns banner HTML oder leer wenn OK
- [ ] Task 6: Severity-Logic (AC: 3)
  - [ ] < 1h stale → kein Banner
  - [ ] 1h–24h → yellow
  - [ ] > 24h → red critical

## Dev Notes

**MCP-Health-Service-Pattern:**
```python
class MCPHealth:
    def __init__(self):
        self.last_success: dict[str, datetime] = {}
        self.error_counts: dict[str, int] = {}

    def record_success(self, agent: str):
        self.last_success[agent] = datetime.utcnow()
        self.error_counts[agent] = 0

    def record_failure(self, agent: str):
        self.error_counts[agent] = self.error_counts.get(agent, 0) + 1

    def get_status(self) -> dict:
        now = datetime.utcnow()
        status = {}
        for agent in ['viktor', 'satoshi', 'rita', 'cassandra', 'gordon']:
            last = self.last_success.get(agent)
            if last is None:
                status[agent] = {'severity': 'red', 'last_success': None}
            else:
                age_hours = (now - last).total_seconds() / 3600
                if age_hours < 1:
                    status[agent] = {'severity': 'ok', 'last_success': last}
                elif age_hours < 24:
                    status[agent] = {'severity': 'yellow', 'last_success': last}
                else:
                    status[agent] = {'severity': 'red', 'last_success': last}
        return status
```

**staleness_banner Macro:**
```jinja2
{% macro staleness_banner(source, last_update, severity='yellow') %}
  <div role="{% if severity == 'red' %}alert{% else %}status{% endif %}"
       aria-live="{% if severity == 'red' %}assertive{% else %}polite{% endif %}"
       class="staleness-banner severity-{{ severity }}"
       hx-get="/api/mcp-status"
       hx-trigger="every 60s"
       hx-swap="outerHTML">
    <span class="text-sm">
      {{ source }}: letztes Update {{ last_update | format_time }},
      {% if severity == 'red' %}Cache > 24h abgelaufen{% else %}Cache abgelaufen{% endif %}
    </span>
  </div>
{% endmacro %}
```

**base.html Integration:**
```html
{% include "_topbar.html" %}
{% if mcp_status.degraded %}
  {{ staleness_banner(mcp_status.agent_name, mcp_status.last_success, mcp_status.severity) }}
{% endif %}
<main>{% block content %}{% endblock %}</main>
```

**Kritisches Prinzip (NFR-R6):**
> "Graceful Degradation on MCP-Outage: Journal, Strategy, Regime Views remain functional; Fundamental assessments show clear unavailability state; Approval flow explicitly blocks with 'Risk-Gate unreachable' state"

Unterschied zwischen:
- **Info-Views (Journal, Strategy, Regime):** Degrade gracefully, zeige "N/A"
- **Action-Views (Approval):** Blocke explizit mit Fehler-State (siehe Epic 7)

**File Structure:**
```
app/
├── services/
│   └── mcp_health.py             # NEW
├── routers/
│   └── api.py                    # UPDATE - /api/mcp-status
└── templates/
    ├── components/
    │   └── staleness_banner.html # UPDATE
    └── base.html                 # UPDATE - include banner
```

### References

- PRD: FR23, NFR-R6
- UX-Spec: UX-DR20 (staleness_banner), UX-DR53 (Warning), UX-DR57 (Graceful Degradation)
- Dependency: Story 1.6 (MCP-Client), Story 5.1 (Fundamental-Service)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
