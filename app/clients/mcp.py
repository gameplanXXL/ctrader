"""Minimal MCP client wrapper for the `fundamental` server.

Story 1.6 scope:
- HTTP-based handshake against the MCP server (`tools/list` JSON-RPC).
- Capture the response as a versioned contract snapshot in
  `data/mcp-snapshots/`.
- 10-second hard timeout on every call (NFR-I1).
- Graceful degradation: a missing or unreachable server logs a warning
  and lets the app start. The downstream services check
  `app.state.mcp_available` before calling MCP.

Real fundamental-analysis calls land in Epic 5. This wrapper is the
seam everything else attaches to.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.logging import get_logger

logger = get_logger(__name__)

# NFR-I1: every MCP call has an explicit hard timeout.
DEFAULT_TIMEOUT_SECONDS = 10.0

# Project-root relative default for the snapshot directory.
DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "mcp-snapshots"


class MCPClient:
    """Thin httpx-based MCP client.

    Not a full MCP protocol implementation — Story 1.6 only needs
    handshake + tools/list. Real protocol coverage (resources,
    prompts, tool calls with streaming) lands when Epic 5 actually
    needs it.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owned_client = client is None

    async def aclose(self) -> None:
        """Close the underlying httpx client if we created it ourselves."""

        if self._owned_client:
            await self._client.aclose()

    async def list_tools(self) -> dict[str, Any]:
        """Call MCP `tools/list` and return the parsed JSON-RPC response.

        Raises:
            httpx.HTTPError: on transport failure or non-2xx response.
            httpx.TimeoutException: on >10s round-trip (NFR-I1).
        """

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        logger.info("mcp.list_tools.requesting", url=self.base_url)
        response = await self._client.post(self.base_url, json=payload)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        logger.info(
            "mcp.list_tools.received",
            tools=_count_tools(result),
        )
        return result


def _count_tools(payload: dict[str, Any]) -> int:
    """Count tools in a JSON-RPC `tools/list` response, regardless of shape."""

    result = payload.get("result", {})
    if isinstance(result, dict):
        tools = result.get("tools", [])
        if isinstance(tools, Iterable):
            return sum(1 for _ in tools)
    return 0


def write_contract_snapshot(
    payload: dict[str, Any],
    *,
    snapshot_dir: Path | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Persist the tools/list response as a versioned snapshot file.

    Filename convention: `week0-YYYYMMDD.json`. Used by Story 5.4 as
    the baseline for daily contract-drift detection.
    """

    target_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    when = timestamp or datetime.now(UTC)
    filename = f"week0-{when:%Y%m%d}.json"
    target = target_dir / filename

    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("mcp.snapshot.written", path=str(target), tools=_count_tools(payload))
    return target


async def handshake(
    base_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    snapshot_dir: Path | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, MCPClient | None]:
    """Connect to MCP, list tools, write snapshot. Never raises.

    Returns `(available, client)`. On failure `available` is False and
    `client` is None — the caller should set `app.state.mcp_available`
    accordingly so downstream code can degrade gracefully (FR23).

    Used by the FastAPI lifespan at startup. Snapshot writing happens
    inside this function so the lifespan stays small.
    """

    mcp_client: MCPClient | None = None
    try:
        mcp_client = MCPClient(base_url, timeout=timeout, client=client)
        payload = await mcp_client.list_tools()
        write_contract_snapshot(payload, snapshot_dir=snapshot_dir)
        logger.info("mcp.handshake.ok", url=base_url)
        return True, mcp_client
    except httpx.TimeoutException as exc:
        logger.warning("mcp.handshake.timeout", url=base_url, error=str(exc))
    except httpx.HTTPError as exc:
        logger.warning("mcp.handshake.http_error", url=base_url, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — graceful degradation by design
        logger.warning("mcp.handshake.unknown_error", url=base_url, error=str(exc))

    if mcp_client is not None:
        await mcp_client.aclose()
    return False, None
