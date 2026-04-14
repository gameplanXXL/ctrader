"""IB error-code → deutsche Meldung mapping (Epic 12 / Story 12.4).

Translates the most common `ib_async` / TWS API error codes into
operator-facing German messages + a `transient`/`terminal`
classification so the Quick-Order error handler can decide between
"retry automatically" and "show a persistent error toast".

The mapping is intentionally incomplete — we only cover the codes
Chef is likely to hit in a Swing-Order context. Unknown codes fall
back to `("terminal", f"Unbekannter IB-Fehler (IB {code})")`.

Extend via migration + code review when new codes surface in the
wild. A PR that adds a code must also add a unit test in
`tests/unit/test_ib_error_map.py`.
"""

from __future__ import annotations

from typing import Literal

ErrorCategory = Literal["transient", "terminal"]


# (category, german_message) per IB error code.
_IB_ERROR_MAP: dict[int, tuple[ErrorCategory, str]] = {
    # Transient — retryable with exponential backoff
    1100: ("transient", "Verbindung zur IB Gateway verloren"),
    1101: ("transient", "Verbindung wiederhergestellt (ohne Daten-Loss)"),
    1102: ("transient", "Verbindung wiederhergestellt (mit Daten-Verlust)"),
    2103: ("transient", "Market-Data-Farm-Verbindung unterbrochen"),
    2104: ("transient", "Market-Data-Farm-Verbindung OK"),
    2105: ("transient", "HMDS-Farm-Verbindung unterbrochen"),
    2106: ("transient", "HMDS-Farm-Verbindung OK"),
    # Terminal — operator must act
    200: ("terminal", "Keine Security-Definition für Symbol / Strike / Expiry"),
    201: ("terminal", "Order abgelehnt"),
    202: ("terminal", "Order storniert (extern)"),
    321: ("terminal", "Ungültige Order-Parameter"),
    322: ("terminal", "Order wurde auf dem Server zu Recht abgelehnt"),
    399: ("terminal", "Warnmeldung — Order trotzdem angenommen"),
    404: ("terminal", "Kein-Short-Locate verfügbar"),
    10148: ("terminal", "Order-Referenz nicht mehr gefunden"),
    10197: ("terminal", "Keine Handelsberechtigung für dieses Symbol"),
    10318: ("terminal", "Margin-Fehler — nicht genügend Buying Power"),
    10322: ("terminal", "Instrument nicht mehr handelbar (Markt geschlossen?)"),
}


def classify(error_code: int | None) -> tuple[ErrorCategory, str]:
    """Return `(category, german_message)` for an IB error code.

    `None` is treated as a "connection not established" terminal
    error. Unknown codes fall back to `terminal` with the raw code
    in the message so the operator has something to search for.
    """

    if error_code is None:
        return ("terminal", "IB TWS/Gateway nicht verbunden")
    mapping = _IB_ERROR_MAP.get(error_code)
    if mapping is None:
        return ("terminal", f"Unbekannter IB-Fehler (IB {error_code})")
    return mapping


def is_transient(error_code: int | None) -> bool:
    """Convenience predicate for the retry loop."""

    return classify(error_code)[0] == "transient"


def format_for_operator(error_code: int | None) -> str:
    """Render `"<message> (IB <code>)"` — used by the error toast.

    A terminal error with the message "Margin-Fehler — nicht
    genügend Buying Power (IB 10318)" is a lot more actionable than
    just a numeric code.
    """

    category, message = classify(error_code)
    if error_code is None:
        return message
    return f"{message} (IB {error_code})"


class IBTransientError(ConnectionError):
    """Network / reconnect / transient — retry with exponential backoff."""

    def __init__(self, message: str, *, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class IBTerminalError(RuntimeError):
    """Margin / invalid symbol / market closed — propagate to operator."""

    def __init__(self, message: str, *, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.german_message = message
