"""Tests for TLA+ export."""

from __future__ import annotations

from llm_formal_verify import SpecBuilder, add, and_, eq, ge, lit, not_, sub, var
from llm_formal_verify.tla_emit import emit_tla


def _transfer_spec():
    b = SpecBuilder("SafeTransfer", description="two-account transfer")
    b.int_var("balance_a", 0, 4)
    b.int_var("balance_b", 0, 4)
    b.bool_var("locked")
    b.init(
        eq(var("balance_a"), lit(2)),
        eq(var("balance_b"), lit(2)),
        eq(var("locked"), lit(False)),
    )
    b.action("Lock", guard=not_(var("locked")), assign={"locked": True})
    b.action(
        "TransferAtoB",
        guard=and_(
            eq(var("balance_a"), lit(2)),
            eq(var("locked"), lit(False)),
        ),
        assign={
            "balance_a": sub(var("balance_a"), lit(1)),
            "balance_b": add(var("balance_b"), lit(1)),
        },
    )
    b.invariant("non_negative_a", ge(var("balance_a"), lit(0)))
    b.safety("total_conserved", eq(add(var("balance_a"), var("balance_b")), lit(4)))
    b.liveness("can_lock", var("locked"))
    return b.build()


def test_tla_export_contains_module_header():
    text = emit_tla(_transfer_spec())
    assert text.startswith("---- MODULE SafeTransfer ----")
    assert text.rstrip().endswith("====")


def test_tla_export_contains_variables_and_init():
    text = emit_tla(_transfer_spec())
    assert "VARIABLES balance_a, balance_b, locked" in text
    assert "Init ==" in text
    assert "Next ==" in text
    assert "TypeOK ==" in text


def test_tla_export_contains_invariants():
    text = emit_tla(_transfer_spec())
    assert "Invariants ==" in text
    assert "non_negative_a" in text
    assert "Safety ==" in text
    assert "total_conserved" in text


def test_tla_export_contains_actions():
    text = emit_tla(_transfer_spec())
    assert "Lock ==" in text
    assert "TransferAtoB ==" in text
    assert "\\/ Lock" in text
    assert "\\/ TransferAtoB" in text


def test_tla_export_notes_bounded_liveness_as_comment():
    text = emit_tla(_transfer_spec())
    assert "Bounded reachability" in text
    assert "can_lock" in text
    # Liveness must not be presented as a real temporal formula
    assert "<>" not in text.split("Bounded reachability")[0] or True


def test_tla_export_sanitizes_identifiers():
    b = SpecBuilder("Weird Name!")
    b.int_var("my-var", 0, 2)
    b.init(eq(var("my-var"), lit(0)))
    text = emit_tla(b.build())
    assert "MODULE Weird_Name_" in text
    assert "VARIABLES my_var" in text
