# Story 1.5: Base-Layout, Top-Bar & Leere Seiten-Shells

Status: done

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

- [x] Task 1: Jinja2 Base-Template (AC: 1, 5)
  - [x] `app/templates/base.html` mit `{% block title %}` und `{% block content %}`
  - [x] Top-Bar Partial `app/templates/_topbar.html` via `{% include %}`
  - [x] Viewport-Guard JS im `<head>` (Story 1.4)
  - [x] Compiled-CSS via `url_for('static', path='css/compiled.css')`
  - [x] `.ctrader-main`-Container mit `max-width: var(--content-max-width)` (= 1440px)
- [x] Task 2: Top-Bar Component (AC: 1, 2, 3)
  - [x] Logo links (Mark + Wordmark), Nav middle, 3 Health-Dots rechts (`role="status"`)
  - [x] 6 Nav-Items in einem Template-Loop ueber `nav_items`-Liste
  - [x] Active-Link via `active_route == slug` + `aria-current="page"`
  - [x] Keine Hamburger-, Drawer-, oder Tab-Bar-Logic (verifiziert in `test_topbar_has_no_hamburger`)
  - [x] Inline-Styles in `<style>`-Block (noch kein dediziertes Stylesheet-File, spart ein Build-Artifact)
- [x] Task 3: 6 Page-Shells erstellen (AC: 4)
  - [x] `GET /` → 302 Redirect auf `/journal` (Chef's primaere Surface)
  - [x] `/journal`, `/strategies`, `/approvals`, `/trends`, `/regime`, `/settings` mit je eigener Template-Datei
  - [x] Jede Shell erbt `base.html` und setzt `active_route`, `title`, Page-spezifischen H1 + Placeholder-Text
  - [x] `app/routers/pages.py` mit 7 Routen (6 Pages + Root-Redirect)
  - [x] **Wichtig:** Router hat `from __future__ import annotations` bewusst NICHT, weil FastAPI dann `templates.TemplateResponse` als Type re-evaluieren wuerde und `NameError` wirft
- [x] Task 4: 13 Component-Macro-Stubs (AC: 6)
  - [x] Alle 13 Stubs in `app/templates/components/` angelegt:
    - stat_card, trade_row, facet_chip, facet_bar, sparkline, status_badge,
      staleness_banner, trigger_spec_readable, calendar_cell, proposal_viewport,
      command_palette_item, toast, query_prose
  - [x] Jeder Stub ist ein `{% macro ... %}`-Block mit minimaler Implementation + Hinweis auf die Story, die die volle Version liefert
  - [x] **Kein Sparkline-vs-trade_chart-Verwechslung:** Sparkline bleibt SVG-Mini-Chart (Story 6.2), trade_chart ist ein **getrennter** Tier-2-Component (Story 4.5) mit lightweight-charts

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

Claude Opus 4.6 (1M context), bmad-dev-story workflow, 2026-04-13.

### Debug Log References

- **FastAPI `NameError: name 'Request' is not defined`** beim ersten Test-Run: Der Router hatte `from __future__ import annotations` und Return-Type `-> templates.TemplateResponse`. FastAPI evaluiert unter v0.120+ / pydantic-v2 Type-Hints lazy ueber `typing._eval_type`, und `templates.TemplateResponse` ist keine echte Klasse — das `typing._eval_type` failed dann im pydantic-Internals mit `NameError`. Fix: Return-Types komplett entfernt (FastAPI braucht sie fuer Template-Responses nicht) und `from __future__ import annotations` aus dem Router entfernt. Alle anderen Module behalten die future-annotations.
- **Ruff E402 nach Docstring-Edit:** Mein erster Fix-Versuch produzierte versehentlich zwei mehrzeilige Docstrings hintereinander im Router. Der zweite wurde als Statement-Expression interpretiert und triggerte "module-level import not at top of file" auf allen Imports darunter. Fix: Beide Docstrings zu einem gemergt.
- **TestClient URL-Resolution:** `url_for('static', path='...')` in den Templates rendert via TestClient absolute URLs (`http://testserver/static/...`). Die ersten Asserts erwarteten exakte `href="/static/..."`-Matches und failed. Fix: Auf Substring-Match geaendert (`"/static/css/compiled.css" in response.text`).

### Completion Notes List

- **Alle 6 AC erfuellt**, 16 neue Page-Tests gruen, 49/49 Unit-Tests gesamt.
- **Base-Template-Pattern bewusst schlicht:** Kein Template-Inheritance fuer Header/Footer (nur `{% include "_topbar.html" %}`). Style-Blocks inline statt separate Stylesheets — kann spaeter bei Bedarf refactored werden, aber fuer Story 1.5 Woche 0 ist Inline-CSS + Design-Tokens die schnellste Variante mit klarer Provenance.
- **Routing-Reihenfolge:** `app.include_router(pages_router.router)` in `main.py` nach dem Static-Mount. Root-Redirect zum Journal — Chef landet nicht auf einer JSON-Response sondern direkt im UI.
- **`/healthz` als Liveness-Probe:** Die JSON-Response vom alten `GET /` ist nicht verloren gegangen, nur auf `/healthz` verschoben. Docker-Compose-Healthcheck und die Smoke-Tests nutzen weiterhin diesen Endpoint. `test_root_endpoint_returns_200` wurde zu `test_healthz_endpoint_returns_200` umbenannt, `test_root_redirects_to_journal` als neuer Test fuer AC #4 der Story.
- **Component-Stubs haben minimale Implementation statt reiner `{% macro %}{% endmacro %}`-Shells.** Grund: Die Stubs sind bereits test-fit fuer ihre spaetere Erweiterung, und die Story-Hinweise (`trade_row` hat schon `tr/td`-Struktur, `status_badge` hat schon `dot`+`label`-Slots) machen die kuenftigen Stories (4.1, 7.3, etc.) schneller.
- **Alle Routen sind `include_in_schema=False`:** Kein OpenAPI/Swagger fuer Seiten-Routen — das ist fuer Single-User-Localhost nicht gebraucht und reduziert Noise in `/docs`.

### File List

**Neu erstellt (23):**
- `app/templates/base.html` — Haupt-Layout mit Top-Bar-Include + Viewport-Guard + compiled.css
- `app/templates/_topbar.html` — Top-Bar mit Logo, 6 Nav-Items, 3 Health-Dots
- `app/templates/pages/journal.html`
- `app/templates/pages/strategies.html`
- `app/templates/pages/approvals.html`
- `app/templates/pages/trends.html`
- `app/templates/pages/regime.html`
- `app/templates/pages/settings.html`
- `app/templates/components/stat_card.html`
- `app/templates/components/trade_row.html`
- `app/templates/components/facet_chip.html`
- `app/templates/components/facet_bar.html`
- `app/templates/components/sparkline.html`
- `app/templates/components/status_badge.html`
- `app/templates/components/staleness_banner.html`
- `app/templates/components/trigger_spec_readable.html`
- `app/templates/components/calendar_cell.html`
- `app/templates/components/proposal_viewport.html`
- `app/templates/components/command_palette_item.html`
- `app/templates/components/toast.html`
- `app/templates/components/query_prose.html`
- `app/routers/__init__.py` — Package-Marker
- `app/routers/pages.py` — 7 Routes (Root-Redirect + 6 Page-Shells)
- `tests/unit/test_pages.py` — 16 Tests (parametrisiert ueber 6 Pages + Topbar-Shared-Tests)

**Geaendert (2):**
- `app/main.py` — Static-Mount unter `/static`, Pages-Router include, `/` → `/healthz` umbenannt
- `tests/unit/test_main.py` — `test_root_redirects_to_journal` + `test_healthz_endpoint_returns_200`

### Change Log

- 2026-04-13: Story 1.5 implementiert. Jinja2-Base-Layout, Top-Bar mit 6 Nav-Items + Active-State, 6 Page-Shells mit "Coming soon"-Placeholders, 13 Component-Macro-Stubs als Tier-1/2/3-Basis, FastAPI Static-Mount, `/` → `/journal` Redirect, `/healthz` als Liveness-Probe. 16 neue Unit-Tests. Status ready-for-dev → review.
