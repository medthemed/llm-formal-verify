"""Tests for the IR: expressions, validation, evaluation, serialization."""

from __future__ import annotations

import pytest

from llm_formal_verify.ir import (
    Action,
    Assignment,
    Check,
    Expr,
    Lit,
    Spec,
    StateVar,
    VarRef,
    add,
    and_,
    apply_action,
    eq,
    eval_expr,
    ge,
    gt,
    implies,
    lit,
    lt,
    ne,
    not_,
    or_,
    sub,
    var,
)


def test_lit_eval():
    assert eval_expr(lit(True), {}) is True
    assert eval_expr(lit(3), {}) == 3


def test_var_eval():
    assert eval_expr(var("x"), {"x": 5}) == 5
    with pytest.raises(KeyError):
        eval_expr(var("missing"), {})


def test_boolean_ops():
    state = {"a": True, "b": False}
    assert eval_expr(and_(var("a"), var("b")), state) is False
    assert eval_expr(or_(var("a"), var("b")), state) is True
    assert eval_expr(not_(var("b")), state) is True
    assert eval_expr(implies(var("b"), var("a")), state) is True
    assert eval_expr(implies(var("a"), var("b")), state) is False


def test_comparison_ops():
    state = {"n": 3, "m": 5}
    assert eval_expr(eq(var("n"), lit(3)), state) is True
    assert eval_expr(ne(var("n"), lit(3)), state) is False
    assert eval_expr(lt(var("n"), var("m")), state) is True
    assert eval_expr(ge(var("m"), var("n")), state) is True


def test_arithmetic_ops():
    state = {"a": 2, "b": 3}
    assert eval_expr(add(var("a"), var("b")), state) == 5
    assert eval_expr(sub(var("b"), var("a")), state) == 1


def test_free_vars():
    expr = and_(gt(var("x"), lit(0)), lt(var("y"), var("x")))
    assert expr.free_vars() == {"x", "y"}


def test_expr_json_roundtrip():
    expr = and_(eq(var("n"), lit(1)), not_(var("flag")))
    data = expr.to_json()
    assert Expr.from_json(data) == expr


def test_spec_validate_rejects_unknown_var():
    with pytest.raises(ValueError, match="unknown variables"):
        Spec(
            name="Bad",
            variables=(StateVar("a", (0, 1)),),
            init=eq(var("missing"), lit(0)),
            actions=(),
        )


def test_spec_validate_rejects_duplicate_vars():
    with pytest.raises(ValueError, match="Duplicate state variable"):
        Spec(
            name="Bad",
            variables=(StateVar("a", (0, 1)), StateVar("a", (2, 3))),
            init=eq(var("a"), lit(0)),
            actions=(),
        )


def test_spec_domain_product():
    spec = Spec(
        name="Grid",
        variables=(StateVar("x", (0, 1)), StateVar("y", (False, True))),
        init=eq(var("x"), lit(0)),
        actions=(),
    )
    states = spec.domain_product()
    assert len(states) == 4
    assert {"x": 0, "y": False} in states


def test_apply_action_guard():
    action = Action(
        name="Inc",
        guard=lt(var("n"), lit(3)),
        assignments=(Assignment("n", add(var("n"), lit(1))),),
    )
    assert apply_action(action, {"n": 1}) == {"n": 2}
    assert apply_action(action, {"n": 3}) is None


def test_spec_json_roundtrip():
    spec = Spec(
        name="Round",
        description="rt",
        variables=(StateVar("n", (0, 1, 2)), StateVar("flag", (False, True))),
        init=and_(eq(var("n"), lit(0)), eq(var("flag"), lit(False))),
        actions=(
            Action(
                name="Step",
                guard=lt(var("n"), lit(2)),
                assignments=(Assignment("n", add(var("n"), lit(1))),),
            ),
        ),
        invariants=(Check("nonneg", "safety", ge(var("n"), lit(0))),),
        checks=(Check("reach", "liveness", eq(var("n"), lit(2))),),
    )
    data = spec.to_json()
    loaded = Spec.from_json(data)
    assert loaded.name == spec.name
    assert loaded.variables == spec.variables
    assert loaded.init == spec.init
    assert loaded.actions == spec.actions
    assert loaded.invariants == spec.invariants
    assert loaded.checks == spec.checks


def test_check_rejects_bad_kind():
    with pytest.raises(ValueError, match="safety"):
        Check(name="x", kind="maybe", expr=lit(True))


def test_state_var_requires_domain():
    with pytest.raises(ValueError):
        StateVar("empty", ())
