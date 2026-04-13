"""CSV export of the trade list (Story 4.7 / FR60)."""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from typing import Any

import asyncpg

from app.services.facets import build_where_clause
from app.services.pnl import compute_pnl

_COLUMNS = [
    "trade_id",
    "symbol",
    "asset_class",
    "side",
    "quantity",
    "entry_price",
    "exit_price",
    "opened_at",
    "closed_at",
    "pnl",
    "fees",
    "broker",
    "perm_id",
    "strategy",
    "trigger_type",
    "horizon",
    "mistake_tags",
]

_SQL = """
SELECT id, symbol, asset_class, side, quantity, entry_price, exit_price,
       opened_at, closed_at, pnl, fees, broker, perm_id, trigger_spec
  FROM trades
 WHERE {where_sql}
 ORDER BY opened_at DESC, id DESC
"""


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _from_spec(row: dict[str, Any], key: str) -> str:
    spec = row.get("trigger_spec") or {}
    if not isinstance(spec, dict):
        return ""
    val = spec.get(key)
    if val is None:
        return ""
    if isinstance(val, list):
        return ",".join(str(x) for x in val)
    return str(val)


async def export_trades_csv(
    conn: asyncpg.Connection,
    facets: dict[str, list[str]] | None = None,
) -> str:
    """Return a CSV string (with UTF-8 BOM) of all trades matching the
    facet selection. The BOM makes Excel auto-detect encoding on open.
    """

    facets = facets or {}
    where_sql, params = build_where_clause(facets)
    sql = _SQL.format(where_sql=where_sql)
    rows = await conn.fetch(sql, *params)

    buffer = StringIO()
    buffer.write("\ufeff")  # UTF-8 BOM — Excel compatibility
    writer = csv.DictWriter(buffer, fieldnames=_COLUMNS, lineterminator="\n")
    writer.writeheader()

    for row in rows:
        row_dict = dict(row)
        computed_pnl = compute_pnl(row_dict)
        writer.writerow(
            {
                "trade_id": row_dict["id"],
                "symbol": row_dict["symbol"],
                "asset_class": row_dict["asset_class"],
                "side": row_dict["side"],
                "quantity": row_dict["quantity"],
                "entry_price": row_dict["entry_price"],
                "exit_price": row_dict["exit_price"] or "",
                "opened_at": _iso(row_dict["opened_at"]),
                "closed_at": _iso(row_dict["closed_at"]),
                "pnl": row_dict["pnl"] if row_dict["pnl"] is not None else (computed_pnl or ""),
                "fees": row_dict["fees"],
                "broker": row_dict["broker"],
                "perm_id": row_dict["perm_id"],
                "strategy": _from_spec(row_dict, "strategy"),
                "trigger_type": _from_spec(row_dict, "trigger_type"),
                "horizon": _from_spec(row_dict, "horizon"),
                "mistake_tags": _from_spec(row_dict, "mistake_tags"),
            }
        )

    return buffer.getvalue()
