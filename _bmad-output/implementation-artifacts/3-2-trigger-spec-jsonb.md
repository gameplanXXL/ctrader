# Story 3.2: Trigger-Spec JSONB & Auto-Befuellung

Status: ready-for-dev

## Story

As a Chef,
I want every trade to have a structured trigger specification,
so that I can trace exactly why each trade was entered.

## Acceptance Criteria

1. **Given** die trades-Tabelle, **When** inspiziert, **Then** hat die trigger_spec-Spalte einen GIN-Index fuer effiziente Facet-Queries (FR16)
2. **Given** ein Bot-Trade wird aus einem genehmigten Proposal erstellt, **When** der Trade in die DB geschrieben wird, **Then** wird die trigger_spec automatisch aus dem Proposal befuellt (FR17)
3. **Given** ein manueller Trade wird ueber das Tagging-Formular getaggt, **When** gespeichert wird, **Then** wird eine konforme trigger_spec (JSONB) aus den Form-Daten generiert und gespeichert (FR17)
4. **Given** die trigger_spec, **When** inspiziert, **Then** ist sie konform zum fundamental/trigger-evaluator-Schema mit snake_case Keys (FR16)

## Tasks / Subtasks

- [ ] Task 1: GIN-Index bereits in Story 2.1 erstellt (AC: 1)
  - [ ] Verify: `idx_trades_trigger_spec` existiert (CREATE INDEX aus Migration 002)
  - [ ] Wenn fehlt: Migration 003_trigger_spec_gin_index.sql
- [ ] Task 2: trigger_spec Schema-Definition (AC: 4)
  - [ ] `app/models/trigger_spec.py` mit Pydantic-Model
  - [ ] Felder: trigger_type, confidence, horizon, entry_reason, agent_id (optional), source, followed (bool)
  - [ ] Konform zum fundamental/trigger-evaluator-Schema
  - [ ] JSON-serialisierbar mit snake_case
- [ ] Task 3: Parser/Renderer Utilities (AC: 2, 3)
  - [ ] `app/services/trigger_spec.py` — `build_from_tagging_form(form_data) -> TriggerSpec`
  - [ ] `build_from_proposal(proposal) -> TriggerSpec` (placeholder bis Epic 7)
  - [ ] `parse(jsonb_dict) -> TriggerSpec`
- [ ] Task 4: Tagging-Endpoint-Update (AC: 3)
  - [ ] Story 3.1's POST /trades/{id}/tag nutzt `build_from_tagging_form`
  - [ ] UPDATE trades SET trigger_spec = $1 (JSONB via asyncpg auto-conversion)
- [ ] Task 5: Schema-Contract-Test (AC: 4)
  - [ ] Test: generierte trigger_spec validiert gegen fundamental/trigger-evaluator-Schema
  - [ ] Schema-File von fundamental als Referenz einbinden (ggf. per MCP-Tool-Call)

## Dev Notes

**trigger_spec JSONB-Beispiel:**
```json
{
  "trigger_type": "technical_breakout",
  "confidence": 0.72,
  "horizon": "swing_short",
  "entry_reason": "20-day high breakout mit volumen confirmation",
  "agent_id": null,
  "source": "manual",
  "followed": true
}
```

Fuer Bot-Trades (ab Epic 7/8):
```json
{
  "trigger_type": "news_event",
  "confidence": 0.85,
  "horizon": "intraday",
  "entry_reason": "Positive earnings surprise",
  "agent_id": "satoshi",
  "source": "bot",
  "followed": true,
  "proposal_id": 42
}
```

**Pydantic-Model:**
```python
from pydantic import BaseModel
from typing import Literal, Optional

class TriggerSpec(BaseModel):
    trigger_type: str  # aus taxonomy.yaml trigger_types
    confidence: float  # 0.0–1.0
    horizon: str       # aus taxonomy.yaml horizons
    entry_reason: str
    agent_id: Optional[str] = None
    source: Literal["manual", "bot"]
    followed: bool = True
    proposal_id: Optional[int] = None
```

**Facet-Query-Beispiel (fuer Epic 4, zur Referenz):**
```sql
SELECT * FROM trades
WHERE trigger_spec @> '{"trigger_type": "news_event"}'::jsonb
  AND trigger_spec->>'agent_id' = 'satoshi';
```

Der GIN-Index beschleunigt solche Queries.

**File Structure:**
```
app/
├── models/
│   └── trigger_spec.py         # NEW
└── services/
    └── trigger_spec.py         # NEW - build/parse helpers
```

**Kritisches Prinzip:**
- **KEIN Raw-JSON in der UI** (siehe Story 3.3 trigger_spec_readable)
- trigger_spec ist die Source-of-Truth — alles andere leitet sich davon ab
- Bei Bot-Trades: trigger_spec wird in Epic 8 Story 8.2 automatisch befuellt (Cross-Reference)

### References

- PRD: FR16, FR17
- Architecture: "JSONB Implementation", "Trigger-Provenance Schema" (Critical Cross-Cutting Concern)
- Dependency: Story 2.1 (trades mit trigger_spec Spalte + GIN-Index), Story 3.1 (Tagging-Form)
- External: fundamental/trigger-evaluator.ts (Schema-Quelle)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
