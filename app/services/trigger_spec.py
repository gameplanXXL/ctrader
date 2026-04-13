"""Builders and parsers for `TriggerSpec` (Story 3.2).

Three entry points:

- `build_from_tagging_form(form_data)` — validates a POSTed tagging
  form and returns a `TriggerSpec`. Called by Story 3.1's
  `POST /trades/{id}/tag`.
- `build_from_proposal(proposal)` — placeholder for Epic 7 — reshapes
  an approved proposal row into a `TriggerSpec`.
- `parse(raw)` — takes a `trigger_spec` dict as it comes back from the
  DB (JSONB → Python dict via asyncpg) and returns a validated
  `TriggerSpec`. Used by the drilldown when it needs to hand the spec
  to the prose renderer.

Validation against `taxonomy.yaml` lives here (not on the Pydantic
model) so the model stays pinnable while the taxonomy evolves.
"""

from __future__ import annotations

from typing import Any

from app.logging import get_logger
from app.models.trigger_spec import TriggerSource, TriggerSpec
from app.services.taxonomy import get_taxonomy

logger = get_logger(__name__)


class TriggerSpecValidationError(ValueError):
    """Raised when a build_from_* helper gets input that violates the taxonomy."""


def _valid_ids(section: str) -> set[str]:
    return set(get_taxonomy().ids(section))


def _require_taxonomy_id(value: str, section: str, field: str) -> str:
    allowed = _valid_ids(section)
    if value not in allowed:
        raise TriggerSpecValidationError(
            f"{field}={value!r} is not in taxonomy.{section} (allowed: {sorted(allowed)})"
        )
    return value


def _coerce_confidence(raw: Any) -> float:
    """Accept '72', '72%', '0.72', 0.72 and normalize to the 0..1 range."""

    if raw is None or raw == "":
        return 0.5  # neutral default if the form omits it
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip().rstrip("%")
        try:
            value = float(text)
        except ValueError as exc:
            raise TriggerSpecValidationError(f"confidence={raw!r} is not a number") from exc
    if value > 1.0:
        value = value / 100.0
    if not 0.0 <= value <= 1.0:
        raise TriggerSpecValidationError(f"confidence={raw!r} is outside [0, 1]")
    return value


def _clean_mistake_tags(raw: Any) -> list[str]:
    """Accept either a list (from JSON) or a list[str] (from form-multi-checkbox)
    and drop anything that's not in the taxonomy. Unknown tags are logged,
    not rejected — the form is authoritative, so a taxonomy drift
    shouldn't block tagging."""

    if raw is None:
        return []
    if isinstance(raw, str):
        tags = [raw]
    elif isinstance(raw, (list, tuple)):
        tags = [str(t) for t in raw if t]
    else:
        raise TriggerSpecValidationError(f"mistake_tags has unexpected shape: {type(raw).__name__}")

    allowed = _valid_ids("mistake_tags")
    cleaned: list[str] = []
    for tag in tags:
        if tag in allowed:
            cleaned.append(tag)
        else:
            logger.warning("trigger_spec.mistake_tag_unknown", tag=tag)
    return cleaned


def build_from_tagging_form(
    form: dict[str, Any],
    *,
    source: TriggerSource = TriggerSource.MANUAL,
) -> TriggerSpec:
    """Translate a POSTed tagging form to a `TriggerSpec`.

    Required form keys (FR15 / Story 3.1 AC #1 — the four mandatory
    tagging fields):
        strategy, trigger_type, horizon, exit_reason

    Optional form keys:
        confidence, entry_reason, note, followed, mistake_tags[]

    Before Epic 6 creates the `strategies` table there is no dedicated
    column for `strategy`, so we store it inside the JSONB spec
    alongside `exit_reason`. Epic 6 Story 6.1 migrates `strategy` to
    `trades.strategy_id` while keeping the JSONB copy as a fallback.
    (Code-review H1 fix — previously both fields were silently dropped.)

    `followed` has no checkbox in the manual tagging form: for manual
    trades the concept doesn't apply, so we leave the flag as `None`
    unless the caller explicitly passes one. Bot-approval code paths
    (Epic 7) populate it via `build_from_proposal`.
    """

    strategy = str(form.get("strategy") or "").strip()
    trigger_type = str(form.get("trigger_type") or "").strip()
    horizon = str(form.get("horizon") or "").strip()
    exit_reason = str(form.get("exit_reason") or "").strip()

    if not strategy:
        raise TriggerSpecValidationError("strategy is required")
    if not trigger_type:
        raise TriggerSpecValidationError("trigger_type is required")
    if not horizon:
        raise TriggerSpecValidationError("horizon is required")
    if not exit_reason:
        raise TriggerSpecValidationError("exit_reason is required")

    _require_taxonomy_id(trigger_type, "trigger_types", "trigger_type")
    _require_taxonomy_id(horizon, "horizons", "horizon")
    _require_taxonomy_id(exit_reason, "exit_reasons", "exit_reason")
    # `strategy` is NOT validated against taxonomy here because Epic 6
    # will source it from the `strategies` table; until then we accept
    # any non-empty string and let the strategy_source adapter manage
    # the dropdown options (it already falls back to
    # taxonomy.strategy_categories before Epic 6).

    confidence = _coerce_confidence(form.get("confidence"))
    mistake_tags = _clean_mistake_tags(form.get("mistake_tags"))

    followed: bool | None = None
    if "followed" in form:
        raw = form["followed"]
        if isinstance(raw, str):
            followed = raw.lower() in ("true", "1", "yes", "on")
        elif raw is not None:
            followed = bool(raw)

    return TriggerSpec(
        trigger_type=trigger_type,
        confidence=confidence,
        horizon=horizon,
        entry_reason=str(form.get("entry_reason") or "").strip(),
        source=source,
        followed=followed,
        strategy=strategy,
        exit_reason=exit_reason,
        mistake_tags=mistake_tags,
        note=(str(form["note"]).strip() if form.get("note") else None),
    )


def build_from_proposal(proposal: dict[str, Any]) -> TriggerSpec:
    """Placeholder (Epic 7): build a `TriggerSpec` from an approved
    proposal. Real implementation lands in Story 7.x — for now we do
    the minimum so tests and callers stay honest.
    """

    return TriggerSpec(
        trigger_type=str(proposal.get("trigger_type") or "manual"),
        confidence=_coerce_confidence(proposal.get("confidence") or 0.5),
        horizon=str(proposal.get("horizon") or "intraday"),
        entry_reason=str(proposal.get("entry_reason") or ""),
        source=TriggerSource.BOT,
        agent_id=proposal.get("agent_id"),
        proposal_id=proposal.get("id"),
        followed=True,
    )


def parse(raw: dict[str, Any] | None) -> TriggerSpec | None:
    """Parse a DB-returned `trigger_spec` dict. `None` stays `None`.

    Unknown / extra keys are rejected (the Pydantic model uses
    `extra="forbid"`) so callers can rely on model_dump round-tripping.
    """

    if raw is None:
        return None
    return TriggerSpec.model_validate(raw)
