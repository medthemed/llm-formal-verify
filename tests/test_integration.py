"""End-to-end integration tests against the packaged example specs.

These load ``examples/safe_transfer.json`` and
``examples/unsafe_transfer.json`` through the *public* API only
(``Spec.from_json`` + ``bounded_model_check``) so they exercise the same
path a library consumer would use.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from llm_formal_verify import Spec, bounded_model_check

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SAFE = EXAMPLES / "safe_transfer.json"
UNSAFE = EXAMPLES / "unsafe_transfer.json"


@pytest.fixture(scope="module", autouse=True)
def _generate_examples():
    if SAFE.exists() and UNSAFE.exists():
        return
    script = EXAMPLES / "generate_specs.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=ROOT)


def _load(path: Path) -> Spec:
    return Spec.from_json(json.loads(path.read_text(encoding="utf-8")))


def test_safe_example_passes_bmc():
    spec = _load(SAFE)
    result = bounded_model_check(spec, bound=6)
    assert result.ok, result.format()
    assert result.spec_name == "SafeTransfer"
    assert result.reachable_states > 0
    assert result.failures == []
    # Every check reports a status the CLI / CI layer understands.
    for check in result.results:
        assert check.status in ("ok", "unreachable")
        assert check.states_examined > 0


def test_unsafe_example_fails_with_counterexample():
    spec = _load(UNSAFE)
    result = bounded_model_check(spec, bound=6)
    assert not result.ok
    assert result.failures, "expected at least one failing check"
    failed = result.failures[0]
    assert failed.status == "failed"
    assert failed.counterexample is not None
    ce = failed.counterexample
    assert ce.kind == "safety"
    assert ce.steps, "counterexample must include a path"
    assert ce.steps[0].action == "Init"
    assert "balance_a" in ce.steps[0].state
    assert ce.trace_length() == len(ce.steps)


def test_safe_example_json_roundtrip_preserves_structure():
    """from_json(to_json(x)) must be equivalent for the public Spec model."""
    original = _load(SAFE)
    rebuilt = Spec.from_json(original.to_json())
    assert rebuilt.name == original.name
    assert len(rebuilt.variables) == len(original.variables)
    assert len(rebuilt.actions) == len(original.actions)
    assert len(rebuilt.invariants) == len(original.invariants)
    assert len(rebuilt.checks) == len(original.checks)
    # A round-tripped spec must still pass.
    assert bounded_model_check(rebuilt, bound=6).ok


def test_tla_emit_on_examples():
    from llm_formal_verify import emit_tla

    for path, module_name in ((SAFE, "SafeTransfer"), (UNSAFE, "UnsafeTransfer")):
        text = emit_tla(_load(path))
        assert f"---- MODULE {module_name} ----" in text
        assert "VARIABLES" in text
        assert "Init" in text
