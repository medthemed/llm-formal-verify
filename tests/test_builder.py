"""Tests for the SpecBuilder API."""

from __future__ import annotations

import pytest

from llm_formal_verify import (
    SpecBuilder,
    add,
    eq,
    eval_expr,
    lit,
    sub,
    var,
)


def _counter_spec():
    b = SpecBuilder("Counter", description="counts to 3")
    b.int_var("n", 0, 3)
    b.bool_var("done")
    b.init(eq(var("n"), lit(0)), eq(var("done"), lit(False)))
    b.action(
        "Inc",
        guard=eq(var("done"), lit(False)),
        assign={"n": add(var("n"), lit(1))},
    )
    b.action(
        "MarkDone",
        guard=eq(var("n"), lit(3)),
        assign={"done": True},
    )
    b.invariant("n_in_range", eq(var("done"), var("done")))  # tautology; domain does the work
    b.safety("not_over", eq(var("done"), lit(True)))
    b.liveness("reaches_three", eq(var("n"), lit(3)))
    return b.build()


def test_builder_creates_valid_spec():
    spec = _counter_spec()
    assert spec.name == "Counter"
    assert len(spec.variables) == 2
    assert len(spec.actions) == 2
    assert eval_expr(spec.init, {"n": 0, "done": False}) is True
    assert eval_expr(spec.init, {"n": 1, "done": False}) is False


def test_builder_action_assignment_accepts_expr_and_literal():
    b = SpecBuilder("Mix")
    b.int_var("n", 0, 5)
    b.bool_var("flag")
    b.init(eq(var("n"), lit(0)), eq(var("flag"), lit(False)))
    b.action(
        "Mixed",
        guard=eq(var("flag"), lit(False)),
        assign={"n": add(var("n"), lit(2)), "flag": True},
    )
    spec = b.build()
    action = spec.actions[0]
    targets = {a.target for a in action.assignments}
    assert targets == {"n", "flag"}


def test_int_var_range_invalid():
    b = SpecBuilder("Bad")
    with pytest.raises(ValueError):
        b.int_var("n", 5, 1)


def test_enum_var_requires_values():
    b = SpecBuilder("Bad")
    with pytest.raises(ValueError):
        b.enum_var("e", [])


def test_builder_json_roundtrip():
    import json

    from llm_formal_verify import Spec

    spec = _counter_spec()
    data = spec.to_json()
    # survive a JSON text round-trip too
    text = json.dumps(data)
    loaded = Spec.from_json(json.loads(text))
    assert loaded.name == "Counter"
    assert loaded.actions[0].name == "Inc"


def test_sub_in_assignment():
    b = SpecBuilder("Down")
    b.int_var("n", 0, 5)
    b.init(eq(var("n"), lit(5)))
    b.action("Dec", guard=eq(var("n"), lit(5)), assign={"n": sub(var("n"), lit(1))})
    spec = b.build()
    from llm_formal_verify.ir import apply_action

    assert apply_action(spec.actions[0], {"n": 5}) == {"n": 4}
