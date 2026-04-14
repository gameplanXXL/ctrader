"""Gordon trend-radar service (Epic 10, Stories 10.1 + 10.2).

Owns:
- `fetch_gordon_trend_radar(mcp_client)` — calls the `trend_radar`
  MCP tool (agent=`gordon`) and returns the raw payload + the parsed
  HOT-picks list. Degrades gracefully on any MCP failure by returning
  a `(None, error_string)` tuple, same pattern as
  `app.services.fear_greed`.
- `persist_snapshot(conn, snapshot_data, hot_picks, source_error)` —
  idempotent INSERT into `gordon_snapshots`.
- `fetch_and_persist(db_pool, mcp_client)` — the end-to-end daily-job
  path called from `POST /api/gordon/fetch` (manual trigger) and by
  the Story-11.1 APScheduler cron.
- `get_latest_snapshot(conn)` / `get_latest_two_snapshots(conn)` —
  convenience helpers for the Trends page.
- `compute_diff(current, previous)` — the Story-10.2 HOT-pick diff
  logic: new vs dropped vs unchanged, keyed by symbol.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.gordon import GordonDiff, GordonSnapshot, HotPick

logger = get_logger(__name__)


_GORDON_TOOL_NAME = "trend_radar"


# ---------------------------------------------------------------------------
# MCP fetch
# ---------------------------------------------------------------------------


def _parse_hot_picks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the HOT-picks array from a Gordon MCP response.

    Gordon's `trend_radar` tool returns a JSON-RPC envelope. The
    picks may live at one of a few documented paths depending on
    the fundamental-side schema version:
        result.hot_picks
        result.content[0].hot_picks
        result.content[0].text (stringified JSON — legacy path)

    We try each in turn and fall back to an empty list so a schema
    surprise never crashes the snapshot pipeline — the operator
    just sees an empty HOT-picks list + a log warning.
    """

    result = payload.get("result") or {}
    if isinstance(result, dict):
        direct = result.get("hot_picks")
        if isinstance(direct, list):
            return direct
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                picks = first.get("hot_picks")
                if isinstance(picks, list):
                    return picks
                raw_text = first.get("text")
                if isinstance(raw_text, str):
                    try:
                        parsed = json.loads(raw_text)
                        if isinstance(parsed, dict):
                            picks = parsed.get("hot_picks")
                            if isinstance(picks, list):
                                return picks
                        if isinstance(parsed, list):
                            return parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
    logger.warning("gordon.parse_hot_picks.empty", payload_keys=list(payload.keys()))
    return []


