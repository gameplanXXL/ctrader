# Story 4.4: P&L-Kalender-View

Status: ready-for-dev

## Story

As a Chef,
I want a calendar view of my daily P&L,
so that I can spot patterns in my trading performance over time.

## Acceptance Criteria

1. **Given** die Journal-Seite, **When** der Kalender-View aktiviert wird, **Then** wird ein Monatsraster angezeigt mit jeder Zelle als Handelstag (FR13b)
2. **Given** eine Kalender-Zelle, **When** gerendert via calendar_cell-Macro, **Then** ist sie gruen getintet bei Gewinn, rot bei Verlust, grau bei keinem Trading, und der aktuelle Tag hat einen Accent-Border (UX-DR19, UX-DR72)
3. **Given** eine Kalender-Zelle, **When** geklickt, **Then** wird die Journal-Liste per HTMX auf diesen Tag gefiltert (FR13b, UX-DR19)
4. **Given** die Kalender-Zelle, **When** inspiziert, **Then** hat sie `role="gridcell"` und `aria-label` mit Datum und P&L (UX-DR19)

## Tasks / Subtasks

- [ ] Task 1: Daily-P&L-Aggregation (AC: 1)
  - [ ] `app/services/daily_pnl.py` — `get_daily_pnl(month: int, year: int)`
  - [ ] SQL: SUM(pnl) GROUP BY DATE(closed_at)
- [ ] Task 2: calendar_cell Macro (AC: 2, 4)
  - [ ] `app/templates/components/calendar_cell.html` (ersetzt Stub)
  - [ ] Parameter: date, pnl, tags
  - [ ] Tinting via style="background-color: ..."
  - [ ] Today-Border bei isToday
  - [ ] role="gridcell", aria-label="2026-04-10: +$234.50"
- [ ] Task 3: Calendar-Page Template (AC: 1, 2)
  - [ ] Monatsraster 7 Spalten (Mo–So) x ~5 Zeilen
  - [ ] Month-Navigation: Prev/Next-Arrows
  - [ ] Integration als Section in journal.html oder eigene Route `/journal/calendar`
- [ ] Task 4: Click-Handler fuer Day-Filter (AC: 3)
  - [ ] hx-get="/journal?date=2026-04-10"
  - [ ] Journal-Query um date-Filter erweitern

## Dev Notes

**SQL fuer Daily-P&L:**
```sql
SELECT
    DATE(closed_at) as trade_date,
    SUM(pnl) as daily_pnl,
    COUNT(*) as trade_count
FROM trades
WHERE closed_at IS NOT NULL
  AND closed_at >= DATE_TRUNC('month', $1::DATE)
  AND closed_at < DATE_TRUNC('month', $1::DATE) + INTERVAL '1 month'
GROUP BY DATE(closed_at)
ORDER BY trade_date;
```

**calendar_cell Tinting-Logik:**
```jinja2
{% macro calendar_cell(date, pnl, count=0, is_today=false) %}
  {% set bg_color = '' %}
  {% if pnl is none or count == 0 %}
    {% set bg_color = 'var(--bg-surface)' %}  {# No trading #}
  {% elif pnl > 0 %}
    {% set intensity = (pnl / 1000) | round(2) %}
    {% set bg_color = 'color-mix(in srgb, var(--color-green) ' + (intensity * 30) + '%, var(--bg-void))' %}
  {% else %}
    {% set intensity = (-pnl / 1000) | round(2) %}
    {% set bg_color = 'color-mix(in srgb, var(--color-red) ' + (intensity * 30) + '%, var(--bg-void))' %}
  {% endif %}
  <div class="calendar-cell {% if is_today %}today{% endif %}"
       role="gridcell"
       aria-label="{{ date }}: {% if pnl %}{{ pnl | format_pnl }}{% else %}no trading{% endif %}"
       style="background-color: {{ bg_color }}"
       hx-get="/journal?date={{ date }}"
       hx-target="#trade-list">
    <span class="date">{{ date.day }}</span>
    {% if pnl %}<span class="pnl font-mono">{{ pnl | format_pnl_short }}</span>{% endif %}
  </div>
{% endmacro %}
```

**Calendar-Layout:**
```
April 2026              [◀ March] [May ▶]
Mo  Tu  We  Th  Fr  Sa  Su
                 1   2   3   4
 5   6   7   8   9  10  11
12  13  14  15  16  17  18
19  20  21  22  23  24  25
26  27  28  29  30
```

**Color-Tinting-Strategy:**
- Proportional zur P&L-Intensitaet (groesserer Gewinn = kraeftigeres Gruen)
- Aber nicht zu aggressiv — Dark-Cockpit-Regel (UX-DR90 Calm Confidence)
- Max 30% Mix mit --bg-void

**File Structure:**
```
app/
├── services/
│   └── daily_pnl.py                 # NEW
├── routers/
│   └── journal.py                   # UPDATE - calendar route + date filter
└── templates/
    ├── components/
    │   └── calendar_cell.html       # UPDATE
    └── pages/
        └── calendar.html            # NEW (or section in journal.html)
```

### References

- PRD: FR13b
- UX-Spec: UX-DR19 (calendar_cell), UX-DR72 (P&L-Kalender)
- Dependency: Story 2.1 (trades), Story 2.3 (Journal-Liste fuer Filter-Integration)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
