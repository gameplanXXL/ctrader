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

import asyncio
import json
from typing import Any

import asyncpg
from pydantic import ValidationError

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.gordon import GordonDiff, GordonSnapshot, HotPick

logger = get_logger(__name__)


# TODO / CLAUDE.md contract gap (Epic 10 code-review EC-2 / EC-3, D214):
# `/home/cneise/Project/fundamental` currently exposes only `crypto`,
# `fundamentals`, `news`, `price`, `search` — there is NO `trend_radar`
# tool and NO `gordon` agent routing on the MCP side. Every
# `fetch_gordon_trend_radar` call therefore lands in the `source_error`
# path (always-write contract preserved). The `/trends` page shows a
# red "MCP-Fetch-Fehler" banner and an empty hot-picks list until either
# (a) fundamental adds a `trend_radar` tool, or (b) Chef decides to
# point Story 10.1 at a different data source (e.g. a scheduled scraper
# of the public Gordon blog). This constant is the single-point-of-
# change when that decision is made.
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
        # Template (`trends.html`) erkennt diesen Identifier und rendert
        # eine strukturierte Hinweis-Box mit Setup-Anleitung statt nur
        # den Raw-String. Key beibehalten, falls UI-Matching geändert wird.
        return None, [], "config_missing:mcp_fundamental_url"

    try:
        response = await mcp_client.call_tool(_GORDON_TOOL_NAME, arguments={"agent": "gordon"})
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("gordon.fetch_failed", error=str(exc), exc_info=True)
        return None, [], f"{type(exc).__name__}: {exc}"

    # Code-review H1 / BH-3: `"error" in response` was True even for
    # `{"error": null}` shapes, misreporting successful calls as MCP
    # errors. Use a truthy check so only a non-null, non-empty error
    # object triggers the failure path.
    if response.get("error"):
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


def _validate_picks_tolerant(
    raw_picks: list[dict[str, Any]],
) -> tuple[list[HotPick], int]:
    """Validate each pick independently, dropping malformed entries.

    Code-review H2 / BH-19: the previous list-comprehension
    `[HotPick.model_validate(p) for p in hot_picks]` crashed the entire
    `persist_snapshot` call when a single malformed pick slipped through
    — directly violating Story 10.1 AC #3 "never drop a day". Now we
    validate one at a time, log each drop with its offending payload,
    and persist whatever survived. The raw `snapshot_data` blob is
    written regardless so the operator can forensically replay the
    malformed day from the snapshot-data column.

    Returns `(valid_picks, dropped_count)`.
    """

    valid: list[HotPick] = []
    dropped = 0
    for index, raw in enumerate(raw_picks):
        try:
            valid.append(HotPick.model_validate(raw))
        except (ValidationError, TypeError, ValueError) as exc:
            dropped += 1
            logger.warning(
                "gordon.pick.malformed_dropped",
                index=index,
                error=str(exc),
                raw_keys=sorted(raw.keys()) if isinstance(raw, dict) else None,
            )
    return valid, dropped


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

    Validates picks tolerantly — see `_validate_picks_tolerant` for
    the rationale.
    """

    valid_picks, dropped_count = _validate_picks_tolerant(hot_picks)

    row = await conn.fetchrow(
        _INSERT_SNAPSHOT_SQL,
        snapshot_data or {},
        hot_picks,  # raw blob goes into JSONB even if validation dropped some
        source_error,
    )
    if row is None:
        raise RuntimeError("INSERT ... RETURNING returned no row")

    snapshot = GordonSnapshot(
        id=row["id"],
        snapshot_data=snapshot_data or {},
        hot_picks=valid_picks,
        source_error=source_error,
        created_at=row["created_at"],
    )
    logger.info(
        "gordon.snapshot.persisted",
        snapshot_id=snapshot.id,
        hot_picks_count=len(snapshot.hot_picks),
        dropped_count=dropped_count,
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


def _pick_key(pick: HotPick) -> tuple[str, str | None]:
    """Composite key for diffing — includes horizon so a symbol that
    appears at a new horizon (e.g. NVDA was swing_short last week, now
    also at swing_long) is correctly reported as NEW rather than
    unchanged (code-review H6 / EC-12).
    """

    return (pick.symbol, pick.horizon)


def compute_diff(current: list[HotPick], previous: list[HotPick] | None) -> GordonDiff:
    """Diff between two HOT-pick lists, keyed by (symbol, horizon).

    - `new`: picks in `current` whose (symbol, horizon) is not in `previous`
    - `dropped`: picks in `previous` whose (symbol, horizon) is not in `current`
    - `unchanged`: picks in `current` whose (symbol, horizon) IS in `previous`

    Notes:
    - A pick that merely changed rank, confidence, thesis, entry_zone,
      or target is `unchanged` — only the (symbol, horizon) tuple
      matters for bucket assignment.
    - `previous=None` or `previous=[]` → every current pick is `new`.

    Code-review H6 / EC-12: the previous implementation used
    `{p.symbol for p in ...}` which deduplicated multi-horizon entries
    for the same symbol. Chef saw a brand-new swing_long NVDA reported
    as "unchanged" alongside the swing_short carry, obscuring the
    actual week-over-week change.
    """

    if not previous:
        return GordonDiff(new=list(current), dropped=[], unchanged=[])

    current_keys = {_pick_key(p) for p in current}
    previous_keys = {_pick_key(p) for p in previous}

    new_picks = [p for p in current if _pick_key(p) not in previous_keys]
    dropped_picks = [p for p in previous if _pick_key(p) not in current_keys]
    unchanged_picks = [p for p in current if _pick_key(p) in previous_keys]

    return GordonDiff(
        new=new_picks,
        dropped=dropped_picks,
        unchanged=unchanged_picks,
    )
