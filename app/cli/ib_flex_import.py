"""CLI: `python -m app.cli.ib_flex_import <xml-file>` — bulk-import a
historical IB Flex Query export into the trades table.

Story 2.1 scope: file-on-disk import. Story 2.2 adds the live Flex
Web Service download.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

from app.config import settings
from app.logging import configure_logging, get_logger
from app.services.ib_flex_import import import_flex_file


async def _run(xml_path: Path) -> int:
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
        parsed=result.parsed,
        inserted=result.inserted,
        skipped_duplicate=result.skipped_duplicate,
        skipped_multi_leg=result.skipped_multi_leg,
        skipped_invalid=result.skipped_invalid,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.ib_flex_import",
        description="Import a historical IB Flex Query XML file into ctrader.",
    )
    parser.add_argument("xml_file", type=Path, help="Path to the Flex Query XML file")
    args = parser.parse_args()

    configure_logging()
    return asyncio.run(_run(args.xml_file))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
