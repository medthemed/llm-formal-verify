"""Tests for the CLI and packaged examples."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from llm_formal_verify.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SAFE = EXAMPLES / "safe_transfer.json"
UNSAFE = EXAMPLES / "unsafe_transfer.json"


@pytest.fixture(scope="module", autouse=True)
def _generate_examples():
    """Ensure example JSON files exist before CLI tests."""
    if SAFE.exists() and UNSAFE.exists():
        return
    script = EXAMPLES / "generate_specs.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=ROOT)


def test_cli_check_safe_spec_passes(capsys):
    code = main(["check", str(SAFE), "--bound", "6"])
    out = capsys.readouterr().out
    assert code == 0
    assert "PASS" in out
    assert "overall: PASS" in out


def test_cli_check_unsafe_spec_fails(capsys):
    code = main(["check", str(UNSAFE), "--bound", "6"])
    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL" in captured.out
    assert "COUNTEREXAMPLE" in captured.out


def test_cli_tla_prints_module(capsys):
    code = main(["tla", str(SAFE)])
    out = capsys.readouterr().out
    assert code == 0
    assert "---- MODULE SafeTransfer ----" in out
    assert "Invariants ==" in out
    assert "total_conserved" in out


def test_cli_missing_file(capsys):
    code = main(["check", "no_such_file.json"])
    assert code == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_cli_check_json_safe_spec(capsys):
    code = main(["check", str(SAFE), "--bound", "6", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["spec"] == "SafeTransfer"
    assert payload["bound"] == 6
    assert payload["failures"] == []
    assert isinstance(payload["checks"], list)
    assert all("status" in c for c in payload["checks"])


def test_cli_check_json_unsafe_spec_includes_counterexample(capsys):
    code = main(["check", str(UNSAFE), "--bound", "6", "--json"])
    out = capsys.readouterr().out
    assert code == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["failures"], "expected at least one failing check"
    failed = [c for c in payload["checks"] if c["status"] == "failed"]
    assert failed
    ce = failed[0]["counterexample"]
    assert ce["kind"] == "safety"
    assert ce["steps"], "counterexample must include a path"
    assert ce["steps"][0]["action"] == "Init"
    assert "state" in ce["steps"][0]
    assert "balance_a" in ce["steps"][0]["state"]
    assert ce["length"] == len(ce["steps"])


def test_examples_are_valid_json():
    for path in (SAFE, UNSAFE):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "name" in data
        assert "variables" in data
        assert "init" in data
        assert "actions" in data
