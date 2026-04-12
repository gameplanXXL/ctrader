# Story 1.4: Design-Tokens & Tailwind-CSS-Pipeline

Status: ready-for-dev

## Story

As a Chef,
I want a consistent dark cockpit visual design,
so that the application looks professional and is easy to read during trading.

## Acceptance Criteria

1. **Given** design-tokens.css, **When** inspiziert, **Then** enthaelt es CSS-Custom-Properties fuer: Background-Layer (`--bg-void`, `--bg-chrome`, `--bg-surface`, `--bg-elevated`), Text-Farben (`--text-primary`, `--text-secondary`, `--text-muted`), P&L-Farben (#3fb950/#f85149), Status-Farben (green/yellow/red), Accent (#58a6ff) (UX-DR1)
2. **Given** design-tokens.css, **When** inspiziert, **Then** enthaelt es Typographie-Skala (6 Groessen 11–28px), Spacing-Tokens (4/8/12/16/24/32/48px) und Font-Families (Inter, JetBrains Mono) (UX-DR2–4)
3. **Given** die Tailwind-Konfiguration, **When** via pytailwindcss gebaut wird, **Then** wird CSS ohne Node.js-Dependency kompiliert (UX-DR8)
4. **Given** ein Viewport < 1024px, **When** eine Seite geladen wird, **Then** wird eine "Minimum 1024px"-Meldung angezeigt (UX-DR29)
5. **Given** das kompilierte CSS, **When** WCAG-Kontrast geprueft wird, **Then** erreicht Primary-Text auf Void mindestens AA (16.4:1) (UX-DR5)
6. **Given** Hover-, Focus-, Active-, Disabled- und Selected-States, **When** auf interaktive Elemente angewendet, **Then** entsprechen sie den definierten Token-Werten (UX-DR6)

## Tasks / Subtasks

- [ ] Task 1: design-tokens.css erstellen (AC: 1, 2)
  - [ ] `app/static/css/design-tokens.css` mit allen CSS-Custom-Properties
  - [ ] Colors: bg-void #0d1117, bg-chrome #161b22, bg-surface #21262d, bg-elevated #30363d
  - [ ] Text: text-primary #f0f6fc, text-secondary #c9d1d9, text-muted #8b949e
  - [ ] P&L: green #3fb950, red #f85149
  - [ ] Accent: #58a6ff
  - [ ] Typography-Scale: 11/12/14/16/20/28px
  - [ ] Spacing-Tokens: 4/8/12/16/24/32/48px
  - [ ] Font-Faces: Inter (Sans), JetBrains Mono (Mono)
- [ ] Task 2: Tailwind via pytailwindcss einrichten (AC: 3)
  - [ ] `tailwind.config.js` mit extended theme aus design-tokens
  - [ ] `app/static/css/main.css` mit `@tailwind base/components/utilities` + `@layer` Overrides
  - [ ] pytailwindcss als uv-dependency
  - [ ] Build-Script: `tailwindcss -i main.css -o app/static/css/compiled.css --minify`
- [ ] Task 3: Multi-Stage Docker Build fuer CSS (AC: 3)
  - [ ] Dockerfile: Tailwind-Build-Stage vor Runtime-Stage
  - [ ] Compiled CSS in Runtime kopieren
- [ ] Task 4: Viewport-Guard Component (AC: 4)
  - [ ] Jinja2 base template mit JS-Check `window.innerWidth < 1024`
  - [ ] Overlay-Message "ctrader requires minimum 1024px viewport"
  - [ ] Kein Mobile-Layout — explizit blockieren
- [ ] Task 5: Interaktive State-Styles (AC: 6)
  - [ ] Hover: `bg-elevated` oder level-up
  - [ ] Focus: `outline: 2px solid var(--accent)`
  - [ ] Active: level-down
  - [ ] Disabled: `opacity: 0.4; pointer-events: none`
  - [ ] Selected: accent-tinted `background-color: color-mix(var(--accent) 15%, transparent)`
- [ ] Task 6: WCAG Kontrast-Validation (AC: 5)
  - [ ] Unit-Test oder Build-Check: Kontrast-Ratios fuer alle Text-Background-Kombinationen
  - [ ] Assertion: Primary auf Void >= 16.4:1
  - [ ] Document der Werte in einem Test-Output

## Dev Notes

**Dark Cockpit Farbsystem (aus UX-Spec):**

| Token | Hex | Contrast to --text-primary |
|-------|-----|----------------------------|
| --bg-void | #0d1117 | 16.4:1 (AAA) |
| --bg-chrome | #161b22 | 14.7:1 (AAA) |
| --bg-surface | #21262d | 13.1:1 (AAA) |
| --bg-elevated | #30363d | 10.3:1 (AAA) |

**Typography-Skala:**
| Size | Use Case |
|------|----------|
| 11px | Labels, Tabellen-Header (uppercase, 0.05em tracking) |
| 12px | Secondary labels |
| 14px | Body-Text |
| 16px | Section-Header |
| 20px | Page-Title |
| 28px | Hero-Metriken (Monospace) |

**Spacing-Grid (4px-Basis):**
- Nur 4, 8, 12, 16, 24, 32, 48 — keine Zwischenwerte wie 5/7/9/10/11

**Fonts:**
- **Inter** fuer Sans-Serif (Labels, Navigation, Prosa)
- **JetBrains Mono** fuer Numerik-Werte (Spaltenalignment in Tabellen)
- Lokale Font-Files unter `app/static/fonts/` (kein CDN)

**File Structure:**
```
app/
├── static/
│   ├── css/
│   │   ├── design-tokens.css    # NEW
│   │   ├── main.css             # NEW (Tailwind source)
│   │   └── compiled.css         # Build-Output (gitignored)
│   ├── fonts/
│   │   ├── Inter-Regular.woff2
│   │   ├── Inter-Medium.woff2
│   │   └── JetBrainsMono-Regular.woff2
│   └── js/
│       └── viewport-guard.js    # Minimum 1024px check
└── templates/
    └── base.html                 # Base Layout mit Viewport-Guard
```

**pytailwindcss:**
- Python-Wrapper um Tailwind Standalone-Binary
- Kein Node.js, kein npm, kein package.json
- Uv-managed Dependency

### References

- UX-Spec: `ux-design-specification.md` — UX-DR1–9, UX-DR29, UX-DR30, UX-DR31, UX-DR90
- Architecture: `architecture.md` — "Frontend Architecture", "Tailwind-Build-Pipeline"
- Locked Decision: kein Node.js, kein React

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
