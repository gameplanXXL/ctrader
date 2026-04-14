"""IB Quick-Order routes (Epic 12).

Exposes:
- `GET  /trades/quick-order/form?symbol=...&asset_class=...` — form
  fragment (Story 12.1).
- `GET  /trades/quick-order/options-chain?symbol=...` — expiries + strikes
  dropdown data (Story 12.1 Task 4).
- `POST /trades/quick-order/preview` — Bestätigungs-Viewport with
  what-if margin (Story 12.2).
- `POST /trades/quick-order/submit` — atomic bracket submission
  (Story 12.2 Task 8).

All endpoints degrade gracefully when `app.state.ib_quick_order_client`
is not wired (returns None) — the form renders a banner instructing
Chef to start TWS or IB Gateway.

NOTE: this module omits `from __future__ import annotations` on
purpose so FastAPI's response-model introspection on `Request` /
`TemplateResponse` works under Python 3.12 without the
future-annotations stringization issue. Same convention as
`app/routers/approvals.py` / `app/routers/strategies.py`.
"""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.filters.formatting import JINJA_FILTERS
from app.logging import get_logger
from app.services.ib_quick_order import (
    QuickOrderForm,
    QuickOrderSubmitError,
    compute_preview,
    submit_quick_order,
)

logger = get_logger(__name__)

router = APIRouter(tags=["quick-order"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
for _name, _fn in JINJA_FILTERS.items():
    templates.env.filters[_name] = _fn


def _get_client(request: Request):
    return getattr(request.app.state, "ib_quick_order_client", None)


def _coerce_decimal(value: Any, field: str) -> Decimal:
    if value is None or value == "":
        raise HTTPException(status_code=422, detail=f"{field} required")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail=f"{field} invalid decimal: {value}") from exc


def _coerce_optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _coerce_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


# Code-review BH-4 / Auditor 12.1 #6: enforce the spec's "min 5 DTE"
# invariant at the router boundary. Options closer than 5 DTE are
# near-assignment territory and Chef must use the post-hoc
# taxonomy_mistake path, not Quick-Order.
_MIN_OPTION_DTE = 5


def _parse_form(form: dict[str, Any]) -> QuickOrderForm:
    """Translate raw form dict → `QuickOrderForm` with validation.

    Raises `HTTPException(422)` on any required-field miss or type
    error so the HTMX swap can display the error inline.
    """

    asset_class = form.get("asset_class", "stock")
    if asset_class not in ("stock", "option"):
        raise HTTPException(status_code=422, detail="asset_class must be stock|option")

    symbol = str(form.get("symbol", "")).strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="symbol required")

    side = str(form.get("side", "")).upper().strip()
    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=422, detail="side must be BUY|SELL")

    quantity = _coerce_decimal(form.get("quantity"), "quantity")
    if quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be > 0")

    limit_price = _coerce_decimal(form.get("limit_price"), "limit_price")
    if limit_price <= 0:
        raise HTTPException(status_code=422, detail="limit_price must be > 0")

    stop_price = _coerce_decimal(form.get("stop_price"), "stop_price")
    if stop_price <= 0:
        raise HTTPException(status_code=422, detail="stop_price must be > 0")

    # Code-review BH-3 / Auditor 12.1 #6: stop on the wrong side of
    # limit means negative risk — an input error, not a valid order.
    # BUY: stop < limit (stop out below entry). SELL: stop > limit.
    if side == "BUY" and stop_price >= limit_price:
        raise HTTPException(
            status_code=422,
            detail="Stop-Loss muss unter dem Limit-Preis liegen (BUY)",
        )
    if side == "SELL" and stop_price <= limit_price:
        raise HTTPException(
            status_code=422,
            detail="Stop-Loss muss über dem Limit-Preis liegen (SELL)",
        )

    option_expiry: date | None = None
    option_strike: Decimal | None = None
    option_right: str | None = None
    option_multiplier: int | None = None
    if asset_class == "option":
        option_expiry = _coerce_date(form.get("option_expiry"))
        option_strike = _coerce_optional_decimal(form.get("option_strike"))
        raw_right = str(form.get("option_right", "")).upper().strip()
        if raw_right not in ("C", "P"):
            raise HTTPException(status_code=422, detail="option_right must be C|P")
        option_right = raw_right
        if option_expiry is None or option_strike is None:
            raise HTTPException(
                status_code=422,
                detail="option_expiry + option_strike required for option orders",
            )
        # Code-review BH-4 / Auditor 12.1 #6: enforce DTE floor.
        dte = (option_expiry - date.today()).days
        if dte < _MIN_OPTION_DTE:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Option-Expiry {option_expiry.isoformat()} ist {dte} DTE — "
                    f"Minimum {_MIN_OPTION_DTE} DTE (unter 5 Tagen ist near-assignment)"
                ),
            )
        option_multiplier = int(form.get("option_multiplier") or 100)

    strategy_id_raw = form.get("strategy_id")
    strategy_id: int | None = None
    if strategy_id_raw not in (None, "", "None"):
        try:
            strategy_id = int(strategy_id_raw)
        except (TypeError, ValueError):
            strategy_id = None

    ack_raw = form.get("acknowledge_margin", "")
    acknowledge_margin = str(ack_raw).lower() in ("true", "on", "1", "yes")

    return QuickOrderForm(
        asset_class=asset_class,  # type: ignore[arg-type]
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        quantity=quantity,
        limit_price=limit_price,
        stop_price=stop_price,
        option_expiry=option_expiry,
        option_strike=option_strike,
        option_right=option_right,  # type: ignore[arg-type]
        option_multiplier=option_multiplier,
        strategy_id=strategy_id,
        trigger_source=str(form.get("trigger_source") or "").strip() or None,
        horizon=str(form.get("horizon") or "").strip() or None,
        notes=str(form.get("notes") or "").strip() or None,
        acknowledge_margin=acknowledge_margin,
    )


