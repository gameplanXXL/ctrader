"""Tests for H3 + H6 defensive contract-test fixes."""

from __future__ import annotations

from pathlib import Path

from app.services.mcp_contract_test import _extract_tools, load_snapshot

# ---------------------------------------------------------------------------
# H3 — _extract_tools defensiveness
# ---------------------------------------------------------------------------


def test_extract_tools_on_non_dict_payload_returns_empty() -> None:
    assert _extract_tools("string") == {}
    assert _extract_tools(None) == {}
    assert _extract_tools([]) == {}
    assert _extract_tools(42) == {}


def test_extract_tools_on_non_dict_result_returns_empty() -> None:
    assert _extract_tools({"result": "oops"}) == {}
    assert _extract_tools({"result": None}) == {}
    assert _extract_tools({"result": []}) == {}


def test_extract_tools_on_non_list_tools_returns_empty() -> None:
    assert _extract_tools({"result": {"tools": "not-a-list"}}) == {}
    assert _extract_tools({"result": {"tools": None}}) == {}


def test_extract_tools_drops_empty_name_tools() -> None:
    payload = {
        "result": {
            "tools": [
                {"name": ""},
                {"name": "real_tool"},
            ]
        }
    }
    tools = _extract_tools(payload)
    assert list(tools.keys()) == ["real_tool"]


# ---------------------------------------------------------------------------
# H6 — snapshot filename canonical-format filter
# ---------------------------------------------------------------------------


def test_load_snapshot_ignores_off_spec_filenames(tmp_path: Path) -> None:
    """Code-review H6 / BH-20 / EC-24: `week0-final.json` must NOT
    become the drift baseline — only `week0-YYYYMMDD.json` counts."""

    (tmp_path / "week0-final.json").write_text('{"result":{"tools":[]}}')
    (tmp_path / "week0-legacy.json").write_text('{"result":{"tools":[]}}')
    (tmp_path / "week0-20260410.json").write_text('{"result":{"tools":[{"name":"fundamentals"}]}}')
    loaded = load_snapshot(tmp_path)
    assert loaded is not None
    payload, version = loaded
    assert version == "week0-20260410"
    assert _extract_tools(payload) == {"fundamentals": {"name": "fundamentals"}}


def test_load_snapshot_picks_latest_date(tmp_path: Path) -> None:
    (tmp_path / "week0-20260101.json").write_text('{"result":{"tools":[]}}')
    (tmp_path / "week0-20260415.json").write_text('{"result":{"tools":[{"name":"x"}]}}')
    loaded = load_snapshot(tmp_path)
    assert loaded is not None
    _, version = loaded
    assert version == "week0-20260415"


def test_load_snapshot_rejects_null_json(tmp_path: Path) -> None:
    (tmp_path / "week0-20260101.json").write_text("null")
    assert load_snapshot(tmp_path) is None


def test_load_snapshot_rejects_non_dict_json(tmp_path: Path) -> None:
    (tmp_path / "week0-20260101.json").write_text("[1, 2, 3]")
    assert load_snapshot(tmp_path) is None


def test_load_snapshot_empty_file_returns_none(tmp_path: Path) -> None:
    (tmp_path / "week0-20260101.json").write_text("")
    assert load_snapshot(tmp_path) is None
