"""Daily MCP contract-drift check (Story 5.4 / FR24 / NFR-R4).

Loads the frozen Week-0 `tools/list` snapshot from disk, compares it
against the current server response, and persists the result in
`mcp_contract_tests` so the health widget + drift banner can pick
it up.

Story 12.1 (scheduler framework) wires this into an APScheduler
cron job at 05:00 UTC. Until then the module exposes a
`run_contract_test()` entry point that can be invoked from a CLI
(`python -m app.cli.mcp_contract_test`) or a one-shot admin route.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from app.clients.mcp import DEFAULT_SNAPSHOT_DIR, MCPClient
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DriftReport:
    """Outcome of one contract test run.

    Code-review H5 / BH-18 / EC-22: `persisted` is mutated by
    `_persist_report` so the API endpoint can surface persistence
    failures to the caller. Without this flag, a drift detection
    that failed to persist would return a cheerful `status="pass"`
    to the user while the drift banner on the next page load shows
    the previous run's state. Not frozen anymore so the runner can
    update `persisted` post-insert.
    """

    status: str  # 'pass' | 'fail' | 'error'
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    error: str | None = None
    snapshot_version: str = "unknown"
    persisted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "error": self.error,
            "snapshot_version": self.snapshot_version,
            "persisted": self.persisted,
        }


# ---------------------------------------------------------------------------
# Snapshot loading
# ---------------------------------------------------------------------------


# Code-review H6 / BH-20 / EC-24: match only the canonical
# `week0-YYYYMMDD.json` filename so off-spec files like
# `week0-legacy.json` or `week0-final.json` don't silently become
# the drift baseline. The 8-digit date suffix sorts correctly under
# lexicographic comparison, so we keep the simple `sorted()` picker.
_SNAPSHOT_FILENAME_RE = __import__("re").compile(r"^week0-\d{8}\.json$")


def _resolve_snapshot_path(snapshot_dir: Path | None = None) -> Path | None:
    """Return the most recent canonical `week0-YYYYMMDD.json` snapshot."""

    target_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    if not target_dir.is_dir():
        return None
    candidates = sorted(
        path for path in target_dir.glob("week0-*.json") if _SNAPSHOT_FILENAME_RE.match(path.name)
    )
    return candidates[-1] if candidates else None


def load_snapshot(snapshot_dir: Path | None = None) -> tuple[dict[str, Any], str] | None:
    """Read the frozen snapshot. Returns `(payload, version)` or None.

    Code-review EC-26 / EC-27: an empty file or a `null` JSON body
    decodes to `None` or `""`, both of which are non-dict and would
    later crash `_extract_tools`. We return None in those cases so
    the caller emits a clean `error` status.
    """

    path = _resolve_snapshot_path(snapshot_dir)
    if path is None:
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("mcp_contract_test.snapshot_unreadable", path=str(path), error=str(exc))
        return None
    if not isinstance(raw, dict):
        logger.warning(
            "mcp_contract_test.snapshot_not_a_dict",
            path=str(path),
            shape=type(raw).__name__,
        )
        return None
    return raw, path.stem  # e.g. "week0-20260414"


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def _extract_tools(payload: Any) -> dict[str, dict[str, Any]]:
    """Return a name → tool-dict map from a `tools/list` response.

    Code-review H3 / EC-25 / EC-27: defensively normalize every
    unexpected shape (None, string, list, scalar) into an empty dict
    instead of crashing the contract test. The caller relies on the
    "always returns a dict" contract to diff without a try/except.
    """

    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    if not isinstance(result, dict):
        return {}
    tools = result.get("tools")
    if not isinstance(tools, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if isinstance(name, str) and name:
            out[name] = tool
    return out


def diff_contracts(
    snapshot: dict[str, Any], current: dict[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    """Return `(added, removed, changed)` tool-name lists."""

    snap = _extract_tools(snapshot)
    curr = _extract_tools(current)
    added = sorted(set(curr) - set(snap))
    removed = sorted(set(snap) - set(curr))
    changed: list[str] = []
    for name in sorted(set(snap) & set(curr)):
        if snap[name] != curr[name]:
            changed.append(name)
    return added, removed, changed


# ---------------------------------------------------------------------------
# Runner + persistence
# ---------------------------------------------------------------------------


_INSERT_SQL = """
INSERT INTO mcp_contract_tests (status, drift_details, snapshot_version)
VALUES ($1, $2, $3)
RETURNING id, run_at
"""

_LATEST_SQL = """
SELECT id, run_at, status, drift_details, snapshot_version
  FROM mcp_contract_tests
 ORDER BY run_at DESC
 LIMIT 1