# ---------------------------------------------------------------------------
# GET /trades/quick-order/form
# ---------------------------------------------------------------------------


@router.get("/trades/quick-order/form", include_in_schema=False)
async def quick_order_form(
    request: Request,
    symbol: str | None = None,
    asset_class: str = "stock",
):
    """Render the Quick-Order form fragment.

    Story 12.1 AC #1: asset-class toggle (Stock | Option).
    Story 12.1 AC #7: disable submit when IB not connected.
    """

    client = _get_client(request)
    is_connected = bool(client and client.is_connected())
    return templates.TemplateResponse(
        request,
        "components/quick_order_form.html",
        {
            "symbol": symbol or "",
            "asset_class": asset_class if asset_class in ("stock", "option") else "stock",
            "ib_connected": is_connected,
        },
    )


# ---------------------------------------------------------------------------
# GET /trades/quick-order/options-chain
# ---------------------------------------------------------------------------


@router.get("/trades/quick-order/options-chain", include_in_schema=False)
async def quick_order_options_chain(
    request: Request,
    symbol: str,
) -> JSONResponse:
    """Return the option chain for an underlying as JSON.

    Shape: `{"symbol": "AAPL", "expiries_by_right": {"C": {...}, "P": {...}}}`.
    The form's Alpine.js state uses this to populate the Expiry +
    Strike dropdowns after the user picks an Option mode + Right.
    """

    client = _get_client(request)
    if client is None or not client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="IB TWS/Gateway nicht verbunden",
        )

    try:
        chain = await client.fetch_option_chain(symbol.upper())
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "quick_order.options_chain.fetch_failed",
            symbol=symbol,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"Chain fetch failed: {exc}") from None

    by_right: dict[str, dict[str, list[str]]] = {"C": {}, "P": {}}
    for entry in chain:
        expiry_key = entry.expiry.isoformat()
        by_right[entry.right].setdefault(expiry_key, []).append(str(entry.strike))
    return JSONResponse(
        {
            "symbol": symbol.upper(),
            "expiries_by_right": by_right,
        }
    )


# ---------------------------------------------------------------------------
# POST /trades/quick-order/preview
# ---------------------------------------------------------------------------


@router.post("/trades/quick-order/preview", include_in_schema=False)
async def quick_order_preview(request: Request):
    """Build and render the Bestätigungs-Viewport (Story 12.2 AC #1/#2).

    No DB writes. Runs `what_if_order` for margin display on
    Short-Options.
    """

    client = _get_client(request)
    if client is None or not client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="IB TWS/Gateway nicht verbunden",
        )

    raw_form = await request.form()
    form_dict = {k: raw_form.get(k) for k in raw_form}
    parsed = _parse_form(form_dict)

    preview = await compute_preview(client, parsed)
    return templates.TemplateResponse(
        request,
        "components/quick_order_preview.html",
        {"preview": preview},
    )


# ---------------------------------------------------------------------------
# POST /trades/quick-order/submit
# ---------------------------------------------------------------------------


@router.post("/trades/quick-order/submit", include_in_schema=False)
async def quick_order_submit(request: Request):
    """Atomic bracket submission (Story 12.2 AC #4/#5/#6).

    Persists the `quick_orders` row BEFORE the network call for
    NFR-R3a idempotency, runs `place_order_with_retry`, updates the
    row on result. Never returns 500 on transient IB errors — those
    are retried. Terminal IB errors surface as 422 with a
    human-readable German message.
    """

    client = _get_client(request)
    if client is None or not client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="IB TWS/Gateway nicht verbunden",
        )

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    raw_form = await request.form()
    form_dict = {k: raw_form.get(k) for k in raw_form}
    parsed = _parse_form(form_dict)

    try:
        async with db_pool.acquire() as conn:
            result = await submit_quick_order(conn, client, parsed)
    except QuickOrderSubmitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return Response(
        status_code=201,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {
                    "showToast": {
                        "message": (
                            f"Order #{result.quick_order_id} submitted ({result.ib_order_id})"
                        ),
                        "variant": "success",
                    }
                }
            ),
        },
    )
