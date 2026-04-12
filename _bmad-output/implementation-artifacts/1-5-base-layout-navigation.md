# Story 1.5: Base-Layout, Top-Bar & Leere Seiten-Shells

Status: ready-for-dev

## Story

As a Chef,
I want persistent navigation and page structure,
so that I can navigate between all main views of ctrader.

## Acceptance Criteria

1. **Given** eine beliebige Seite, **When** geladen, **Then** ist ein persistenter Top-Bar sichtbar mit: Logo (links), Navigation-Links Journal/Strategies/Approvals/Trends/Regime/Settings (Mitte), Health-Status-Placeholder-Dots (rechts) (UX-DR78)
2. **Given** die aktuelle Route, **When** die Seite laedt, **Then** ist der aktive Navigation-Link in --accent-Farbe hervorgehoben
3. **Given** den Top-Bar, **When** inspiziert, **Then** enthaelt er keine Hamburger-Menus, Slide-Out-Drawers oder Tab-Bars (UX-DR82)
4. **Given** einen Navigation-Link, **When** geklickt, **Then** navigiert er zur entsprechenden leeren Seiten-Shell
5. **Given** den Seiten-Inhalt, **When** gerendert, **Then** ist er zentriert mit max-width 1440px und --bg-void fuellt den Raum darueber hinaus (UX-DR31)
6. **Given** die Jinja2-Template-Struktur, **When** inspiziert, **Then** existieren Stub-Macros fuer alle 13 Component-Macros in `app/templates/components/` (UX-DR9)

## Tasks / Subtasks

- [ ] Task 1: Jinja2 Base-Template (AC: 1, 5)
  - [ ] `app/templates/base.html` mit `{% block content %}`
  - [ ] Top-Bar Partial `app/templates/_topbar.html`
  - [ ] Max-width 1440px mit centered layout
- [ ] Task 2: Top-Bar Component (AC: 1, 2, 3)
  - [ ] Logo links, Navigation-Links mittig, Health-Status-Dots rechts
  - [ ] Active-Link via Request-Route-Check
  - [ ] Keine Hamburger-/Drawer-Logic
- [ ] Task 3: 6 Page-Shells erstellen (AC: 4)
  - [ ] `/` → Journal (Redirect oder Landing)
  - [ ] `/journal`, `/strategies`, `/approvals`, `/trends`, `/regime`, `/settings`
  - [ ] Jede Shell: Inherit base.html, Placeholder-Text "Coming soon"
  - [ ] FastAPI Router in `app/routers/pages.py`
- [ ] Task 4: 13 Component-Macro-Stubs (AC: 6)
  - [ ] `app/templates/components/stat_card.html`
  - [ ] `app/templates/components/trade_row.html`
  - [ ] `app/templates/components/facet_chip.html`
  - [ ] `app/templates/components/facet_bar.html`
  - [ ] `app/templates/components/sparkline.html`
  - [ ] `app/templates/components/status_badge.html`
  - [ ] `app/templates/components/staleness_banner.html`
  - [ ] `app/templates/components/trigger_spec_readable.html`
  - [ ] `app/templates/components/calendar_cell.html`
  - [ ] `app/templates/components/proposal_viewport.html`
  - [ ] `app/templates/components/command_palette_item.html`
  - [ ] `app/templates/components/toast.html`
  - [ ] `app/templates/components/query_prose.html`
  - [ ] Jede als Stub mit `{% macro name(...) %}{% endmacro %}` (Implementierung kommt in spaeteren Stories)

## Dev Notes

**Navigation-Links (final):**
```
Journal    → /journal
Strategies → /strategies
Approvals  → /approvals
Trends     → /trends
Regime     → /regime
Settings   → /settings
```

**Component-Macro-Rollout:**
Laut UX-DR9 werden die Macros tier-basiert ueber die Wochen 0–6 ausgerollt:
- Woche 0 (diese Story): Stub-Files anlegen, damit spaetere Stories sie `{% from ... import ... %}` importieren koennen
- Woche 1–6: Stories implementieren die Macros bei Bedarf

**Jinja2 Base-Template Pattern:**
```html
<!DOCTYPE html>
<html lang="de">
<head>
  <link rel="stylesheet" href="{{ url_for('static', path='css/compiled.css') }}">
</head>
<body class="bg-void text-primary min-h-screen">
  {% include "_topbar.html" %}
  <main class="max-w-[1440px] mx-auto px-6">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

**File Structure:**
```
app/
├── routers/
│   ├── __init__.py
│   └── pages.py              # NEW - Page routes
└── templates/
    ├── base.html             # NEW
    ├── _topbar.html          # NEW
    ├── components/           # NEW - 13 stub macros
    └── pages/                # NEW
        ├── journal.html
        ├── strategies.html
        ├── approvals.html
        ├── trends.html
        ├── regime.html
        └── settings.html
```

### References

- UX-Spec: UX-DR9 (13 Macros), UX-DR24 (Layout), UX-DR29 (Desktop-only), UX-DR78 (Top-Bar), UX-DR81 (No Breadcrumbs), UX-DR82 (No Hamburger)
- Architecture: "Frontend Architecture" — HTMX + Jinja2 Pattern

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
