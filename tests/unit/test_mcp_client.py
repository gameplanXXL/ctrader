"""Unit tests for the MCP client wrapper (Story 1.6).

Uses `httpx.MockTransport` to simulate the fundamental MCP server so
the tests are hermetic — no real network, no real server. Covers all 4
acceptance criteria.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.clients.mcp import (
    DEFAULT_TIMEOUT_SECONDS,
    MCPClient,
    handshake,
    write_contract_snapshot,
)

# ---------------------------------------------------------------------------
# Helper — build a MockTransport that returns a preset payload
# ---------------------------------------------------------------------------


def _mock_client(payload: dict, *, status_code: int = 200) -> httpx.AsyncClient:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(_handler))


SAMPLE_TOOLS_RESPONSE = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {"name": "fundamentals", "description": "Stock fundamentals"},
            {"name": "price", "description": "Price data"},
            {"name": "news", "description": "News search"},
            {"name": "search", "description": "General search"},
            {"name": "crypto", "description": "Crypto-specific"},
        ]
    },
}


# ---------------------------------------------------------------------------
# AC #1 — successful handshake & tools/list
# ---------------------------------------------------------------------------


async def test_list_tools_returns_parsed_response(tmp_path: Path) -> None:
    client = MCPClient("http://mcp.local", client=_mock_client(SAMPLE_TOOLS_RESPONSE))
    payload = await client.list_tools()
    await client.aclose()

    assert payload["result"]["tools"][0]["name"] == "fundamentals"
    assert len(payload["result"]["tools"]) == 5


# ---------------------------------------------------------------------------
# AC #2 — snapshot is written to data/mcp-snapshots/
# ---------------------------------------------------------------------------


def test_write_contract_snapshot_creates_file(tmp_path: Path) -> None:
    timestamp = datetime(2026, 4, 13, tzinfo=UTC)
    target = write_contract_snapshot(
        SAMPLE_TOOLS_RESPONSE, snapshot_dir=tmp_path, timestamp=timestamp
    )

    assert target.name == "week0-20260413.json"
    assert target.is_file()

    # Content is round-trippable JSON identical to the input payload.
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == SAMPLE_TOOLS_RESPONSE


def test_write_contract_snapshot_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "snapshots"
    target = write_contract_snapshot(SAMPLE_TOOLS_RESPONSE, snapshot_dir=nested)
    assert target.parent == nested
    assert nested.is_dir()


async def test_handshake_writes_snapshot_on_success(tmp_path: Path) -> None:
    available, client = await handshake(
        "http://mcp.local",
        client=_mock_client(SAMPLE_TOOLS_RESPONSE),
        snapshot_dir=tmp_path,
    )

    assert available is True
    assert client is not None
    snapshots = list(tmp_path.glob("week0-*.json"))
    assert len(snapshots) == 1

    await client.aclose()


# ---------------------------------------------------------------------------
# AC #3 — graceful degradation when the server is unreachable
# ---------------------------------------------------------------------------


async def test_handshake_returns_unavailable_on_connection_error(tmp_path: Path) -> None:
    def _failing(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    bad_client = httpx.AsyncClient(transport=httpx.MockTransport(_failing))
    available, client = await handshake(
        "http://mcp.local",
        client=bad_client,
        snapshot_dir=tmp_path,
    )

    assert available is False
    assert client is None
    # No snapshot written on failure.
    assert list(tmp_path.glob("week0-*.json")) == []


async def test_handshake_returns_unavailable_on_http_error(tmp_path: Path) -> None:
    available, client = await handshake(
        "http://mcp.local",
        client=_mock_client({"error": "internal"}, status_code=500),
        snapshot_dir=tmp_path,
    )

    assert available is False
    assert client is None


# ---------------------------------------------------------------------------
# AC #4 — 10-second timeout enforcement (NFR-I1)
# ---------------------------------------------------------------------------


def test_default_timeout_matches_nfr_i1() -> None:
    """The module-level constant must be exactly 10 seconds."""

    assert DEFAULT_TIMEOUT_SECONDS == 10.0


def test_client_uses_explicit_timeout_when_constructing_default_client() -> None:
    """A bare `MCPClient(url)` builds an httpx.AsyncClient with timeout=10s."""

    client = MCPClient("http://mcp.local")
    assert isinstance(client._client, httpx.AsyncClient)
    # httpx Timeout objects expose `connect`, `read`, `write`, `pool` attrs;
    # all should reflect our 10s default.
    timeout = client._client.timeout
    assert timeout.read == DEFAULT_TIMEOUT_SECONDS


async def test_handshake_returns_unavailable_on_timeout(tmp_path: Path) -> None:
    def _slow(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated 15s delay")

    slow_client = httpx.AsyncClient(transport=httpx.MockTransport(_slow))
    available, client = await handshake(
        "http://mcp.local",
        client=slow_client,
        snapshot_dir=tmp_path,
    )

    assert available is False
    assert client is None


# ---------------------------------------------------------------------------
# Misc — debug route returns 503 when MCP unavailable (verified separately
# in test_pages because it needs the TestClient + lifespan)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tools_response",
    [
        {"result": {"tools": []}},
        {"result": {"tools": [{"name": "only"}]}},
        {"result": {}},  # No tools key at all
        {},  # Empty payload
    ],
)
def test_count_tools_handles_various_shapes(tools_response: dict) -> None:
    """The internal `_count_tools` helper never raises on weird payloads."""

    from app.clients.mcp import _count_tools

    count = _count_tools(tools_response)
    assert isinstance(count, int)
    assert count >= 0
