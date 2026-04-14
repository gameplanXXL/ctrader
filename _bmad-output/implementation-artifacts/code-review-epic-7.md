---
review_date: 2026-04-14
review_type: adversarial-multi-layer
commit_under_review: a4d64e9
stories_reviewed:
  - 7-1-proposal-datenmodell-dashboard
  - 7-2-risk-gate-integration
  - 7-3-proposal-drilldown-viewport
  - 7-4-approve-reject-revision
  - 7-5-immutable-audit-log
reviewers:
  - acceptance-auditor (general-purpose subagent, full spec access)
  - blind-hunter (general-purpose subagent, diff-only)
  - edge-case-hunter (general-purpose subagent, full project read)
findings_summary:
  decision_needed: 0
  patch_high: 8
  patch_medium: 8
  patch_low: 0
  defer: 8
  dismiss: 0
status: tranche-a-applied
---

# Code Review — Epic 7 (Stories 7.1–7.5)

Adversarial multi-layer review of the approval-pipeline + risk-gate block. Acceptance Auditor validated all 5 stories on AC level with one blocking gap (Story 7.5 Task 4 append-only test missing). Blind Hunter + Edge Case Hunter surfaced the bulk of the race-condition findings (H1–H3 around FR28's TOCTOU window). Tranche A applies 16 patches (8 HIGH + 8 MEDIUM) plus the H7 integration test. **364/364 tests grün** (344 unit + 20 integration inkl. 4 neue append-only-Tests), ruff clean, live smoke-probe grün (create/approve/reject via Docker Compose).

## Patches Applied — Tranche A (16)

### 🔴 HIGH (8)

- **H1** **FR28 TOCTOU — risk_gate_result flip race** (BH-1, EC-1). The approve pipeline read `proposal.risk_gate_result` outside any transaction, then issued a plain `UPDATE ... WHERE status='pending'`. A concurrent `run_risk_gate_for_proposal` could flip red→green in that window, letting a stale pre-check slip through. Fix: three-layer defense — (1) pessimistic `is_red` returns `True` on `None` (fail closed); (2) service-layer pre-check raises `ProposalBlockedError` for 403; (3) new `_APPROVE_STATUS_SQL` includes `AND risk_gate_result IS NOT NULL AND risk_gate_result != 'red'` so the SQL UPDATE itself is the gate. *(app/models/proposal.py, app/services/proposal.py)*

- **H2** **Phantom audit rows on reject/revision CAS failure** (BH-2, EC-2). `reject_proposal` and `send_to_revision` silently swallowed `UPDATE ... WHERE status='pending'` misses, still writing an `audit_log` entry even when nothing changed. Fix: both functions now check the `RETURNING id` value and raise `ProposalNotFoundError` on CAS failure, before the audit write. *(app/services/proposal.py)*

- **H3** **`is_red` returned False on None** (EC-34, BH-40). A proposal whose risk-gate had not yet completed (`risk_gate_result is None`) was treated as "not red" → `can_be_approved` slipped through the brief window between proposal create and risk-gate completion. Fix: pessimistic — `None` now returns True. *(app/models/proposal.py)*

- **H4** *(merged with H1+H3, no separate patch)*

- **H5** **Strategy name missing from approval card** (Auditor 7.1 AC #2 / FR25). The dashboard card rendered only `strategy_id` (raw integer), breaking FR25's "Strategie" requirement. Fix: `_LIST_SQL` LEFT JOINs `strategies` and returns `strategy_name`; `Proposal` gets a `strategy_name: str | None` denormalized field; the card template shows the name or "— keine Strategie —" as em-dash for strategy-free proposals. *(app/services/proposal.py, app/models/proposal.py, app/templates/pages/approvals.html)*

- **H6** **Notes collected but never visible** (Auditor 7.4 AC #4). The approval viewport had a hidden `<input type="hidden" name="notes">` but no visible textarea — Chef could not actually type a note. Fix: replaced with a `<textarea name="notes" rows="2" maxlength="2000">`; reject/revision buttons get `hx-include="closest form"` so the notes flow to all three decision endpoints, not just approve. *(app/templates/components/proposal_viewport.html)*

- **H7** **Append-only trigger was not automatically tested** (Auditor 7.5 Task 4 / NFR-S3). Migration 008 installs a `BEFORE UPDATE OR DELETE` trigger that `RAISE EXCEPTION 'audit log is append-only'`, but the only evidence it worked was manual smoke-probing. Fix: new `tests/integration/test_audit_log_append_only.py` with four cases — INSERT + SELECT happy path (trigger doesn't block writes), UPDATE blocked, DELETE blocked, bulk UPDATE without WHERE also blocked (verifies FOR EACH ROW semantics). All 4 green against testcontainers Postgres 16. *(tests/integration/test_audit_log_append_only.py)*

- **H8** **audit_log had no CHECK constraints on event_type / risk_budget** (EC-3, EC-4). A typo like `'propposal_approved'` could silently persist, disappearing from the future Story-12.2 log viewer. `risk_budget` had no non-negative parity with `proposals.risk_budget`. Fix: Migration 009 adds `audit_log_event_type_check` (closed vocabulary: approved / rejected / revision / kill_switch_triggered / kill_switch_overridden) and `audit_log_risk_budget_check` (>= 0). Both use `NOT VALID + VALIDATE` for fast application on populated tables. *(migrations/009_audit_log_constraints.sql)*

### 🟡 MEDIUM (8)

- **M1** **`status_badge` macro announced "Status: Active" instead of "Risk Gate: GREEN"** (BH-14, EC-8). The dashboard card's risk-gate pill passed `"active"` etc. to the strategy-lifecycle badge macro — screen readers heard the wrong taxonomy. Fix: pass `green`/`yellow`/`red`/`unreachable` directly with an explicit `label="Risk Gate: GREEN"`. *(app/templates/pages/approvals.html)*

- **M2** **Post-persist UNREACHABLE dead branch in drilldown template** (EC-10). UNREACHABLE is mapped to RED at the DB layer (`risk_gate_result='red'` with `risk_gate_response.level='unreachable'`), so a template branch checking `proposal.risk_gate_result.value == 'unreachable'` was dead. Fix: probe `proposal.risk_gate_response.get('level')` from the JSONB to distinguish unreachable from real red. *(app/templates/components/proposal_viewport.html)*

- **M3** **Notes overwrite in `_UPDATE_STATUS_SQL`** (BH-1). The generic status-update wrote `notes = COALESCE($3, notes)` which would overwrite the Bot's original notes with Chef's decision notes. Fix: removed the notes column from the update entirely; Chef-side notes live exclusively in `audit_log.notes` where they belong per the audit-trail model. *(app/services/proposal.py)*

- **M4** **Strategy-active gate race on create_proposal** (BH-5). `is_strategy_active()` check was outside any transaction — a concurrent `toggle_status → retired` could sneak in between check and insert. Fix: wrapped the active-check in a transaction with `SELECT status FROM strategies WHERE id=$1 FOR UPDATE`, extracted `_do_insert_proposal` as a helper so both the strategy-gated and strategy-free paths share the insert. *(app/services/proposal.py)*

- **M5+M6** **Keyboard shortcut hardening** (BH-12, EC-10, EC-11). The `A`/`R` shortcut handler (a) fired on Ctrl+A (select-all), Cmd+R (reload), (b) ignored `<select>` + contentEditable, and (c) always routed to the first open drilldown, not the most recently clicked. Fix: early-return on any modifier, add `SELECT` and `isContentEditable` to the skip-list, track `lastFocusedDrilldown` via a body-level click listener so the shortcut routes to the last clicked card. *(app/templates/pages/approvals.html)*

- **M9** **Yellow risk-gate had no visual differentiation** from green approve. Fix: new `.proposal-viewport__btn--warn` variant with amber border + `⚠` prefix; template picks it in the `{% elif proposal.is_yellow %}` branch. *(app/templates/components/proposal_viewport.html)*

- **M10** **`_decision_response` had dead request + proposal parameters** (BH-15). Both were passed by every handler but only used to derive the `HX-Trigger` toast text, which can be built from `proposal_id` alone. Fix: dropped both parameters, shortened the function signature to `(action: str, proposal_id: int) -> Response`. *(app/routers/approvals.py)*

## Live Smoke-Probe Results

Against Docker Compose stack (`docker compose up -d --build`), Migration 009 applied in 9ms:

| Probe | Outcome |
|---|---|
| `GET /approvals` | HTTP 200, "0 pending" |
| `POST /api/proposals {...}` | HTTP 201, `{"id":2,"status":"pending","risk_gate_result":"red"}` — MCP unreachable → UNREACHABLE mapped to red, verified via the full refactored create-with-FOR-UPDATE pathway |
| `POST /proposals/2/approve` | **HTTP 403** `{"detail":"proposal 2 blocked by risk gate (red)"}` — FR28 hard invariant live-verified at the backend |
| `POST /proposals/2/reject` | HTTP 200 (toast swap) |
| `POST /proposals/2/reject` (second time) | **HTTP 404** `{"detail":"proposal 2 not pending"}` — H2 CAS check catches the already-decided state, no phantom audit row |

## Deferred (LOW) — 8 items

All added to `deferred-work.md` as **D173–D180**. Summary:
- Integration-test gaps (D173–D177): full HTTP approve flow, TOCTOU race test, list query JOIN, drilldown fragment rendering, Migration 009 constraint probes
- UI/observability (D178–D180): aria-live on toast container, Shift-modifier in keyboard shortcut, structlog events on decision endpoints

None block Epic 8 — all are post-MVP polish.

## Status

- **Tranche A applied:** 16 patches (8 HIGH + 8 MEDIUM) + new append-only integration test
- **Tests:** 364/364 green (344 unit + 20 integration)
- **Ruff:** clean (1 unused import removed after refactor)
- **Smoke probe:** end-to-end verified against Docker Compose
- **Deferred:** D173–D180 in deferred-work.md
- **Ready for:** Epic 8 (cTrader Bot Execution) Yolo-mode implementation
