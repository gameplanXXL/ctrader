"""ib_async wrapper for Interactive Brokers TWS / Gateway.

Story 2.2 scope: connection lifecycle + execution event subscription.
Real-order-placement (Story 11.2 / Quick-Order) and historical data
queries land in later stories — this module is the seam everything
else hangs off.

Design notes:
- Connection is OPTIONAL. If `settings.ib_host` is None we don't even
  try — the app starts with `ib_available=False` and downstream code
  degrades gracefully (same pattern as MCP, FR23 spirit).
- The IB Gateway / TWS UI is required to be running locally before
  `connect_ib()` will succeed. `connect_ib()` returns `(False, None)`
  on any connection failure rather than crashing startup.
- `disconnect_ib()` is idempotent and safe to call on `None`.
- The execution-event handler is wired up by the live-sync service in
  `app.services.ib_live_sync`; this client just exposes the connection.
"""

from __future__ import annotations

import asyncio

from app.logging import get_logger

logger = get_logger(__name__)


# Hard timeout for the initial connection attempt. Without this, a
# misconfigured IB_HOST can hang the FastAPI lifespan indefinitely.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0


def _running_under_uvloop() -> bool:
    """True if the current asyncio event loop is uvloop.

    Code-review fix H8: ib_async installs `nest_asyncio.apply()` on
    import which is incompatible with uvloop. Detecting it lets us
    refuse the connect attempt with a clear log line instead of
    crashing the loop or silently breaking other coroutines.
    """

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return False
    return "uvloop" in type(loop).__module__


async def connect_ib(
    host: str,
    port: int,
    client_id: int,
    *,
    timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
):
    """Connect to TWS / IB Gateway. Returns the IB instance or None on failure.

    Lazy-imports `ib_async` so the rest of the app can run even if the
    library is not installed yet (e.g., during integration tests that
    don't need a real IB).

    Refuses to connect under uvloop because `ib_async` (via
    `nest_asyncio`) is incompatible with it. To use live IB sync, run
    uvicorn with `--loop asyncio`.
    """

    if _running_under_uvloop():
        logger.warning(
            "ib.connect.uvloop_unsupported",
            hint=(
                "ib_async (via nest_asyncio) is incompatible with uvloop. "
                "Run uvicorn with --loop asyncio to enable live IB sync."
            ),
        )
        return None

    try:
        from ib_async import IB
    except ImportError:
        logger.warning("ib.connect.lib_unavailable")
        return None

    ib = IB()
    try:
        await asyncio.wait_for(
            ib.connectAsync(host=host, port=port, clientId=client_id),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("ib.connect.timeout", host=host, port=port, client_id=client_id)
        return None
    except OSError as exc:
        logger.warning("ib.connect.refused", host=host, port=port, error=str(exc))
        return None
    except Exception as exc:  # noqa: BLE001 — never crash the lifespan on a flaky broker
        logger.warning("ib.connect.unknown_error", host=host, port=port, error=str(exc))
        return None

    logger.info("ib.connect.ok", host=host, port=port, client_id=client_id)
    return ib


async def disconnect_ib(ib) -> None:
    """Disconnect from IB. Safe to call on None or an already-disconnected client."""

    if ib is None:
        return
    try:
        if hasattr(ib, "isConnected") and ib.isConnected():
            ib.disconnect()
            logger.info("ib.disconnect.ok")
    except Exception as exc:  # noqa: BLE001 — best effort
        logger.warning("ib.disconnect.failed", error=str(exc))
