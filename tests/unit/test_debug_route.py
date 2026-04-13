"""Story 1.6 — debug router smoke test.

Verifies that `/debug/mcp-tools` is mounted in development mode and
returns 503 when MCP is unavailable (which it always is in unit tests
thanks to the autouse handshake fake in conftest.py).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_debug_mcp_tools_returns_503_when_unavailable(client: TestClient) -> None:
    """When the conftest handshake fake says unavailable, the route says 503."""

    response = client.get("/debug/mcp-tools")
    assert response.status_code == 503

    body = response.json()
    assert body["detail"]["mcp_available"] is False
    assert "MCP_FUNDAMENTAL_URL" in body["detail"]["hint"]
