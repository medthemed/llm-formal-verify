"""Tests for project config loading and option resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_formal_verify import (
    ProjectConfig,
    SpecError,
    discover_config,
    load_config,
    resolve_check_options,
)
from llm_formal_verify.config import DEFAULT_BOUND, DEFAULT_SEARCH


def test_defaults_when_no_config(tmp_path: Path):
    cfg = discover_config(tmp_path)
    assert cfg.bound == DEFAULT_BOUND
    assert cfg.search == DEFAULT_SEARCH
    assert cfg.source is None


def test_load_dot_lfv_json(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text(json.dumps({"bound": 12, "search": "dfs"}), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.bound == 12
    assert cfg.search == "dfs"
    assert cfg.source == str(path)


def test_discover_prefers_dot_lfv_over_lfv_config(tmp_path: Path):
    (tmp_path / ".lfv.json").write_text(json.dumps({"bound": 5}), encoding="utf-8")
    (tmp_path / "lfv.config.json").write_text(json.dumps({"bound": 99}), encoding="utf-8")
    cfg = discover_config(tmp_path)
    assert cfg.bound == 5


def test_discover_falls_back_to_lfv_config_json(tmp_path: Path):
    (tmp_path / "lfv.config.json").write_text(json.dumps({"bound": 7}), encoding="utf-8")
    cfg = discover_config(tmp_path)
    assert cfg.bound == 7


def test_partial_config_uses_defaults_for_missing_keys(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text(json.dumps({"bound": 3}), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.bound == 3
    assert cfg.search == DEFAULT_SEARCH


def test_invalid_json_raises_spec_error(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SpecError, match="not valid JSON"):
        load_config(path)


def test_non_object_raises_spec_error(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(SpecError, match="must be a JSON object"):
        load_config(path)


def test_bad_bound_raises_spec_error(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text(json.dumps({"bound": "ten"}), encoding="utf-8")
    with pytest.raises(SpecError, match="'bound' must be an integer"):
        load_config(path)


def test_negative_bound_raises_spec_error(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text(json.dumps({"bound": -1}), encoding="utf-8")
    with pytest.raises(SpecError, match="'bound' must be >= 0"):
        load_config(path)


def test_bad_search_raises_spec_error(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text(json.dumps({"search": "random"}), encoding="utf-8")
    with pytest.raises(SpecError, match="'search' must be one of"):
        load_config(path)


def test_extra_keys_are_ignored(tmp_path: Path):
    path = tmp_path / ".lfv.json"
    path.write_text(json.dumps({"bound": 4, "future_key": True}), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.bound == 4


def test_resolve_cli_overrides_config():
    cfg = ProjectConfig(bound=10, search="dfs")
    bound, search = resolve_check_options(bound=3, search="bfs", config=cfg)
    assert bound == 3
    assert search == "bfs"


def test_resolve_falls_back_to_config():
    cfg = ProjectConfig(bound=10, search="dfs")
    bound, search = resolve_check_options(config=cfg)
    assert bound == 10
    assert search == "dfs"


def test_resolve_partial_cli_overrides():
    cfg = ProjectConfig(bound=10, search="dfs")
    bound, search = resolve_check_options(bound=None, search="bfs", config=cfg)
    assert bound == 10
    assert search == "bfs"


def test_resolve_from_directory(tmp_path: Path):
    (tmp_path / ".lfv.json").write_text(json.dumps({"bound": 6}), encoding="utf-8")
    bound, search = resolve_check_options(directory=tmp_path)
    assert bound == 6
    assert search == "bfs"
