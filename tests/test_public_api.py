"""Freeze the public API surface for the 0.x compatibility promise.

Every name in ``llm_formal_verify.__all__`` must be importable, and the
signatures of the builder / BMC entry points must not change without a
minor version bump. If this test fails, either restore the signature or
deliberately bump the minor version and update this file.
"""

from __future__ import annotations

import inspect

import llm_formal_verify as lfv


EXPECTED_ALL = {
    "Action",
    "BMCResult",
    "Check",
    "CheckResult",
    "Counterexample",
    "Expr",
    "ModelError",
    "Spec",
    "SpecBuilder",
    "SpecError",
    "StateVar",
    "Step",
    "TRUE",
    "FALSE",
    "lit",
    "var",
    "and_",
    "or_",
    "not_",
    "eq",
    "ne",
    "lt",
    "le",
    "gt",
    "ge",
    "implies",
    "add",
    "sub",
    "bounded_model_check",
    "emit_tla",
    "apply_action",
    "eval_expr",
}


def test_all_matches_expected_surface():
    assert set(lfv.__all__) == EXPECTED_ALL


def test_all_names_are_importable():
    for name in lfv.__all__:
        assert hasattr(lfv, name), f"__all__ lists {name!r} but it is not importable"
        assert getattr(lfv, name) is not None


def test_no_stray_dunder_or_private_in_all():
    for name in lfv.__all__:
        assert not name.startswith("_"), f"{name!r} should not be in the public API"


def test_bounded_model_check_signature_frozen():
    sig = inspect.signature(lfv.bounded_model_check)
    params = list(sig.parameters)
    assert params == ["spec", "bound"], f"BMC signature changed: {params}"
    assert sig.parameters["bound"].default == 8


def test_spec_builder_fluent_methods_frozen():
    """The fluent builder methods callers rely on must remain present."""
    required = {
        "var",
        "bool_var",
        "int_var",
        "enum_var",
        "init",
        "init_eq",
        "action",
        "invariant",
        "safety",
        "liveness",
        "build",
    }
    for method in required:
        assert hasattr(lfv.SpecBuilder, method), f"SpecBuilder.{method} is missing"


def test_bmc_result_shape_frozen():
    """BMCResult attributes consumed by CI tooling must stay put."""
    required = {"spec_name", "bound", "reachable_states", "transitions_explored", "results"}
    for attr in required:
        assert attr in lfv.BMCResult.__dataclass_fields__, attr

    for attr in ("ok", "failures", "format", "to_dict", "to_json"):
        assert hasattr(lfv.BMCResult, attr), attr


def test_version_string_is_semver():
    parts = lfv.__version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
