"""CLI: import an IB Flex Query into the trades table.

Two modes:

    # Historical file-on-disk import (Story 2.1):
    python -m app.cli.ib_flex_import /path/to/flex.xml

    # On-demand Web-Service pull (Story 2.5):
    python -m app.cli.ib_flex_import --pull

The `--pull` flag requires `IB_FLEX_TOKEN` and `IB_FLEX_QUERY_ID` in
`.env`. It is the recommended entry point for the initial 12-month
backfill: temporarily set the IB-configured Flex Query period to
"Last 365 Days", run `--pull` once, then reset to the production
"Last 90 Days" sliding-window that the `ib_flex_nightly` scheduler
job uses.

Exit codes:
- 0  Success (trades parsed and upserted — duplicates counted via
     `UNIQUE(broker, perm_id)`, re-running is always safe)
- 2  argparse error (mutually-exclusive xml_file + --pull, missing arg)
- 3  `--pull`: Flex Web Service download returned no XML
- 4  `--pull`: IB_FLEX_TOKEN or IB_FLEX_QUERY_ID is unset
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

from app.config import settings
from app.logging import configure_logging, get_logger
from app.services.ib_flex_import import import_flex_file, import_flex_xml
from app.services.ib_reconcile import download_flex_xml


async def _run_file(xml_path: Path) -> int:
    logger = get_logger(__name__)

    if not xml_path.is_file():
        logger.error("ib_flex_cli.file_not_found", path=str(xml_path))
        return 2

    conn = await asyncpg.connect(dsn=settings.database_url)
    try:
        result = await import_flex_file(conn, xml_path)
    finally:
        await conn.close()

    logger.info(
        "ib_flex_cli.summary",
        mode="file",
        parsed=result.parsed,
        inserted=result.inserted,
        skipped_duplicate=result.skipped_duplicate,
        skipped_multi_leg=result.skipped_multi_leg,
        skipped_invalid=result.skipped_invalid,
    )
    return 0


async def _run_pull() -> int:
    logger = get_logger(__name__)

    token = settings.ib_flex_token
    query_id = settings.ib_flex_query_id
    if not token or not query_id:
        print(
            "IB_FLEX_TOKEN and IB_FLEX_QUERY_ID must be set in .env",
            file=sys.stderr,
        )
        logger.error("ib_flex_cli.pull_missing_secrets")
        return 4

    xml_text = await download_flex_xml(token, query_id)
    if xml_text is None:
        print("Flex download failed — see logs", file=sys.stderr)
        logger.error("ib_flex_cli.pull_download_failed")
        return 3

    conn = await asyncpg.connect(dsn=settings.database_url)
    try:
        result = await import_flex_xml(conn, xml_text)
    finally:
        await conn.close()

    logger.info(
        "ib_flex_cli.summary",
        mode="pull",
        bytes=len(xml_text),
        parsed=result.parsed,
        inserted=result.inserted,
        skipped_duplicate=result.skipped_duplicate,
        skipped_multi_leg=result.skipped_multi_leg,
        skipped_invalid=result.skipped_invalid,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.ib_flex_import",
        description=(
            "Import IB Flex Query trades into ctrader. "
            "Supply either a path to a downloaded XML file or --pull to "
            "fetch via the IB Flex Web Service."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "xml_file",
        nargs="?",
        type=Path,
        default=None,
        help="Path to a downloaded IB Flex Query XML file",
    )
    group.add_argument(
        "--pull",
        action="store_true",
        help=(
            "Fetch the configured Flex Query via the IB Web Service "
            "(requires IB_FLEX_TOKEN + IB_FLEX_QUERY_ID in .env)"
        ),
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    configure_logging()
    if args.pull:
        return asyncio.run(_run_pull())
    return asyncio.run(_run_file(args.xml_file))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
