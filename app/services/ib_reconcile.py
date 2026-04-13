"""IB Flex Query reconciliation against the live-synced trades table.

Story 2.2 FR5: Flex Query is **source of truth**. The live-sync handler
in `ib_live_sync.py` fires immediately on `execDetailsEvent` and may
have stale fees / pnl until IB finalizes the execution overnight. The
reconcile job runs daily and overwrites any divergent fields with the
Flex values.

Story 2.2 scope here: the reconcile *function* + the Flex Web Service
download wrapper. The APScheduler hookup is intentionally NOT here —
it lives in Story 12.1 (Scheduled-Jobs-Framework). Until then the
function is callable manually via the CLI in Story 2.1 or by future
operators code.

Reconciliation rule (FR5):
- For every trade in the Flex export that already exists in the DB,
  UPDATE the divergent fields (`fees`, `pnl`, `exit_price`, `closed_at`).
- For trades that don't exist yet, INSERT them (handled by the existing
  `insert_trades` upsert path).
- Live-sync rows are NEVER deleted by reconcile — only updated.
"""

from __future__ import annotations

import asyncio

import asyncpg
import httpx

from app.logging import get_logger
from app.models.trade import TradeIn
from app.services.ib_flex_import import import_flex_xml, parse_flex_xml

logger = get_logger(__name__)


# IB Flex Web Service endpoints (documented at IB).
FLEX_REQUEST_URL = (
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest"
)
FLEX_DOWNLOAD_URL = (
    "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement"
)

# Hard timeout for both the request and the download phases (NFR-I1
# spirit — never let an external service hang the reconcile job).
DEFAULT_FLEX_TIMEOUT_SECONDS = 30.0

# Two-step download: request returns a reference code, then we poll
# the download endpoint until the statement is ready. This sleep
# spaces out the polls.
POLL_INTERVAL_SECONDS = 3.0
MAX_POLL_ATTEMPTS = 10


# ---------------------------------------------------------------------------
# Flex Web Service download
# ---------------------------------------------------------------------------


async def download_flex_xml(
    token: str,
    query_id: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_FLEX_TIMEOUT_SECONDS,
) -> str | None:
    """Two-step Flex download: request → poll → return XML body.

    Returns None on any failure (network, HTTP, malformed XML). Never
    raises so the reconcile job stays best-effort.
    """

    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    try:
        # Step 1 — request a statement, get a reference code.
        ref_resp = await http.get(
            FLEX_REQUEST_URL,
            params={"t": token, "q": query_id, "v": "3"},
            timeout=timeout,
        )
        ref_resp.raise_for_status()

        # The response is XML containing <ReferenceCode> on success or
        # <ErrorCode> + <ErrorMessage> on failure. We do a substring
        # scan to keep the parser dependency-free.
        ref_text = ref_resp.text
        if "<ErrorCode>" in ref_text:
            logger.warning("ib_flex_download.request_error", body=ref_text[:200])
            return None
        ref_code = _extract_xml_value(ref_text, "ReferenceCode")
        if ref_code is None:
            logger.warning("ib_flex_download.no_reference_code", body=ref_text[:200])
            return None

        # Step 2 — poll for the statement until it's ready.
        for attempt in range(MAX_POLL_ATTEMPTS):
            stmt_resp = await http.get(
                FLEX_DOWNLOAD_URL,
                params={"t": token, "q": ref_code, "v": "3"},
                timeout=timeout,
            )
            stmt_resp.raise_for_status()
            body = stmt_resp.text

            if "<ErrorCode>" in body:
                code = _extract_xml_value(body, "ErrorCode")
                # 1019 = "Statement generation in progress" — retry.
                if code == "1019":
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue
                logger.warning("ib_flex_download.poll_error", code=code, attempt=attempt)
                return None

            # Accept the body as a Flex statement if the wrapper element
            # appears anywhere — `<?xml ... ?>` declarations or
            # `<!DOCTYPE>` lines may precede it.
            if "<FlexQueryResponse" in body:
                logger.info("ib_flex_download.ok", attempts=attempt + 1, bytes=len(body))
                return body

            # Unknown shape — fail soft.
            logger.warning("ib_flex_download.unknown_body", attempt=attempt, snippet=body[:200])
            return None

        logger.warning("ib_flex_download.poll_exhausted", attempts=MAX_POLL_ATTEMPTS)
        return None

    except httpx.HTTPError as exc:
        logger.warning("ib_flex_download.http_error", error=str(exc))
        return None
    except Exception as exc:  # noqa: BLE001 — never crash the reconcile job
        logger.warning("ib_flex_download.unknown_error", error=str(exc))
        return None
    finally:
        if own_client:
            await http.aclose()


