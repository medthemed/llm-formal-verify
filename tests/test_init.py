"""Tests for lfv init scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_formal_verify import Spec, bounded_model_check, write_starter
from llm_formal_verify.cli import main
from llm_formal_verify.init import STARTER_SPEC


def test_write_starter_creates_spec_and_config(tmp_path: Path):
    written = write_starter(tmp_path)
    names = {p.name for p in written}
    assert names == {"spec.json", ".lfv.json"}
    for path in written:
        assert path.is_file()
        json.loads(path.read_text(encoding="utf-8"))


def test_starter_spec_is_valid_and_passes(tmp_path: Path):
    write_starter(tmp_path)
    spec = Spec.from_json(json.loads((tmp_path / "spec.json").read_text(encoding="utf-8")))
    result = bounded_model_check(spec, bound=8)
    assert result.ok, result.format()
    assert result.spec_name == "Starter"


def test_write_starter_refuses_overwrite(tmp_path: Path):
    write_starter(tmp_path)
    with pytest.raises(FileExistsError):
        write_starter(tmp_path)


def test_write_starter_force_overwrites(tmp_path: Path):
    write_starter(tmp_path)
    written = write_starter(tmp_path, force=True)
    assert len(written) == 2


def test_write_starter_spec_only(tmp_path: Path):
    written = write_starter(tmp_path, config_name=None)
    assert [p.name for p in written] == ["spec.json"]
    assert not (tmp_path / ".lfv.json").exists()


def test_cli_init(tmp_path: Path, capsys):
    code = main(["init", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "wrote" in out
    assert (tmp_path / "spec.json").exists()
    assert (tmp_path / ".lfv.json").exists()


def test_cli_init_refuses_existing(tmp_path: Path, capsys):
    main(["init", str(tmp_path)])
    code = main(["init", str(tmp_path)])
    err = capsys.readouterr().err
    assert code == 1
    assert "already exists" in err


def test_cli_init_force(tmp_path: Path):
    main(["init", str(tmp_path)])
    code = main(["init", str(tmp_path), "--force"])
    assert code == 0


def test_cli_init_then_check(tmp_path: Path, capsys):
    """The happy path a new user hits: init, then check."""
    assert main(["init", str(tmp_path)]) == 0
    capsys.readouterr()
    code = main(["check", str(tmp_path / "spec.json")])
    out = capsys.readouterr().out
    assert code == 0
    assert "PASS" in out


def test_cli_check_uses_project_config(tmp_path: Path, capsys, monkeypatch):
    """A .lfv.json next to the cwd supplies the default bound."""
    write_starter(tmp_path)
    # Config says bound=3; the starter still passes at that bound.
    (tmp_path / ".lfv.json").write_text(
        json.dumps({"bound": 3, "search": "dfs"}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    code = main(["check", "spec.json"])
    out = capsys.readouterr().out
    assert code == 0
    assert "bound=3" in out
    assert "search=dfs" in out


def test_cli_check_flag_overrides_config(tmp_path: Path, capsys, monkeypatch):
    write_starter(tmp_path)
    (tmp_path / ".lfv.json").write_text(json.dumps({"bound": 3}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    code = main(["check", "spec.json", "--bound", "5", "--search", "bfs"])
    out = capsys.readouterr().out
    assert code == 0
    assert "bound=5" in out
    assert "search=bfs" in out


def test_search_strategy_both_find_same_violations():
    """BFS and DFS must agree on pass/fail; only the trace may differ."""
    from llm_formal_verify import SpecBuilder, eq, lit, var, not_, and_, add, sub, gt, lt

    b = SpecBuilder("Race")
    b.int_var("x", 0, 3)
    b.init(eq(var("x"), lit(0)))
    b.action("inc", guard=lt(var("x"), lit(3)), assign={"x": add(var("x"), lit(1))})
    b.action("bad", guard=eq(var("x"), lit(3)), assign={"x": lit(0)})
    # Safety that fails once x hits 3 then drops: just use x <= 3 always true,
    # and a liveness that never becomes true.
    b.safety("always_small", lt(var("x"), lit(10)))
    b.liveness("never", eq(var("x"), lit(99)))
    spec = b.build()

    bfs = bounded_model_check(spec, bound=5, search="bfs")
    dfs = bounded_model_check(spec, bound=5, search="dfs")
    assert bfs.ok == dfs.ok
    assert bfs.reachable_states == dfs.reachable_states
    assert bfs.search == "bfs"
    assert dfs.search == "dfs"


def test_invalid_search_raises():
    from llm_formal_verify import ModelError, SpecBuilder, eq, lit, var

    b = SpecBuilder("Tiny")
    b.var("x", [0, 1])
    b.init(eq(var("x"), lit(0)))
    spec = b.build()
    with pytest.raises(ModelError, match="search must be one of"):
        bounded_model_check(spec, bound=1, search="random")


def test_starter_spec_structure():
    """Sanity-check the embedded starter so we notice accidental edits."""
    assert STARTER_SPEC["name"] == "Starter"
    assert len(STARTER_SPEC["variables"]) == 2
    assert len(STARTER_SPEC["actions"]) == 2
    assert STARTER_SPEC["checks"][0]["kind"] == "liveness"
