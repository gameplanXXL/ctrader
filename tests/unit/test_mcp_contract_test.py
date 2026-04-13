"""Unit tests for Story 5.4 contract-drift logic."""

from __future__ import annotations

from pathlib import Path

from app.services.mcp_contract_test import (
    _extract_tools,
    diff_contracts,
    load_snapshot,
)


def _tools_list_payload(tools: list[dict]) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": tools},
    }


def test_extract_tools_returns_name_to_dict_map() -> None:
    payload = _tools_list_payload([{"name": "fundamentals"}, {"name": "price"}, {"name": "news"}])
    tools = _extract_tools(payload)
    assert set(tools.keys()) == {"fundamentals", "price", "news"}


def test_extract_tools_ignores_malformed_entries() -> None:
    payload = _tools_list_payload(
        [
            {"name": "fundamentals"},
            "oops_string_tool",
            {"missing_name": True},
            {"name": 42},  # non-string name
        ]
    )
    tools = _extract_tools(payload)
    assert list(tools.keys()) == ["fundamentals"]


def test_diff_contracts_identical_returns_empty_lists() -> None:
    snapshot = _tools_list_payload(
        [{"name": "fundamentals", "description": "x"}, {"name": "news", "description": "y"}]
    )
    current = _tools_list_payload(
        [{"name": "fundamentals", "description": "x"}, {"name": "news", "description": "y"}]
    )
    added, removed, changed = diff_contracts(snapshot, current)
    assert added == []
    assert removed == []
    assert changed == []


def test_diff_contracts_detects_added_tool() -> None:
    snapshot = _tools_list_payload([{"name": "fundamentals"}])
    current = _tools_list_payload([{"name": "fundamentals"}, {"name": "news"}])
    added, removed, changed = diff_contracts(snapshot, current)
    assert added == ["news"]


def test_diff_contracts_detects_removed_tool() -> None:
    snapshot = _tools_list_payload([{"name": "fundamentals"}, {"name": "legacy"}])
    current = _tools_list_payload([{"name": "fundamentals"}])
    added, removed, changed = diff_contracts(snapshot, current)
    assert removed == ["legacy"]


def test_diff_contracts_detects_changed_tool() -> None:
    snapshot = _tools_list_payload([{"name": "fundamentals", "description": "old"}])
    current = _tools_list_payload([{"name": "fundamentals", "description": "new"}])
    added, removed, changed = diff_contracts(snapshot, current)
    assert changed == ["fundamentals"]


def test_load_snapshot_missing_dir_returns_none(tmp_path: Path) -> None:
    empty_dir = tmp_path / "missing"
    assert load_snapshot(empty_dir) is None


def test_load_snapshot_returns_latest_file(tmp_path: Path) -> None:
    (tmp_path / "week0-20260101.json").write_text('{"result":{"tools":[]}}')
    (tmp_path / "week0-20260310.json").write_text('{"result":{"tools":[{"name":"x"}]}}')
    loaded = load_snapshot(tmp_path)
    assert loaded is not None
    payload, version = loaded
    assert version == "week0-20260310"
    assert _extract_tools(payload) == {"x": {"name": "x"}}