def _extract_xml_value(xml_text: str, tag: str) -> str | None:
    """Tiny substring scan for `<tag>...</tag>` so we don't need lxml."""

    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    start = xml_text.find(open_tag)
    if start < 0:
        return None
    start += len(open_tag)
    end = xml_text.find(close_tag, start)
    if end < 0:
        return None
    return xml_text[start:end].strip()


# ---------------------------------------------------------------------------
# Reconciliation against the trades table
# ---------------------------------------------------------------------------


_RECONCILE_UPDATE_SQL = """
UPDATE trades
   SET exit_price  = COALESCE($1, exit_price),
       closed_at   = COALESCE($2, closed_at),
       pnl         = COALESCE($3, pnl),
       fees        = $4,
       updated_at  = NOW()
 WHERE broker = $5 AND perm_id = $6
   AND (
        fees       IS DISTINCT FROM $4
        OR pnl     IS DISTINCT FROM $3
        OR exit_price IS DISTINCT FROM $1
        OR closed_at IS DISTINCT FROM $2
   )
RETURNING id
"""


async def reconcile_with_flex(conn: asyncpg.Connection, xml_text: str) -> dict[str, int]:
    """Reconcile the trades table against a Flex XML payload.

    For every trade in the XML:
    - If it already exists: UPDATE the divergent fields (Flex wins, FR5).
    - If it doesn't: INSERT via the standard upsert path.

    Returns a counts dict: `{"updated": N, "inserted": M, "unchanged": K, "skipped": S}`.
    """

    trades, skipped_multi_leg, skipped_invalid = parse_flex_xml(xml_text)
    counts = {
        "updated": 0,
        "inserted": 0,
        "unchanged": 0,
        "skipped_multi_leg": skipped_multi_leg,
        "skipped_invalid": skipped_invalid,
    }

    for trade in trades:
        existing = await conn.fetchrow(
            "SELECT fees, pnl, exit_price, closed_at FROM trades WHERE broker = $1 AND perm_id = $2",
            trade.broker.value,
            trade.perm_id,
        )

        if existing is None:
            # Fresh trade — fall through to the regular upsert.
            await _insert_via_import(conn, trade)
            counts["inserted"] += 1
            continue

        # Existing trade — issue an UPDATE that only fires if any of
        # the reconciled fields differ. The WHERE clause guarantees
        # we don't bump `updated_at` on no-op reconciles.
        updated = await conn.fetchrow(
            _RECONCILE_UPDATE_SQL,
            trade.exit_price,
            trade.closed_at,
            trade.pnl,
            trade.fees,
            trade.broker.value,
            trade.perm_id,
        )
        if updated:
            counts["updated"] += 1
            logger.info(
                "ib_reconcile.updated",
                perm_id=trade.perm_id,
                symbol=trade.symbol,
            )
        else:
            counts["unchanged"] += 1

    logger.info("ib_reconcile.done", **counts)
    return counts


async def _insert_via_import(conn: asyncpg.Connection, trade: TradeIn) -> None:
    """Convenience: reuse the Flex importer's upsert path for a single trade."""

    from app.services.ib_flex_import import insert_trades

    await insert_trades(conn, [trade])


# ---------------------------------------------------------------------------
# End-to-end orchestration (Flex download → reconcile)
# ---------------------------------------------------------------------------


async def run_nightly_reconcile(
    conn: asyncpg.Connection,
    token: str,
    query_id: str,
) -> dict[str, int] | None:
    """Top-level entry point: download Flex XML and reconcile.

    Returns the counts dict on success, None if the download itself
    failed. Never raises — this is meant to be called from a scheduled
    job and must degrade gracefully.
    """

    xml = await download_flex_xml(token, query_id)
    if xml is None:
        logger.warning("ib_reconcile.download_failed")
        return None

    return await reconcile_with_flex(conn, xml)


# Note: `import_flex_xml` is re-exported for convenience so the CLI
# from Story 2.1 can also be used as a manual reconcile entry point.
__all__ = [
    "download_flex_xml",
    "import_flex_xml",
    "reconcile_with_flex",
    "run_nightly_reconcile",
]
