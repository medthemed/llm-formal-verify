"""llm-formal-verify: bounded formal checks for business-logic specs.

This package is intentionally small. It lets you write a machine-checkable
specification of business logic (state, transitions, invariants), export it
as TLA+-like text for human review, and run a bounded model checker that
exhaustively explores small finite state spaces and reports counterexamples.

It is NOT a full proof assistant. Unbounded liveness is out of scope.

Public API
----------
Everything re-exported here (see ``__all__``) is covered by the 0.x
compatibility promise: names may be added, but existing names and their
call signatures stay stable within the 0.x series. Prefer this package
namespace over importing from private modules.
"""

from .errors import SpecError, ModelError
from .ir import (
    Action,
    Check,
    Expr,
    Spec,
    StateVar,
    TRUE,
    FALSE,
    lit,
    var,
    and_,
    or_,
    not_,
    eq,
    ne,
    lt,
    le,
    gt,
    ge,
    implies,
    add,
    sub,
)
from .builder import SpecBuilder
from .bmc import BMCResult, CheckResult, Counterexample, Step, bounded_model_check
from .tla_emit import emit_tla
from .ir import apply_action, eval_expr

__all__ = [
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
]

__version__ = "0.2.0"
