"""Generate example specs as JSON.

Run from repo root after ``pip install -e .``:

    python examples/generate_specs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_formal_verify import (  # noqa: E402
    SpecBuilder,
    add,
    and_,
    eq,
    ge,
    gt,
    lit,
    lt,
    not_,
    or_,
    sub,
    var,
)


def build_safe():
    """Two-account transfer: total conserved, balances never negative."""
    b = SpecBuilder(
        "SafeTransfer",
        description=(
            "Two accounts with a 1-unit transfer. "
            "Invariant: balances stay non-negative and total is conserved."
        ),
    )
    b.int_var("balance_a", 0, 4, comment="account A balance")
    b.int_var("balance_b", 0, 4, comment="account B balance")
    b.bool_var("locked", comment="admin lock")

    b.init(
        eq(var("balance_a"), lit(2)),
        eq(var("balance_b"), lit(2)),
        eq(var("locked"), lit(False)),
    )

    b.action(
        "Lock",
        guard=not_(var("locked")),
        assign={"locked": True},
        comment="admin locks transfers",
    )
    b.action(
        "Unlock",
        guard=var("locked"),
        assign={"locked": False},
        comment="admin unlocks transfers",
    )
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
        comment="move 1 unit from A to B",
    )
    b.action(
        "TransferBtoA",
        guard=and_(
            gt(var("balance_b"), lit(0)),
            lt(var("balance_a"), lit(4)),
            not_(var("locked")),
        ),
        assign={
            "balance_b": sub(var("balance_b"), lit(1)),
            "balance_a": add(var("balance_a"), lit(1)),
        },
        comment="move 1 unit from B to A",
    )

    b.invariant("non_negative_a", ge(var("balance_a"), lit(0)))
    b.invariant("non_negative_b", ge(var("balance_b"), lit(0)))
    b.safety(
        "total_conserved",
        eq(add(var("balance_a"), var("balance_b")), lit(4)),
        comment="A + B always equals 4",
    )
    b.liveness("can_lock", var("locked"), comment="system can be locked")
    return b.build()


def build_unsafe():
    """Buggy transfer: A decreases, B is not credited — total drifts."""
    b = SpecBuilder(
        "UnsafeTransfer",
        description=(
            "Buggy transfer: A decreases but B is not credited, "
            "so total money is not conserved. BMC should find a counterexample."
        ),
    )
    b.int_var("balance_a", 0, 4)
    b.int_var("balance_b", 0, 4)
    b.bool_var("locked")

    b.init(
        eq(var("balance_a"), lit(2)),
        eq(var("balance_b"), lit(2)),
        eq(var("locked"), lit(False)),
    )

    b.action(
        "Lock",
        guard=not_(var("locked")),
        assign={"locked": True},
    )
    b.action(
        "Unlock",
        guard=var("locked"),
        assign={"locked": False},
    )
    # BUG: money disappears
    b.action(
        "BuggyTransfer",
        guard=and_(
            gt(var("balance_a"), lit(0)),
            not_(var("locked")),
        ),
        assign={
            "balance_a": sub(var("balance_a"), lit(1)),
            # balance_b intentionally left unchanged
        },
        comment="A decreases, B unchanged — money disappears",
    )

    b.invariant("non_negative_a", ge(var("balance_a"), lit(0)))
    b.safety(
        "total_conserved",
        eq(add(var("balance_a"), var("balance_b")), lit(4)),
        comment="SHOULD FAIL: total drifts below 4",
    )
    return b.build()


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    safe_path = out_dir / "safe_transfer.json"
    unsafe_path = out_dir / "unsafe_transfer.json"
    safe_path.write_text(json.dumps(build_safe().to_json(), indent=2) + "\n", encoding="utf-8")
    unsafe_path.write_text(
        json.dumps(build_unsafe().to_json(), indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {safe_path}")
    print(f"wrote {unsafe_path}")


if __name__ == "__main__":
    main()
