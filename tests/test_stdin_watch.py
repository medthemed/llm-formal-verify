"""Tests for stdin spec loading (``lfv check -``) and watch mode.

Issue #16: stream specs from stdin and add a watch loop.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

import llm_formal_verify as lfv
from llm_formal_verify import SpecError, load_spec_from_stdin, load_spec_text, watch_specs
from llm_formal_verify.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SAFE = EXAMPLES / "safe_transfer.json"
UNSAFE = EXAMPLES / "unsafe_transfer.json"


def _spec_text(path: Path = SAFE) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API: load_spec_text / load_spec_from_stdin
# ---------------------------------------------------------------------------


def test_load_spec_text_matches_file_load():
    from llm_formal_verify.batch import load_spec_file

    via_text = load_spec_text(_spec_text())
    via_file = load_spec_file(SAFE)
    assert via_text.name == via_file.name == "SafeTransfer"
    assert via_text.to_json() == via_file.to_json()


def test_load_spec_from_stdin_stream():
    spec = load_spec_from_stdin(io.StringIO(_spec_text(UNSAFE)))
    assert spec.name == "UnsafeTransfer"


def test_load_spec_text_empty_raises_spec_error():
    for text in ("", "   \n  "):
        with pytest.raises(SpecError):
            load_spec_text(text)


def test_load_spec_from_stdin_empty_raises_spec_error():
    with pytest.raises(SpecError):
        load_spec_from_stdin(io.StringIO(""))


def test_load_spec_text_invalid_json_raises_spec_error():
    with pytest.raises(SpecError):
        load_spec_text("{not json")


def test_load_spec_text_non_object_raises_spec_error():
    with pytest.raises(SpecError):
        load_spec_text("[1, 2, 3]")


# ---------------------------------------------------------------------------
# CLI: lfv check -
# ---------------------------------------------------------------------------


def _feed_stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def test_cli_check_stdin_safe_spec_same_report_as_file(monkeypatch, capsys):
    code_file = main(["check", str(SAFE), "--bound", "6"])
    out_file = capsys.readouterr().out

    _feed_stdin(monkeypatch, _spec_text())
    code_stdin = main(["check", "-", "--bound", "6"])
    out_stdin = capsys.readouterr().out

    assert code_stdin == code_file == 0
    assert out_stdin == out_file
    assert "overall: PASS" in out_stdin


def test_cli_check_stdin_unsafe_spec_fails(monkeypatch, capsys):
    _feed_stdin(monkeypatch, _spec_text(UNSAFE))
    code = main(["check", "-", "--bound", "6"])
    out = capsys.readouterr().out
    assert code == 1
    assert "COUNTEREXAMPLE" in out


def test_cli_check_stdin_json_output(monkeypatch, capsys):
    _feed_stdin(monkeypatch, _spec_text())
    code = main(["check", "-", "--bound", "6", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["spec"] == "SafeTransfer"


def test_cli_check_stdin_empty_is_error(monkeypatch, capsys):
    _feed_stdin(monkeypatch, "")
    code = main(["check", "-"])
    captured = capsys.readouterr()
    assert code == 2
    assert "error" in captured.err.lower()


def test_cli_check_stdin_invalid_json_is_error(monkeypatch, capsys):
    _feed_stdin(monkeypatch, "{oops")
    code = main(["check", "-"])
    captured = capsys.readouterr()
    assert code == 2
    assert "error" in captured.err.lower()


def test_cli_check_stdin_cannot_combine_with_paths(monkeypatch, capsys):
    _feed_stdin(monkeypatch, _spec_text())
    code = main(["check", "-", str(SAFE)])
    captured = capsys.readouterr()
    assert code == 2
    assert "stdin" in captured.err.lower()


# ---------------------------------------------------------------------------
# Public API + CLI: watch_specs / lfv watch
# ---------------------------------------------------------------------------


def test_watch_once_single_pass_passing(tmp_path):
    target = tmp_path / "spec.json"
    target.write_text(_spec_text(), encoding="utf-8")
    seen: list[lfv.BatchCheckResult] = []
    code = watch_specs([target], bound=6, once=True, emit=seen.append)
    assert code == 0
    assert len(seen) == 1
    assert seen[0].ok


def test_watch_once_failing_spec_returns_1(tmp_path):
    target = tmp_path / "spec.json"
    target.write_text(_spec_text(UNSAFE), encoding="utf-8")
    code = watch_specs([target], bound=6, once=True, emit=lambda b: None)
    assert code == 1


def test_watch_once_missing_file_returns_2(tmp_path):
    code = watch_specs(
        [tmp_path / "nope.json"], bound=6, once=True, emit=lambda b: None
    )
    assert code == 2


def test_watch_once_no_specs_is_spec_error():
    with pytest.raises(SpecError):
        watch_specs([], once=True)


def test_watch_rejects_non_positive_interval(tmp_path):
    with pytest.raises(SpecError):
        watch_specs([tmp_path / "x.json"], interval=0, once=True)


def test_watch_reruns_when_file_changes(tmp_path):
    target = tmp_path / "spec.json"
    target.write_text(_spec_text(), encoding="utf-8")
    seen: list[lfv.BatchCheckResult] = []

    sleeps = {"n": 0}

    def fake_sleep(_seconds: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] == 1:
            # Mutate the watched file (different size + mtime), then let
            # the loop observe the change on this poll.
            target.write_text(_spec_text(UNSAFE), encoding="utf-8")
            os.utime(target, None)
        else:
            raise KeyboardInterrupt

    code = watch_specs([target], bound=6, emit=seen.append, sleep=fake_sleep)
    assert len(seen) == 2, "expected an initial run plus one re-run after the change"
    assert seen[0].ok and not seen[1].ok
    assert code == 1, "exit code must track the most recent run"


def test_watch_no_rerun_when_nothing_changes(tmp_path):
    target = tmp_path / "spec.json"
    target.write_text(_spec_text(), encoding="utf-8")
    seen: list[lfv.BatchCheckResult] = []

    def fake_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    code = watch_specs([target], bound=6, emit=seen.append, sleep=fake_sleep)
    assert code == 0
    assert len(seen) == 1


def test_cli_watch_once(tmp_path, capsys):
    target = tmp_path / "spec.json"
    target.write_text(_spec_text(), encoding="utf-8")
    code = main(["watch", str(target), "--bound", "6", "--once"])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 checked, 1 passed" in out


def test_cli_watch_no_specs_found(tmp_path, capsys):
    code = main(["watch", str(tmp_path), "--once"])
    captured = capsys.readouterr()
    assert code == 2
    assert "error" in captured.err.lower()
