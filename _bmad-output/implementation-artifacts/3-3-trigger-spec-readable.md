# Story 3.3: Lesbare Trigger-Spec-Darstellung

Status: ready-for-dev

## Story

As a Chef,
I want to see the trigger specification as readable text instead of raw JSON,
so that I can quickly understand the trade rationale without parsing technical data.

## Acceptance Criteria

1. **Given** einen Trade mit vollstaendiger trigger_spec, **When** im Drilldown angezeigt, **Then** rendert das trigger_spec_readable-Macro die Spec als natuerlichsprachige Saetze (z.B. "Satoshi (Confidence 72%, Horizon: Swing) empfahl Long BTCUSD — Chef folgte der Empfehlung.") (FR18, UX-DR18)
2. **Given** einen Trade mit teilweise befuellter trigger_spec, **When** im Drilldown angezeigt, **Then** werden fehlende Felder als "Unbekannt" dargestellt (UX-DR18)
3. **Given** einen Trade ohne trigger_spec, **When** im Drilldown angezeigt, **Then** wird "Nicht getaggt" angezeigt (UX-DR18)
4. **Given** das trigger_spec_readable-Macro, **When** inspiziert, **Then** enthaelt es 20-30 Template-Patterns fuer verschiedene Trigger-Typen (UX-DR74)

## Tasks / Subtasks

- [ ] Task 1: trigger_spec_readable Macro (AC: 1, 2, 3)
  - [ ] `app/templates/components/trigger_spec_readable.html` (ersetzt Stub)
  - [ ] Parameter: trade, trigger_spec
  - [ ] Ausgabe als Prosa-Saetze
- [ ] Task 2: Template-Pattern-Library (AC: 4)
  - [ ] `app/services/trigger_prose.py` mit 20–30 Patterns
  - [ ] Ein Pattern pro trigger_type aus taxonomy.yaml
  - [ ] Bot-Pattern: "{agent_name} ({confidence}%, {horizon}) empfahl {side} {symbol} — {followed_text}"
  - [ ] Manual-Pattern: "Chef {side} {symbol} wegen {entry_reason} ({horizon}, {confidence}%)"
- [ ] Task 3: Partial-/Empty-Handling (AC: 2, 3)
  - [ ] Wenn trigger_spec NULL → "Nicht getaggt" in --text-muted
  - [ ] Wenn Feld fehlt → "Unbekannt"
- [ ] Task 4: Integration in Trade-Drilldown (AC: 1)
  - [ ] `fragments/trade_detail.html` updates
  - [ ] Import macro, render mit `{{ trigger_spec_readable(trade) }}`
- [ ] Task 5: Unit-Tests (AC: 1, 2, 3, 4)
  - [ ] Test fuer jedes der 20–30 Patterns
  - [ ] Test Partial: Felder fehlen → "Unbekannt"
  - [ ] Test Empty: NULL → "Nicht getaggt"

## Dev Notes

**Pattern-Beispiele (aus UX-DR74):**

| Trigger-Type | Pattern |
|--------------|---------|
| `technical_breakout` | "{side} {symbol} auf technischem Ausbruch — {entry_reason}" |
| `news_event` | "{agent_name} empfahl {side} {symbol} nach News-Event ({confidence}%)" |
| `mean_reversion` | "Mean-Reversion-Play: {side} {symbol} auf Oversold-Signal" |
| `satoshi_recommend` | "Satoshi (Confidence {confidence}%, Horizon: {horizon}) empfahl {side} {symbol} — {followed_text}" |
| `viktor_recommend` | "Viktor analysierte {symbol} als {rating} ({horizon}) — Chef {followed_text}" |
| `gordon_trend` | "Aus Gordon-Wochen-Radar: {symbol} als HOT-Pick ({horizon})" |

**followed_text:**
- `followed=true` → "Chef folgte der Empfehlung"
- `followed=false` → "Chef ueberstimmte die Empfehlung"

**Service-Pattern:**
```python
def render_trigger_prose(trigger_spec: dict | None, trade: dict) -> str:
    if not trigger_spec:
        return "Nicht getaggt"

    trigger_type = trigger_spec.get("trigger_type") or "Unbekannt"
    template = PATTERNS.get(trigger_type, PATTERNS["default"])
    return template.format(
        symbol=trade["symbol"],
        side=trade["side"],
        confidence=int((trigger_spec.get("confidence") or 0) * 100),
        horizon=trigger_spec.get("horizon") or "Unbekannt",
        agent_name=AGENT_NAMES.get(trigger_spec.get("agent_id"), "Ein Agent"),
        followed_text="folgte der Empfehlung" if trigger_spec.get("followed") else "ueberstimmte die Empfehlung",
        entry_reason=trigger_spec.get("entry_reason") or "Unbekannt",
    )
```

**Kritisches UX-Prinzip:**
> "KEIN Raw-JSON in der User-Facing UI" (FR18)

Der volle JSON darf nur im Debug-Mode oder in einem expliziten "Advanced View" sichtbar sein.

**File Structure:**
```
app/
├── services/
│   └── trigger_prose.py              # NEW
└── templates/
    └── components/
        └── trigger_spec_readable.html  # UPDATE (replaces stub)
```

### References

- PRD: FR18
- UX-Spec: UX-DR18 (trigger_spec_readable), UX-DR74 (20-30 Patterns)
- Dependency: Story 3.2 (trigger_spec Model), Story 2.4 (Drilldown)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
