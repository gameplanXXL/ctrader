"""Debug routes — only mounted when `settings.environment == "development"`.

Story 1.6 includes `GET /debug/mcp-tools` so Chef can verify the MCP
handshake from a browser without writing test code. Production builds
never see this router.
"""

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/mcp-tools")
async def debug_mcp_tools(request: Request):
    """Return the live `tools/list` response from the MCP server.

    Honest behavior:
    - If MCP was never available at startup → 503 with "configure URL".
    - If MCP was available at startup but is now unreachable / broken
      (server died, network blip, shutdown race) → 503 with the actual
      error, NOT a 500 + traceback.
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
    try:
        payload = await client.list_tools()
    except (httpx.HTTPError, RuntimeError) as exc:
        # `RuntimeError` covers the lifespan-shutdown race where the
        # injected httpx.AsyncClient was already aclose()d under us.
        raise HTTPException(
            status_code=503,
            detail={
                "mcp_available": False,
                "hint": "MCP was reachable at startup but is no longer responding.",
                "error": str(exc),
            },
        ) from exc

    return {
        "mcp_available": True,
        "url": client.base_url,
        "tools_response": payload,
    }
