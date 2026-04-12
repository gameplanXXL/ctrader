# Story 7.4: Approve, Reject & Revision-Flow

Status: ready-for-dev

## Story

As a Chef,
I want to approve, reject, or send back proposals with clear audit trails,
so that every decision is documented and I maintain full control over automated trading.

## Acceptance Criteria

1. **Given** ein Proposal mit YELLOW- oder GREEN-Status, **When** Chef "Approve" waehlt, **Then** muss ein Risikobudget als Pflichtfeld gesetzt werden (Default aus Proposal, ueberschreibbar) (FR29, UX-DR63)
2. **Given** ein Proposal, **When** Chef die Fundamental-Einschaetzung ueberstimmen will, **Then** setzt ein optionaler Override-Checkbox `overrode_fundamental=true` (FR31, UX-DR63)
3. **Given** ein Proposal, **When** Chef "Reject" waehlt, **Then** erscheint ein optionales Begruendungs-Feld; das Proposal verschwindet sofort aus der Pending-Liste mit Toast "Rejected" (FR30, UX-DR64)
4. **Given** ein Proposal, **When** Chef "Revision" waehlt, **Then** wird das Proposal mit optionaler Notiz an den Agent zurueckgeschickt; Status wechselt auf "revision" (FR30, UX-DR65)
5. **Given** die Approval-Action-Buttons, **When** inspiziert, **Then** sind sie keyboard-accessible: `A` fuer Approve (primary, filled), `R` fuer Reject (secondary, outlined), mit sichtbaren Shortcut-Badges (UX-DR43, UX-DR44, UX-DR66)

## Tasks / Subtasks

- [ ] Task 1: POST /proposals/{id}/approve (AC: 1, 2)
  - [ ] Request-Body: { risk_budget, overrode_fundamental: bool, notes: optional }
  - [ ] Backend-Guard: risk_gate != 'red' (siehe Story 7.2)
  - [ ] UPDATE proposals SET status='approved', decided_at=NOW()
  - [ ] INSERT audit_log (via Story 7.5)
  - [ ] Trigger: Bot-Execution (Epic 8, wird in Story 8.1 implementiert)
- [ ] Task 2: POST /proposals/{id}/reject (AC: 3)
  - [ ] Request-Body: { notes: optional }
  - [ ] UPDATE proposals SET status='rejected', decided_at=NOW()
  - [ ] INSERT audit_log
  - [ ] Response: HX-Trigger showToast + hx-swap-oob entfernt Card
- [ ] Task 3: POST /proposals/{id}/revision (AC: 4)
  - [ ] Status='revision', notes optional
  - [ ] Agent wird "notified" (placeholder — Epic 7 spezifiziert keinen konkreten Pfad)
- [ ] Task 4: Approve-Form (AC: 1, 2)
  - [ ] Inline im proposal_viewport (nicht als Modal!)
  - [ ] Risikobudget-Input mit Default aus Proposal
  - [ ] Override-Checkbox
- [ ] Task 5: Keyboard-Shortcuts (AC: 5)
  - [ ] Alpine.js oder vanilla JS
  - [ ] `A` → Approve-Flow (oeffnet Form, nicht direkt submit)
  - [ ] `R` → Reject-Flow
  - [ ] Nur aktiv wenn Proposal-Drilldown offen
- [ ] Task 6: Shortcut-Badges im UI (AC: 5)
  - [ ] `[A]` rechts vom Approve-Button
  - [ ] `[R]` rechts vom Reject-Button

## Dev Notes

**Kein Modal-Confirmation (UX-DR66):**
> "no modal confirmation (Approval is intentionally irreversible)"

Chef bestaetigt absichtlich ohne Popup — die Irreversibilitaet ist durchdacht und Teil der Strenge.

**Approve-Request-Flow:**
```
1. Chef klickt "Approve" oder drueckt 'A'
2. Inline-Form erscheint im proposal_viewport:
   - Risikobudget: [200] (prefilled)
   - [ ] Override fundamental
   - [Bestaetigen]
3. POST /proposals/42/approve {risk_budget: 200, overrode_fundamental: false}
4. Backend:
   - Guard: risk_gate != red
   - UPDATE proposals
   - INSERT audit_log (Story 7.5)
   - Trigger Bot-Execution async
5. Response:
   - HX-Trigger: showToast "Approved: Bot-Trade wird ausgefuehrt"
   - hx-swap-oob entfernt Proposal-Card aus Liste
```

**Audit-Log-Eintrag bei Approve:**
```json
{
  "event_type": "proposal_approved",
  "proposal_id": 42,
  "strategy_id": 5,
  "risk_budget": 200,
  "risk_gate_snapshot": { /* full response */ },
  "fundamental_snapshot": { /* full response */ },
  "override_flags": {"overrode_fundamental": false},
  "strategy_version": 1,
  "actor": "chef",
  "notes": null
}
```

**Override-Semantik (FR31):**
- Nur bei YELLOW oder GREEN erlaubt
- Bei RED technisch nicht moeglich (Button disabled)
- Override bedeutet: Chef genehmigt trotz negativer Fundamental-Einschaetzung
- Flag wird im Audit-Log persistent gespeichert

**Keyboard-Shortcut-Pattern:**
```html
<div x-data="{ approving: false }" @keydown.window="handleShortcut($event)">
  <button @click="approving = true" class="btn-primary">
    Approve <kbd>[A]</kbd>
  </button>

  <button hx-post="/proposals/42/reject" class="btn-secondary">
    Reject <kbd>[R]</kbd>
  </button>

  <div x-show="approving">
    <!-- Inline approve form -->
  </div>
</div>

<script>
function handleShortcut(e) {
  if (document.activeElement.tagName === 'INPUT') return;
  if (e.key.toLowerCase() === 'a') approving = true;
  if (e.key.toLowerCase() === 'r') document.querySelector('[hx-post*="reject"]').click();
}
</script>
```

**File Structure:**
```
app/
├── routers/
│   └── approvals.py              # UPDATE - approve/reject/revision endpoints
└── templates/
    └── fragments/
        └── approve_form.html     # NEW (inline form)
```

### References

- PRD: FR29, FR30, FR31
- UX-Spec: UX-DR43 (Shortcuts), UX-DR44 (Badges), UX-DR63 (Approve-Form), UX-DR64 (Reject), UX-DR65 (Revision), UX-DR66 (Buttons)
- Dependency: Story 7.1 (proposals), Story 7.2 (risk-gate), Story 7.5 (audit-log)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