async def fetch_gordon_trend_radar(
    mcp_client: MCPClient | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    """Fetch Gordon's trend radar via MCP.

    Returns `(snapshot_data, hot_picks, error)`:
    - On success: `(full_result_dict, parsed_hot_picks_list, None)`
    - On failure: `(None, [], error_string)` — always-persist contract.
    """

    if mcp_client is None:
        return None, [], "mcp_client not configured"

    try:
        response = await mcp_client.call_tool(_GORDON_TOOL_NAME, arguments={"agent": "gordon"})
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("gordon.fetch_failed", error=str(exc))
        return None, [], f"{type(exc).__name__}: {exc}"

    if "error" in response:
        logger.warning("gordon.fetch.mcp_error", error=response["error"])
        return None, [], f"mcp_error: {response['error']}"

    hot_picks = _parse_hot_picks(response)
    return response, hot_picks, None


# ---------------------------------------------------------------------------
# Persist + fetch helpers
# ---------------------------------------------------------------------------


_INSERT_SNAPSHOT_SQL = """
INSERT INTO gordon_snapshots (snapshot_data, hot_picks, source_error)
VALUES ($1::jsonb, $2::jsonb, $3)
RETURNING id, created_at
"""


_SELECT_LATEST_SQL = """
SELECT id, snapshot_data, hot_picks, source_error, created_at
  FROM gordon_snapshots
 ORDER BY created_at DESC, id DESC
 LIMIT 1
"""


_SELECT_LATEST_TWO_SQL = """
SELECT id, snapshot_data, hot_picks, source_error, created_at
  FROM gordon_snapshots
 ORDER BY created_at DESC, id DESC
 LIMIT 2
"""


_SELECT_BY_ID_SQL = """
SELECT id, snapshot_data, hot_picks, source_error, created_at
  FROM gordon_snapshots
 WHERE id = $1
"""


def _row_to_snapshot(row: asyncpg.Record | None) -> GordonSnapshot | None:
    if row is None:
        return None
    snapshot_data = row["snapshot_data"] or {}
    if isinstance(snapshot_data, str):
        snapshot_data = json.loads(snapshot_data)
    hot_picks_raw = row["hot_picks"] or []
    if isinstance(hot_picks_raw, str):
        hot_picks_raw = json.loads(hot_picks_raw)
    hot_picks = [HotPick.model_validate(p) for p in hot_picks_raw]
    return GordonSnapshot(
        id=row["id"],
        snapshot_data=snapshot_data,
        hot_picks=hot_picks,
        source_error=row["source_error"],
        created_at=row["created_at"],
    )


async def persist_snapshot(
    conn: asyncpg.Connection,
    *,
    snapshot_data: dict[str, Any] | None,
    hot_picks: list[dict[str, Any]],
    source_error: str | None,
) -> GordonSnapshot:
    """Insert one snapshot row and return the hydrated model.

    `_INSERT_SNAPSHOT_SQL` only RETURNs id + created_at — we hydrate
    the `GordonSnapshot` from those two columns plus the values we
    just passed in. Avoids a second round-trip.
    """

    row = await conn.fetchrow(
        _INSERT_SNAPSHOT_SQL,
        snapshot_data or {},
        hot_picks,
        source_error,
    )
    assert row is not None, "INSERT ... RETURNING returned no row"
    snapshot = GordonSnapshot(
        id=row["id"],
        snapshot_data=snapshot_data or {},
        hot_picks=[HotPick.model_validate(p) for p in hot_picks],
        source_error=source_error,
        created_at=row["created_at"],
    )
    logger.info(
        "gordon.snapshot.persisted",
        snapshot_id=snapshot.id,
        hot_picks_count=len(snapshot.hot_picks),
        has_error=snapshot.source_error is not None,
    )
    return snapshot


async def fetch_and_persist(
    db_pool: Any,
    mcp_client: MCPClient | None,
) -> GordonSnapshot:
    """End-to-end daily-job path: fetch via MCP, persist, return.

    Story 10.1 AC #3 "no silent failure" — even on full MCP outage
    we still write a row (with empty hot_picks + source_error) so
    the weekly heartbeat is durable.
    """

    snapshot_data, hot_picks, error = await fetch_gordon_trend_radar(mcp_client)

    async with db_pool.acquire() as conn:
        snapshot = await persist_snapshot(
            conn,
            snapshot_data=snapshot_data,
            hot_picks=hot_picks,
            source_error=error,
        )
    return snapshot


async def get_latest_snapshot(conn: asyncpg.Connection) -> GordonSnapshot | None:
    row = await conn.fetchrow(_SELECT_LATEST_SQL)
    return _row_to_snapshot(row)


async def get_latest_two_snapshots(
    conn: asyncpg.Connection,
) -> tuple[GordonSnapshot | None, GordonSnapshot | None]:
    """Return `(current, previous)` for the Trends diff.

    Either or both may be None on a fresh install (no snapshots
    persisted yet) or after a single-run system.
    """

    rows = await conn.fetch(_SELECT_LATEST_TWO_SQL)
    if not rows:
        return None, None
    current = _row_to_snapshot(rows[0])
    previous = _row_to_snapshot(rows[1]) if len(rows) > 1 else None
    return current, previous


async def get_snapshot_by_id(conn: asyncpg.Connection, snapshot_id: int) -> GordonSnapshot | None:
    row = await conn.fetchrow(_SELECT_BY_ID_SQL, snapshot_id)
    return _row_to_snapshot(row)


# ---------------------------------------------------------------------------
# Diff logic (Story 10.2)
# ---------------------------------------------------------------------------


def compute_diff(current: list[HotPick], previous: list[HotPick] | None) -> GordonDiff:
    """Symbol-keyed diff between two HOT-pick lists.

    - `new`: picks in `current` whose symbol is not in `previous`
    - `dropped`: picks in `previous` whose symbol is not in `current`
    - `unchanged`: picks in `current` whose symbol IS in `previous`

    Notes:
    - A symbol that merely moved rank or changed thesis is `unchanged`.
    - `previous=None` → every current pick is `new`.
    """

    if not previous:
        return GordonDiff(new=list(current), dropped=[], unchanged=[])

    current_symbols = {p.symbol for p in current}
    previous_symbols = {p.symbol for p in previous}

    new_picks = [p for p in current if p.symbol not in previous_symbols]
    dropped_picks = [p for p in previous if p.symbol not in current_symbols]
    unchanged_picks = [p for p in current if p.symbol in previous_symbols]

    return GordonDiff(
        new=new_picks,
        dropped=dropped_picks,
        unchanged=unchanged_picks,
    )