"""


async def run_contract_test(
    conn: asyncpg.Connection,
    mcp_client: MCPClient | None,
    *,
    snapshot_dir: Path | None = None,
) -> DriftReport:
    """Fetch current tools, diff, persist, return the DriftReport."""

    snapshot_pair = load_snapshot(snapshot_dir)
    if snapshot_pair is None:
        report = DriftReport(
            status="error",
            error="snapshot file missing",
        )
        await _persist_report(conn, report)
        return report

    snapshot_payload, snapshot_version = snapshot_pair

    if mcp_client is None:
        report = DriftReport(
            status="error",
            error="mcp unavailable",
            snapshot_version=snapshot_version,
        )
        await _persist_report(conn, report)
        return report

    try:
        current = await mcp_client.list_tools()
    except (httpx.HTTPError, OSError) as exc:
        report = DriftReport(
            status="error",
            error=f"mcp fetch failed: {exc}",
            snapshot_version=snapshot_version,
        )
        await _persist_report(conn, report)
        return report
    except Exception as exc:  # noqa: BLE001 — defensive
        report = DriftReport(
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            snapshot_version=snapshot_version,
        )
        await _persist_report(conn, report)
        return report

    added, removed, changed = diff_contracts(snapshot_payload, current)
    has_drift = bool(added or removed or changed)
    report = DriftReport(
        status="fail" if has_drift else "pass",
        added=added,
        removed=removed,
        changed=changed,
        snapshot_version=snapshot_version,
    )
    await _persist_report(conn, report)
    logger.info(
        "mcp_contract_test.completed",
        status=report.status,
        added=len(added),
        removed=len(removed),
        changed=len(changed),
        snapshot=snapshot_version,
    )
    return report


async def _persist_report(conn: asyncpg.Connection, report: DriftReport) -> None:
    """Persist the report row. Flip `report.persisted=True` on success.

    Code-review H5 / BH-18 / EC-22: if the DB write fails we log
    loudly, append a `(persist failed)` note to the existing error
    string, and keep `persisted=False`. The API endpoint reads
    `persisted` so it can return a 500 / surface the gap to Chef
    instead of pretending everything landed.
    """

    try:
        details = {
            "added": report.added,
            "removed": report.removed,
            "changed": report.changed,
            "error": report.error,
        }
        await conn.execute(
            _INSERT_SQL,
            report.status,
            details,
            report.snapshot_version,
        )
        report.persisted = True
    except Exception as exc:  # noqa: BLE001 — surface, don't swallow
        logger.warning("mcp_contract_test.persist_failed", error=str(exc))
        suffix = f" (persist failed: {exc})"
        report.error = (report.error or "") + suffix
        report.persisted = False


@dataclass(frozen=True)
class LatestContractTest:
    id: int
    run_at: datetime
    status: str
    drift_details: dict[str, Any]
    snapshot_version: str

    @property
    def has_drift(self) -> bool:
        return self.status == "fail"


async def get_latest_contract_test(
    conn: asyncpg.Connection,
) -> LatestContractTest | None:
    """Return the most recent contract-test run, or None if the table
    is empty (scheduler hasn't run yet)."""

    row = await conn.fetchrow(_LATEST_SQL)
    if row is None:
        return None
    details = row["drift_details"] or {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except ValueError:
            details = {}
    return LatestContractTest(
        id=int(row["id"]),
        run_at=row["run_at"],
        status=str(row["status"]),
        drift_details=details,
        snapshot_version=str(row["snapshot_version"]),
    )
