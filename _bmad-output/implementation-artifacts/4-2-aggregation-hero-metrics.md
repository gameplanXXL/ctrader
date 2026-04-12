# Story 4.2: Aggregation, Hero-Metriken & Query-Prosa

Status: ready-for-dev

## Story

As a Chef,
I want to see aggregated metrics for any facet combination,
so that I can evaluate the statistical performance of trade subsets.

## Acceptance Criteria

1. **Given** eine beliebige Facetten-Kombination, **When** aktiv, **Then** zeigt der Hero-Aggregation-Block: Trade Count, Expectancy (R-Multiple), Winrate (%), Drawdown (R-Multiple) — jeweils in Monospace 28px mit Sparkline darunter (FR13, UX-DR14, UX-DR68)
2. **Given** die Aggregation, **When** berechnet bei <= 2000 Trades, **Then** erscheint das Ergebnis innerhalb von 800ms (NFR-P4)
3. **Given** aktive Facetten, **When** die Hero-Aggregation aktualisiert wird, **Then** geschieht dies mit sanftem Opacity-Flash (1→0.5→1), ohne Layout-Jump (UX-DR42)
4. **Given** aktive Facetten, **When** die query_prose-Komponente rendert, **Then** zeigt sie eine lesbare Beschreibung der Query (z.B. "Crypto-Shorts mit Satoshi-Override") oder "Alle Trades" bei leeren Filtern (UX-DR21)
5. **Given** die Aggregation, **When** serverseitig gecached, **Then** wird der Cache nur bei neuen Trades/Tags/Approvals invalidiert (UX-DR103)

## Tasks / Subtasks

- [ ] Task 1: Aggregation-Service (AC: 1, 2)
  - [ ] `app/services/aggregation.py` — `compute_aggregation(facets) -> AggregationResult`
  - [ ] SQL: COUNT, AVG(r_multiple), winrate, max drawdown
  - [ ] Expectancy-Berechnung: sum(r_multiple) / count
- [ ] Task 2: stat_card Macro (AC: 1)
  - [ ] `app/templates/components/stat_card.html` (ersetzt Stub)
  - [ ] Parameter: label, value, trend, variant
  - [ ] Monospace 28px, sparkline darunter
- [ ] Task 3: Sparkline Macro (AC: 1)
  - [ ] `app/templates/components/sparkline.html` (ersetzt Stub)
  - [ ] Server-side SVG-Generation aus zeit-serialisierten Daten
  - [ ] role="img", aria-label
- [ ] Task 4: Hero-Block Layout (AC: 1)
  - [ ] 4-Spalten-Grid: Trade Count | Expectancy | Winrate | Drawdown
  - [ ] Query-Prosa darueber
- [ ] Task 5: query_prose Macro (AC: 4)
  - [ ] `app/templates/components/query_prose.html` (ersetzt Stub)
  - [ ] Template-Patterns: "{n_facets} facets active → '{rendered_text}'"
  - [ ] 20–30 Patterns fuer verschiedene Facet-Kombinationen
- [ ] Task 6: Server-side Aggregation-Cache (AC: 5)
  - [ ] `cachetools.TTLCache` oder dict mit `cache_key = hash(facets)`
  - [ ] Invalidation auf INSERT/UPDATE trades, tag-Events
- [ ] Task 7: HTMX Opacity-Flash (AC: 3)
  - [ ] CSS transition auf `.hero-metric` mit opacity
  - [ ] JS: bei facet-change → addClass('updating') → remove nach 200ms
- [ ] Task 8: Performance-Test (AC: 2)
  - [ ] 2000 Trades
  - [ ] Measure: Aggregation-Calc < 800ms

## Dev Notes

**Aggregation-Metriken:**

| Metrik | Formel |
|--------|--------|
| Trade Count | `COUNT(*)` |
| Expectancy | `AVG(r_multiple)` (ignoring NULLs) |
| Winrate | `100.0 * COUNT(*) FILTER (WHERE pnl > 0) / COUNT(*)` |
| Drawdown | `MIN(cumulative_r_multiple)` — requires window function |

**SQL-Beispiel:**
```sql
WITH filtered AS (
    SELECT * FROM trades WHERE <facet-conditions>
),
cumulative AS (
    SELECT
        r_multiple,
        pnl,
        SUM(r_multiple) OVER (ORDER BY opened_at) as cum_r
    FROM filtered
)
SELECT
    COUNT(*) as trade_count,
    AVG(r_multiple) as expectancy,
    100.0 * COUNT(*) FILTER (WHERE pnl > 0) / NULLIF(COUNT(*), 0) as winrate,
    MIN(cum_r) as drawdown
FROM cumulative;
```

**Hero-Block-Layout (aus UX-DR68):**
```
┌─ Query: Crypto-Shorts with Satoshi Override ─────────────┐
│                                                           │
│    TRADES       EXPECTANCY      WINRATE      DRAWDOWN    │
│    ═════        ══════════      ══════       ═════════   │
│     47            +0.32R         52%          -1.8R      │
│    ~~~~           ~~~~            ~~~~         ~~~~      │  ← sparklines
└───────────────────────────────────────────────────────────┘
```

**query_prose Patterns (UX-DR21):**
```python
def render_query_prose(facets: dict) -> str:
    if not facets:
        return "Alle Trades"

    parts = []
    if "asset_class" in facets:
        parts.append(f"{facets['asset_class'].title()}-Trades")
    if "trigger_source" in facets and "satoshi" in facets["trigger_source"]:
        if facets.get("followed_vs_override") == "override":
            parts.append("mit Satoshi-Override")
    # ... etc
    return " ".join(parts)
```

**File Structure:**
```
app/
├── services/
│   ├── aggregation.py               # NEW
│   ├── query_prose.py               # NEW
│   └── sparkline.py                 # NEW
└── templates/
    └── components/
        ├── stat_card.html           # UPDATE
        ├── sparkline.html           # UPDATE
        └── query_prose.html         # UPDATE
```

### References

- PRD: FR13, NFR-P4
- UX-Spec: UX-DR14/15/17 (stat_card, sparkline), UX-DR21 (query_prose), UX-DR42 (Live-Update), UX-DR68 (Hero-Aggregation), UX-DR103 (Server-Cache)
- Dependency: Story 4.1 (Facet-Framework), Story 2.3 (Journal-Page)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
