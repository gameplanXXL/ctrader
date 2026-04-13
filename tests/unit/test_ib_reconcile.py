"""Unit tests for the Flex Web Service downloader (Story 2.2).

Reconciliation against a real DB is covered in
`tests/integration/test_ib_reconcile.py` (added later if needed). This
file focuses on the pure-function `download_flex_xml` happy/sad paths
using `httpx.MockTransport`.
"""

from __future__ import annotations

import httpx

from app.services.ib_reconcile import _extract_xml_value, download_flex_xml


def _http_handler_factory(responses: list[httpx.Response]):
    """Return a MockTransport handler that yields each response in order.

    Lets us simulate the two-step Flex flow (request → poll → final).
    """

    iterator = iter(responses)

    def _handler(_request: httpx.Request) -> httpx.Response:
        try:
            return next(iterator)
        except StopIteration:
            return httpx.Response(500, text="<unexpected/>")

    return _handler


# ---------------------------------------------------------------------------
# Helper — _extract_xml_value
# ---------------------------------------------------------------------------


def test_extract_xml_value_returns_inner_text() -> None:
    body = "<Status>Success</Status><ReferenceCode>ABC123</ReferenceCode>"
    assert _extract_xml_value(body, "ReferenceCode") == "ABC123"
    assert _extract_xml_value(body, "Status") == "Success"


def test_extract_xml_value_returns_none_for_missing_tag() -> None:
    assert _extract_xml_value("<Foo>bar</Foo>", "Bar") is None
    assert _extract_xml_value("", "X") is None


# ---------------------------------------------------------------------------
# download_flex_xml — happy path
# ---------------------------------------------------------------------------


async def test_download_returns_xml_on_success() -> None:
    final_xml = '<?xml version="1.0"?><FlexQueryResponse><FlexStatements/></FlexQueryResponse>'
    responses = [
        httpx.Response(
            200,
            text="<FlexStatementResponse><Status>Success</Status><ReferenceCode>REF-1</ReferenceCode></FlexStatementResponse>",
        ),
        httpx.Response(200, text=final_xml),
    ]
    client = httpx.AsyncClient(transport=httpx.MockTransport(_http_handler_factory(responses)))

    result = await download_flex_xml("token", "query-1", client=client)

    assert result == final_xml
    await client.aclose()


async def test_download_polls_until_ready_then_returns_xml() -> None:
    """First request returns reference code, first poll says 'in progress'
    (1019), second poll returns the XML.
    """

    final_xml = "<FlexQueryResponse><Trades/></FlexQueryResponse>"
    responses = [
        httpx.Response(
            200,
            text="<FlexStatementResponse><Status>Success</Status><ReferenceCode>REF-2</ReferenceCode></FlexStatementResponse>",
        ),
        httpx.Response(
            200,
            text="<FlexStatementResponse><ErrorCode>1019</ErrorCode><ErrorMessage>In progress</ErrorMessage></FlexStatementResponse>",
        ),
        httpx.Response(200, text=final_xml),
    ]
    client = httpx.AsyncClient(transport=httpx.MockTransport(_http_handler_factory(responses)))

    # Override the poll interval so the test runs in milliseconds.
    import app.services.ib_reconcile as mod

    original = mod.POLL_INTERVAL_SECONDS
    mod.POLL_INTERVAL_SECONDS = 0.0
    try:
        result = await download_flex_xml("token", "query-2", client=client)
    finally:
        mod.POLL_INTERVAL_SECONDS = original

    assert result == final_xml
    await client.aclose()


# ---------------------------------------------------------------------------
# download_flex_xml — sad paths
# ---------------------------------------------------------------------------


async def test_download_returns_none_on_request_error() -> None:
    responses = [
        httpx.Response(
            200,
            text="<FlexStatementResponse><Status>Fail</Status><ErrorCode>1010</ErrorCode><ErrorMessage>Bad token</ErrorMessage></FlexStatementResponse>",
        ),
    ]
    client = httpx.AsyncClient(transport=httpx.MockTransport(_http_handler_factory(responses)))

    result = await download_flex_xml("bad-token", "q", client=client)
    assert result is None
    await client.aclose()


async def test_download_returns_none_on_http_error() -> None:
    def _failing(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(_failing))

    result = await download_flex_xml("token", "q", client=client)
    assert result is None
    await client.aclose()


async def test_download_returns_none_when_reference_code_missing() -> None:
    responses = [
        httpx.Response(200, text="<unknown/>"),  # no ReferenceCode tag
    ]
    client = httpx.AsyncClient(transport=httpx.MockTransport(_http_handler_factory(responses)))

    result = await download_flex_xml("token", "q", client=client)
    assert result is None
    await client.aclose()


async def test_download_returns_none_after_poll_exhaustion() -> None:
    """Reference returned, but every poll says 'in progress' → exhaust max attempts."""

    in_progress = httpx.Response(
        200,
        text="<FlexStatementResponse><ErrorCode>1019</ErrorCode></FlexStatementResponse>",
    )
    responses = [
        httpx.Response(
            200,
            text="<FlexStatementResponse><ReferenceCode>REF-3</ReferenceCode></FlexStatementResponse>",
        ),
    ] + [in_progress] * 20  # more than MAX_POLL_ATTEMPTS
    client = httpx.AsyncClient(transport=httpx.MockTransport(_http_handler_factory(responses)))

    import app.services.ib_reconcile as mod

    original = mod.POLL_INTERVAL_SECONDS
    mod.POLL_INTERVAL_SECONDS = 0.0
    try:
        result = await download_flex_xml("token", "q", client=client)
    finally:
        mod.POLL_INTERVAL_SECONDS = original

    assert result is None
    await client.aclose()
