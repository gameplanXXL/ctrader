"""Debug routes — only mounted when `settings.environment == "development"`.

Story 1.6 includes `GET /debug/mcp-tools` so Chef can verify the MCP
handshake from a browser without writing test code. Production builds
never see this router.
"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/mcp-tools")
async def debug_mcp_tools(request: Request):
    """Return the live `tools/list` response from the MCP server.

    Honest behavior: if MCP is unavailable, returns a 503 with a clear
    JSON body. Never crashes.
    """

    if not getattr(request.app.state, "mcp_available", False):
        raise HTTPException(
            status_code=503,
            detail={
                "mcp_available": False,
                "hint": (
                    "Set MCP_FUNDAMENTAL_URL in .env and ensure the "
                    "fundamental MCP server is running."
                ),
            },
        )

    client = request.app.state.mcp_client
    payload = await client.list_tools()
    return {
        "mcp_available": True,
        "url": client.base_url,
        "tools_response": payload,
    }
