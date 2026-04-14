"""Fear & Greed / VIX fetchers (Epic 9 / Story 9.1 Task 2 + 3).

Pragmatic best-effort data sources:

- **Fear & Greed Index** via `https://api.alternative.me/fng/?limit=1`
  — free, no auth, returns a 0..100 int.

- **VIX** via the public Yahoo Finance v8 chart API (`^VIX`). No auth
  required but needs a plain User-Agent header or Yahoo serves 401.

Both fetchers return `None` on any failure (network error, malformed
response, rate-limited, timeout). The Story-9.1 AC #3 "bei Datenquellen-
Ausfall kein Silent Failure" path still persists a snapshot row with
a NULL field + a `fetch_errors` JSONB entry describing what failed,
so the daily heartbeat is never skipped just because alternative.me
was down for ten minutes.

These fetchers are pure functions: they take an `httpx.AsyncClient`,
return `(value, error)` tuples, and do NOT touch the database or the
settings singleton. Integration testability for free.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.logging import get_logger

logger = get_logger(__name__)


_FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
_VIX_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=1d"
_USER_AGENT = "ctrader/0.1 (+https://localhost/ Epic-9 regime snapshot)"
_DEFAULT_TIMEOUT = 5.0


async def fetch_fear_greed(
    client: httpx.AsyncClient,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> tuple[int | None, str | None]:
    """Return `(value, error)` for the current Fear & Greed index.

    On success, `value` is the 0..100 int and `error` is None.
    On failure, `value` is None and `error` carries a short diagnostic
    string (for persistence into `regime_snapshots.fetch_errors`).
    """

    try:
        response = await client.get(_FEAR_GREED_URL, timeout=timeout)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        data = payload.get("data")
        if not data:
            return None, "alternative.me returned empty data array"
        first = data[0]
        raw_value = first.get("value")
        if raw_value is None:
            return None, "alternative.me missing `value` field"
        value = int(raw_value)
        if not 0 <= value <= 100:
            return None, f"value out of range: {value}"
        return value, None
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        logger.warning("regime.fear_greed.fetch_failed", error=str(exc))
        return None, f"{type(exc).__name__}: {exc}"


async def fetch_vix(
    client: httpx.AsyncClient,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> tuple[Decimal | None, str | None]:
    """Return `(value, error)` for the most recent VIX close.

    Yahoo's v8 chart endpoint returns a nested array shape. We only
    care about the last non-null close from the `indicators.quote[0]
    .close` array. The response is small (<5 KB) but we still keep a
    hard timeout so a slow-loris Yahoo can't hang the daily snapshot
    job.
    """

    try:
        headers = {"User-Agent": _USER_AGENT}
        response = await client.get(_VIX_URL, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        chart = payload.get("chart") or {}
        result = (chart.get("result") or [None])[0]
        if result is None:
            return None, "yahoo returned empty chart.result"
        indicators = (result.get("indicators") or {}).get("quote") or []
        if not indicators:
            return None, "yahoo missing indicators.quote"
        closes = indicators[0].get("close") or []
        # Most recent non-None close.
        last_close = next((c for c in reversed(closes) if c is not None), None)
        if last_close is None:
            return None, "yahoo chart.close contained only nulls"
        value = Decimal(str(last_close)).quantize(Decimal("0.01"))
        return value, None
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
        InvalidOperation,
    ) as exc:
        logger.warning("regime.vix.fetch_failed", error=str(exc))
        return None, f"{type(exc).__name__}: {exc}"
