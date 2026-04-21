"""Unit tests for the `--pull` flag of the IB Flex CLI (Story 2.5).

All network and DB interactions are mocked — the test validates the
CLI contract (argparse, exit codes, error messages) and the wiring
between `download_flex_xml` and `import_flex_xml`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.cli import ib_flex_import as cli
from app.services.ib_flex_import import ImportResult


@pytest.fixture(autouse=True)
def _silence_configure_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI calls `configure_logging()` which opens a
    RotatingFileHandler against `data/logs/ctrader.log`. That path may
    be read-only in the test sandbox. Stub it out — structlog stays
    usable via its default dev-friendly processors."""

    monkeypatch.setattr(cli, "configure_logging", lambda: None)


# ---------------------------------------------------------------------------
# argparse — mutual exclusion and required-one (AC 8)
# ---------------------------------------------------------------------------


def test_argparse_rejects_no_arguments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Neither --pull nor a file path → argparse error (exit 2)."""

    monkeypatch.setattr(sys, "argv", ["prog"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 2


def test_argparse_rejects_both_file_and_pull(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--pull AND a file path is mutually exclusive (exit 2)."""

    monkeypatch.setattr(sys, "argv", ["prog", "--pull", "/tmp/fake.xml"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# --pull missing secrets (AC 6)
# ---------------------------------------------------------------------------


def test_pull_without_token_exits_4(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit code 4 + stderr message when IB_FLEX_TOKEN is unset."""

    monkeypatch.setattr(cli.settings, "ib_flex_token", None)
    monkeypatch.setattr(cli.settings, "ib_flex_query_id", "q-1")
    monkeypatch.setattr(sys, "argv", ["prog", "--pull"])

    exit_code = cli.main()
    err = capsys.readouterr().err
    assert exit_code == 4
    assert "IB_FLEX_TOKEN" in err
    assert "IB_FLEX_QUERY_ID" in err


def test_pull_without_query_id_exits_4(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit code 4 when IB_FLEX_QUERY_ID is unset — same treatment."""

    monkeypatch.setattr(cli.settings, "ib_flex_token", "tok-1")
    monkeypatch.setattr(cli.settings, "ib_flex_query_id", None)
    monkeypatch.setattr(sys, "argv", ["prog", "--pull"])

    exit_code = cli.main()
    err = capsys.readouterr().err
    assert exit_code == 4
    assert "must be set in .env" in err


# ---------------------------------------------------------------------------
# --pull download failure (AC 7)
# ---------------------------------------------------------------------------


def test_pull_download_returns_none_exits_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit code 3 + stderr message when the Flex download returns None."""

    monkeypatch.setattr(cli.settings, "ib_flex_token", "tok-1")
    monkeypatch.setattr(cli.settings, "ib_flex_query_id", "q-1")
    monkeypatch.setattr(cli, "download_flex_xml", AsyncMock(return_value=None))
    monkeypatch.setattr(sys, "argv", ["prog", "--pull"])

    exit_code = cli.main()
    err = capsys.readouterr().err
    assert exit_code == 3
    assert "Flex download failed" in err


# ---------------------------------------------------------------------------
# --pull happy path (AC 5)
# ---------------------------------------------------------------------------


async def _noop_close(_conn: object) -> None:
    return None


class _FakeConn:
    async def close(self) -> None:
        return None

    async def execute(self, *_args: object, **_kwargs: object) -> str:
        return "INSERT 0 1"

    async def fetch(self, *_args: object, **_kwargs: object) -> list[object]:
        return []

    async def fetchval(self, *_args: object, **_kwargs: object) -> object:
        return None


def test_pull_happy_path_downloads_and_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full happy path:
    - secrets present
    - download returns XML
    - import_flex_xml is called with that XML
    - exit code 0
    """

    monkeypatch.setattr(cli.settings, "ib_flex_token", "tok-1")
    monkeypatch.setattr(cli.settings, "ib_flex_query_id", "q-1")

    xml_payload = '<?xml version="1.0"?><FlexQueryResponse/>'
    download_mock = AsyncMock(return_value=xml_payload)
    import_mock = AsyncMock(
        return_value=ImportResult(parsed=3, inserted=2, skipped_duplicate=1)
    )
    connect_mock = AsyncMock(return_value=_FakeConn())

    monkeypatch.setattr(cli, "download_flex_xml", download_mock)
    monkeypatch.setattr(cli, "import_flex_xml", import_mock)
    monkeypatch.setattr(cli.asyncpg, "connect", connect_mock)
    monkeypatch.setattr(sys, "argv", ["prog", "--pull"])

    exit_code = cli.main()

    assert exit_code == 0
    download_mock.assert_awaited_once_with("tok-1", "q-1")
    import_mock.assert_awaited_once()
    # Verify the downloaded XML was the one passed to import_flex_xml.
    _, passed_xml = import_mock.await_args.args
    assert passed_xml == xml_payload


# ---------------------------------------------------------------------------
# File-mode regression (AC existing Story 2.1)
# ---------------------------------------------------------------------------


def test_file_mode_calls_import_flex_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """File-on-disk path must still work unchanged — a regression
    guard for the Story 2.1 behaviour."""

    xml = tmp_path / "trades.xml"
    xml.write_text("<FlexQueryResponse/>")

    import_file_mock = AsyncMock(return_value=ImportResult(parsed=1, inserted=1))
    connect_mock = AsyncMock(return_value=_FakeConn())

    monkeypatch.setattr(cli, "import_flex_file", import_file_mock)
    monkeypatch.setattr(cli.asyncpg, "connect", connect_mock)
    monkeypatch.setattr(sys, "argv", ["prog", str(xml)])

    exit_code = cli.main()
    assert exit_code == 0
    import_file_mock.assert_awaited_once()
