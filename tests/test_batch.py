"""Tests for multi-spec batch checking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_formal_verify.batch import (
    BatchCheckResult,
    SpecOutcome,
    check_many,
    expand_spec_paths,
    load_spec_file,
)
from llm_formal_verify.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SAFE = EXAMPLES / "safe_transfer.json"
UNSAFE = EXAMPLES / "unsafe_transfer.json"


def test_expand_spec_paths_expands_directory(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("skip", encoding="utf-8")
    expanded = expand_spec_paths([tmp_path])
    names = [p.name for p in expanded]
    assert names == ["a.json", "b.json"]


def test_expand_spec_paths_keeps_files():
    expanded = expand_spec_paths([SAFE, UNSAFE])
    assert expanded == [Path(SAFE), Path(UNSAFE)]


def test_check_many_safe_and_unsafe():
    batch = check_many([SAFE, UNSAFE], bound=6)
    assert isinstance(batch, BatchCheckResult)
    assert len(batch.outcomes) == 2
    assert batch.passed[0].label == "safe_transfer.json"
    assert batch.failed[0].label == "unsafe_transfer.json"
    assert not batch.ok
    assert batch.bound == 6


def test_check_many_records_load_errors(tmp_path):
    missing = tmp_path / "nope.json"
    batch = check_many([missing], bound=2)
    assert batch.errors
    assert batch.errors[0].status == "error"
    assert batch.errors[0].error
    assert not batch.ok


def test_batch_table_has_header_and_summary():
    batch = check_many([SAFE, UNSAFE], bound=6)
    table = batch.format_table()
    assert "SPEC" in table
    assert "STATUS" in table
    assert "safe_transfer.json" in table
    assert "PASS" in table
    assert "FAIL" in table
    assert "2 checked" in table
    assert "1 passed" in table
    assert "1 failed" in table


def test_batch_to_dict_shape():
    batch = check_many([SAFE], bound=6)
    payload = batch.to_dict()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["passed"] == 1
    assert payload["failed"] == 0
    assert payload["results"][0]["path"].endswith("safe_transfer.json")
    assert payload["results"][0]["result"]["spec"] == "SafeTransfer"


def test_spec_outcome_status():
    ok = SpecOutcome(path="a.json", result=check_many([SAFE], bound=6).outcomes[0].result)
    assert ok.status == "pass"
    bad = SpecOutcome(path="b.json", error="boom")
    assert bad.status == "error"
    assert bad.to_dict()["error"] == "boom"


def test_cli_check_multiple_specs_table(capsys):
    code = main(["check", str(SAFE), str(UNSAFE), "--bound", "6"])
    out = capsys.readouterr().out
    assert code == 1
    assert "SPEC" in out
    assert "2 checked" in out


def test_cli_check_directory(capsys, tmp_path):
    (tmp_path / "ok.json").write_text(SAFE.read_text(encoding="utf-8"), encoding="utf-8")
    code = main(["check", str(tmp_path), "--bound", "6"])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 checked" in out
    assert "PASS" in out


def test_cli_check_batch_json(capsys):
    code = main(["check", str(SAFE), str(UNSAFE), "--bound", "6", "--json"])
    out = capsys.readouterr().out
    assert code == 1
    payload = json.loads(out)
    assert payload["count"] == 2
    assert payload["ok"] is False
    assert payload["failed"] == 1


def test_cli_check_format_json_alias(capsys):
    code = main(["check", str(SAFE), "--bound", "6", "--format", "json"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["spec"] == "SafeTransfer"


def test_cli_check_single_file_unchanged(capsys):
    code = main(["check", str(SAFE), "--bound", "6"])
    out = capsys.readouterr().out
    assert code == 0
    assert "BMC result for" in out
    assert "SPEC" not in out.splitlines()[0]


def test_load_spec_file_roundtrip():
    spec = load_spec_file(SAFE)
    assert spec.name == "SafeTransfer"
