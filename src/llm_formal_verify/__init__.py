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
from .batch import (
    BatchCheckResult,
    SpecOutcome,
    check_many,
    expand_spec_paths,
)
from .bmc import BMCResult, CheckResult, Counterexample, Step, bounded_model_check
from .config import ProjectConfig, discover_config, load_config, resolve_check_options
from .init import write_starter
from .schemas import (
    BATCH_REPORT,
    BMC_REPORT,
    KNOWN_SCHEMAS,
    SPEC,
    TLA_MODULE,
    load_schema,
    schema_path,
)
from .tla_emit import emit_tla
from .ir import apply_action, eval_expr

__all__ = [
    "Action",
    "BMCResult",
    "BatchCheckResult",
    "Check",
    "CheckResult",
    "Counterexample",
    "Expr",
    "ModelError",
    "ProjectConfig",
    "Spec",
    "SpecBuilder",
    "SpecError",
    "SpecOutcome",
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
    "BATCH_REPORT",
    "BMC_REPORT",
    "KNOWN_SCHEMAS",
    "SPEC",
    "TLA_MODULE",
    "bounded_model_check",
    "check_many",
    "discover_config",
    "emit_tla",
    "expand_spec_paths",
    "load_config",
    "load_schema",
    "resolve_check_options",
    "schema_path",
    "write_starter",
    "apply_action",
    "eval_expr",
]

__version__ = "0.4.0"
