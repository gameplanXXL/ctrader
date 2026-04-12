# Story 4.6: Command Palette

Status: ready-for-dev

## Story

As a Chef,
I want a keyboard-driven command palette for fast navigation and search,
so that I can quickly jump to any view, strategy, or saved query without mouse navigation.

## Acceptance Criteria

1. **Given** eine beliebige Seite, **When** Ctrl+K gedrueckt wird, **Then** oeffnet sich ein 600px zentriertes Overlay mit Suchfeld (UX-DR50, FR59)
2. **Given** die Command Palette ist offen, **When** Text eingegeben wird, **Then** werden Ergebnisse via Fuzzy-Matching ueber Routes, Strategien, Trade-IDs und Facet-Presets angezeigt (UX-DR49, FR59)
3. **Given** ein Ergebnis in der Palette, **When** Enter gedrueckt wird, **Then** navigiert der Browser zur entsprechenden Seite (UX-DR23)
4. **Given** die Command Palette ist offen, **When** Escape gedrueckt wird, **Then** schliesst sich das Overlay
5. **Given** die command_palette_item-Eintraege, **When** inspiziert, **Then** haben sie `role="option"` in einer Listbox mit `aria-activedescendant` fuer Keyboard-Navigation (UX-DR23)
6. **Given** gespeicherte Query-Presets, **When** in der Palette gesucht, **Then** erscheinen sie als navigierbare Eintraege (UX-DR106, FR61)

## Tasks / Subtasks

- [ ] Task 1: Command-Palette-Overlay (AC: 1, 4)
  - [ ] `app/templates/components/command_palette.html`
  - [ ] Alpine.js Component: `x-data="commandPalette()"` `@keydown.ctrl.k.window.prevent="open=true"`
  - [ ] Position: fixed, centered, 600px width
  - [ ] Background: `--bg-elevated` mit backdrop-blur
  - [ ] Escape: close
- [ ] Task 2: Fuzzy-Search-Engine (AC: 2)
  - [ ] Vanilla JS Fuzzy-Match (z.B. fuse.js als lokale Vendor-Copy, oder eigene minimal-Implementation)
  - [ ] Index: Routes + Strategies + Trade-IDs + Presets
- [ ] Task 3: Command-Palette-Data-Endpoint (AC: 2, 6)
  - [ ] GET `/api/command-palette` returns JSON
  - [ ] Items: routes, strategies (aus DB), saved-queries (aus Story 4.7)
  - [ ] Refresh on palette open (or cache in sessionStorage)
- [ ] Task 4: command_palette_item Macro (AC: 5)
  - [ ] `app/templates/components/command_palette_item.html` (ersetzt Stub)
  - [ ] role="option"
  - [ ] Layout: Label + Shortcut-Badge (rechts)
  - [ ] Focused-State in --accent
- [ ] Task 5: Keyboard-Navigation (AC: 3, 5)
  - [ ] Arrow-Up/Down navigiert zwischen Items
  - [ ] Enter navigiert zu `window.location = item.url`
  - [ ] `aria-activedescendant` wird aktualisiert
- [ ] Task 6: Static-Routes-Registry
  - [ ] `app/services/command_palette.py` — `get_static_routes()`
  - [ ] Returns: Journal, Strategies, Approvals, Trends, Regime, Settings

## Dev Notes

**Alpine.js Pattern (aus Architecture.md Z. 273):**
```html
<div x-data="commandPalette()"
     @keydown.ctrl.k.window.prevent="open = true"
     @keydown.escape.window="open = false"
     x-show="open"
     x-transition.opacity
     class="fixed inset-0 flex items-start justify-center pt-[20vh] z-50 backdrop-blur-sm">

  <div class="w-[600px] bg-[var(--bg-elevated)] rounded-lg shadow-2xl">
    <input type="text"
           x-ref="searchInput"
           x-model="query"
           @keydown.arrow-down.prevent="selectNext()"
           @keydown.arrow-up.prevent="selectPrev()"
           @keydown.enter.prevent="navigate()"
           placeholder="Suchen..."
           class="w-full p-4 bg-transparent border-b border-[var(--bg-surface)]">

    <ul role="listbox" :aria-activedescendant="activeId" class="max-h-[400px] overflow-y-auto">
      <template x-for="(item, idx) in filteredItems" :key="item.id">
        {% from "components/command_palette_item.html" import command_palette_item %}
        <li role="option" :id="'cpi-' + item.id"
            :class="{ 'bg-[var(--accent)]': idx === activeIdx }"
            x-text="item.label">
        </li>
      </template>
    </ul>
  </div>
</div>

<script>
function commandPalette() {
  return {
    open: false,
    query: '',
    activeIdx: 0,
    items: [],
    get filteredItems() {
      return fuzzyFilter(this.items, this.query);
    },
    get activeId() {
      return this.filteredItems[this.activeIdx]?.id;
    },
    async init() {
      const res = await fetch('/api/command-palette');
      this.items = await res.json();
    },
    selectNext() { this.activeIdx = Math.min(this.activeIdx + 1, this.filteredItems.length - 1); },
    selectPrev() { this.activeIdx = Math.max(this.activeIdx - 1, 0); },
    navigate() {
      const item = this.filteredItems[this.activeIdx];
      if (item) window.location.href = item.url;
    },
  };
}
</script>
```

**Data-Format:**
```json
[
  {"id": "route-journal", "label": "Journal", "url": "/journal", "category": "Navigation"},
  {"id": "route-strategies", "label": "Strategies", "url": "/strategies", "category": "Navigation"},
  {"id": "strategy-5", "label": "Mean Reversion Crypto", "url": "/strategies/5", "category": "Strategies"},
  {"id": "preset-12", "label": "Satoshi Overrides Lost", "url": "/journal?preset=12", "category": "Presets"}
]
```

**Static Shortcut-Badges:**
- `[Ctrl+K]` im Top-Bar als visueller Hinweis
- Einzelne Items koennen eigene Shortcuts haben (z.B. `G J` fuer Journal)

**File Structure:**
```
app/
├── services/
│   └── command_palette.py          # NEW
├── routers/
│   └── api.py                      # UPDATE - /api/command-palette
├── static/
│   └── js/
│       └── vendor/
│           └── fuse.min.js         # NEW (or inline minimal fuzzy-match)
└── templates/
    ├── components/
    │   ├── command_palette.html         # NEW
    │   └── command_palette_item.html    # UPDATE
    └── base.html                   # UPDATE - include palette
```

### References

- PRD: FR59 (Command Palette)
- UX-Spec: UX-DR23, UX-DR49, UX-DR50
- Architecture: Alpine.js fuer Command Palette (Z. 65, 273)
- Dependency: Story 4.7 (Query-Presets)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
