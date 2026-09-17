"""Tests for the bounded model checker."""

from __future__ import annotations

from llm_formal_verify import (
    SpecBuilder,
    add,
    and_,
    bounded_model_check,
    eq,
    ge,
    gt,
    lit,
    lt,
    not_,
    sub,
    var,
)


def _safe_transfer():
    b = SpecBuilder("SafeTransfer")
    b.int_var("balance_a", 0, 4)
    b.int_var("balance_b", 0, 4)
    b.bool_var("locked")
    b.init(
        eq(var("balance_a"), lit(2)),
        eq(var("balance_b"), lit(2)),
        eq(var("locked"), lit(False)),
    )
    b.action("Lock", guard=not_(var("locked")), assign={"locked": True})
    b.action("Unlock", guard=var("locked"), assign={"locked": False})
    b.action(
        "TransferAtoB",
        guard=and_(
            gt(var("balance_a"), lit(0)),
            lt(var("balance_b"), lit(4)),
            not_(var("locked")),
        ),
        assign={
            "balance_a": sub(var("balance_a"), lit(1)),
            "balance_b": add(var("balance_b"), lit(1)),
        },
    )
    b.invariant("non_negative_a", ge(var("balance_a"), lit(0)))
    b.invariant("non_negative_b", ge(var("balance_b"), lit(0)))
    b.safety("total_conserved", eq(add(var("balance_a"), var("balance_b")), lit(4)))
    b.liveness("can_lock", var("locked"))
    return b.build()


def _unsafe_transfer():
    b = SpecBuilder("UnsafeTransfer")
    b.int_var("balance_a", 0, 4)
    b.int_var("balance_b", 0, 4)
    b.bool_var("locked")
    b.init(
        eq(var("balance_a"), lit(2)),
        eq(var("balance_b"), lit(2)),
        eq(var("locked"), lit(False)),
    )
    b.action("Lock", guard=not_(var("locked")), assign={"locked": True})
    b.action("Unlock", guard=var("locked"), assign={"locked": False})
    b.action(
        "BuggyTransfer",
        guard=and_(gt(var("balance_a"), lit(0)), not_(var("locked"))),
        assign={"balance_a": sub(var("balance_a"), lit(1))},
    )
    b.safety("total_conserved", eq(add(var("balance_a"), var("balance_b")), lit(4)))
    return b.build()


def test_safe_spec_passes_within_bound():
    result = bounded_model_check(_safe_transfer(), bound=6)
    assert result.ok, result.format()
    names = {r.name: r for r in result.results}
    assert names["total_conserved"].status == "ok"
    assert names["non_negative_a"].status == "ok"
    assert names["can_lock"].status == "ok"
    assert names["can_lock"].witness is not None


def test_unsafe_spec_finds_counterexample():
    result = bounded_model_check(_unsafe_transfer(), bound=6)
    assert not result.ok
    failures = result.failures
    assert failures, "expected at least one failure"
    fail = failures[0]
    assert fail.name == "total_conserved"
    assert fail.counterexample is not None
    # The bug destroys money: final total is < 4
    final_state = fail.counterexample.steps[-1].state
    total = final_state["balance_a"] + final_state["balance_b"]
    assert total < 4
    # Trace should be non-empty and start from an initial-like state
    assert fail.counterexample.trace_length() >= 1
    first = fail.counterexample.steps[0].state
    assert first["balance_a"] == 2 and first["balance_b"] == 2


def test_counterexample_format_is_readable():
    result = bounded_model_check(_unsafe_transfer(), bound=4)
    text = result.failures[0].counterexample.format()
    assert "COUNTEREXAMPLE" in text
    assert "total_conserved" in text
    assert "trace:" in text


def test_bound_zero_only_checks_initial_states():
    # At bound 0 the buggy transfer has not fired yet, so the invariant holds.
    result = bounded_model_check(_unsafe_transfer(), bound=0)
    assert result.ok, result.format()


def test_out_of_domain_next_value_raises():
    from llm_formal_verify.ir import Spec, StateVar

    # Action that would set n = 5 outside domain {0,1}
    from llm_formal_verify.ir import Action, Assignment, Check

    spec = Spec(
        name="Overflow",
        variables=(StateVar("n", (0, 1)),),
        init=eq(var("n"), lit(0)),
        actions=(
            Action(
                name="Jump",
                guard=eq(var("n"), lit(0)),
                assignments=(Assignment("n", lit(5)),),
            ),
        ),
    )
    import pytest

    with pytest.raises(ValueError, match="out-of-domain"):
        bounded_model_check(spec, bound=2)


def test_liveness_unreachable_reports_status():
    b = SpecBuilder("Stuck")
    b.int_var("n", 0, 2)
    b.init(eq(var("n"), lit(0)))
    # no actions: can never leave 0
    b.liveness("reaches_two", eq(var("n"), lit(2)))
    result = bounded_model_check(b.build(), bound=5)
    live = next(r for r in result.results if r.name == "reaches_two")
    assert live.status == "unreachable"
    assert result.ok  # unreachable is not a hard failure for overall ok
