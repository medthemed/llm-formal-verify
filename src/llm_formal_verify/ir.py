"""Intermediate representation for business-logic specifications.

The IR is deliberately tiny so that it stays easy to serialize (JSON) and
easy to reason about:

- StateVar  -- a named finite-domain variable.
- Expr      -- a small boolean / comparison expression tree.
- Action    -- a named transition (guard + next-state assignments).
- Check     -- an assertion (safety or bounded liveness) to verify.
- Spec      -- the whole thing: name, variables, Init, Next, invariants, checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Expr:
    """Base class for all expressions in the IR.

    Expressions are immutable and hashable so they can be used as dict keys
    during model checking (visited-state tracking).
    """

    def free_vars(self) -> set[str]:
        """Return the set of state-variable names this expression reads."""
        return _free_vars(self)

    def to_json(self) -> dict[str, Any]:
        return _expr_to_json(self)

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> "Expr":
        return _expr_from_json(data)

    def __and__(self, other: "Expr") -> "Expr":
        return and_(self, other)

    def __or__(self, other: "Expr") -> "Expr":
        return or_(self, other)

    def __invert__(self) -> "Expr":
        return not_(self)


@dataclass(frozen=True)
class Lit(Expr):
    """A constant: bool or int."""

    value: Any

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Lit({self.value!r})"


@dataclass(frozen=True)
class VarRef(Expr):
    """Reference to a state variable by name."""

    name: str

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"VarRef({self.name!r})"


@dataclass(frozen=True)
class Unary(Expr):
    op: str  # "not"
    operand: Expr

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Unary({self.op!r}, {self.operand!r})"


@dataclass(frozen=True)
class BinOp(Expr):
    op: str  # and | or | eq | ne | lt | le | gt | ge | implies
    left: Expr
    right: Expr

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"BinOp({self.op!r}, {self.left!r}, {self.right!r})"


# Convenience constructors -------------------------------------------------

TRUE = Lit(True)
FALSE = Lit(False)


def lit(value: Any) -> Lit:
    return Lit(value)


def var(name: str) -> VarRef:
    return VarRef(name)


def and_(*operands: Expr) -> Expr:
    if not operands:
        return TRUE
    result = operands[0]
    for op in operands[1:]:
        result = BinOp("and", result, op)
    return result


def or_(*operands: Expr) -> Expr:
    if not operands:
        return FALSE
    result = operands[0]
    for op in operands[1:]:
        result = BinOp("or", result, op)
    return result


def not_(operand: Expr) -> Expr:
    return Unary("not", operand)


def eq(left: Expr, right: Expr) -> Expr:
    return BinOp("eq", left, right)


def ne(left: Expr, right: Expr) -> Expr:
    return BinOp("ne", left, right)


def lt(left: Expr, right: Expr) -> Expr:
    return BinOp("lt", left, right)


def le(left: Expr, right: Expr) -> Expr:
    return BinOp("le", left, right)


def gt(left: Expr, right: Expr) -> Expr:
    return BinOp("gt", left, right)


def ge(left: Expr, right: Expr) -> Expr:
    return BinOp("ge", left, right)


def implies(left: Expr, right: Expr) -> Expr:
    """Logical implication: left => right."""
    return BinOp("implies", left, right)


def add(left: Expr, right: Expr) -> Expr:
    """Integer addition (values must stay inside declared domains)."""
    return BinOp("add", left, right)


def sub(left: Expr, right: Expr) -> Expr:
    """Integer subtraction (values must stay inside declared domains)."""
    return BinOp("sub", left, right)


def _free_vars(expr: Expr) -> set[str]:
    if isinstance(expr, VarRef):
        return {expr.name}
    if isinstance(expr, Unary):
        return _free_vars(expr.operand)
    if isinstance(expr, BinOp):
        return _free_vars(expr.left) | _free_vars(expr.right)
    return set()


def _expr_to_json(expr: Expr) -> dict[str, Any]:
    if isinstance(expr, Lit):
        return {"kind": "lit", "value": expr.value}
    if isinstance(expr, VarRef):
        return {"kind": "var", "name": expr.name}
    if isinstance(expr, Unary):
        return {"kind": "unary", "op": expr.op, "operand": _expr_to_json(expr.operand)}
    if isinstance(expr, BinOp):
        return {
            "kind": "binop",
            "op": expr.op,
            "left": _expr_to_json(expr.left),
            "right": _expr_to_json(expr.right),
        }
    raise TypeError(f"Cannot serialize expression: {expr!r}")


def _expr_from_json(data: Mapping[str, Any]) -> Expr:
    kind = data["kind"]
    if kind == "lit":
        return Lit(data["value"])
    if kind == "var":
        return VarRef(data["name"])
    if kind == "unary":
        return Unary(data["op"], _expr_from_json(data["operand"]))
    if kind == "binop":
        return BinOp(data["op"], _expr_from_json(data["left"]), _expr_from_json(data["right"]))
    raise ValueError(f"Unknown expression kind: {kind!r}")


# ---------------------------------------------------------------------------
# Variables, Actions, Checks, Spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateVar:
    """A finite-domain state variable.

    ``domain`` is the list of legal values. Domains must be non-empty and
    every value must be hashable (ints, bools, or strings in practice).
    """

    name: str
    domain: tuple[Any, ...]
    comment: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("StateVar.name must be non-empty")
        if not self.domain:
            raise ValueError(f"StateVar {self.name!r} needs a non-empty domain")
        object.__setattr__(self, "domain", tuple(self.domain))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "domain": list(self.domain)}
        if self.comment:
            payload["comment"] = self.comment
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> "StateVar":
        return StateVar(
            name=data["name"],
            domain=tuple(data["domain"]),
            comment=data.get("comment", ""),
        )


@dataclass(frozen=True)
class Assignment:
    """Next-state assignment: ``target := expr``."""

    target: str
    expr: Expr

    def to_json(self) -> dict[str, Any]:
        return {"target": self.target, "expr": self.expr.to_json()}

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> "Assignment":
        return Assignment(target=data["target"], expr=Expr.from_json(data["expr"]))


@dataclass(frozen=True)
class Action:
    """A named transition: when ``guard`` holds, apply ``assignments``.

    Variables not listed in ``assignments`` keep their current value
    (stuttering / frame condition).
    """

    name: str
    guard: Expr
    assignments: tuple[Assignment, ...] = ()
    comment: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Action.name must be non-empty")
        object.__setattr__(self, "assignments", tuple(self.assignments))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "guard": self.guard.to_json(),
            "assignments": [a.to_json() for a in self.assignments],
        }
        if self.comment:
            payload["comment"] = self.comment
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> "Action":
        return Action(
            name=data["name"],
            guard=Expr.from_json(data["guard"]),
            assignments=tuple(Assignment.from_json(a) for a in data.get("assignments", [])),
            comment=data.get("comment", ""),
        )


@dataclass(frozen=True)
class Check:
    """A property to verify under the bound.

    kind:
      - "safety": must hold in every reachable state.
      - "liveness": (bounded) there exists a reachable state where it holds
        within the exploration bound. This is *not* full temporal liveness;
        it is a bounded reachability check.
    """

    name: str
    kind: str  # "safety" | "liveness"
    expr: Expr
    comment: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("safety", "liveness"):
            raise ValueError(f"Check.kind must be 'safety' or 'liveness', got {self.kind!r}")
        if not self.name:
            raise ValueError("Check.name must be non-empty")

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "expr": self.expr.to_json(),
        }
        if self.comment:
            payload["comment"] = self.comment
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> "Check":
        return Check(
            name=data["name"],
            kind=data["kind"],
            expr=Expr.from_json(data["expr"]),
            comment=data.get("comment", ""),
        )


@dataclass(frozen=True)
class Spec:
    """A complete finite-state specification.

    Fields
    ------
    name:        Human-readable title.
    variables:   Finite-domain state variables.
    init:        Conjunctive initial-state condition.
    actions:     Named transitions (their disjunction forms Next).
    invariants:  Conditions that must hold in every reachable state.
    checks:      Extra named safety / bounded-liveness properties.
    """

    name: str
    variables: tuple[StateVar, ...]
    init: Expr
    actions: tuple[Action, ...]
    invariants: tuple[Check, ...] = ()
    checks: tuple[Check, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Spec.name must be non-empty")
        if not self.variables:
            raise ValueError("Spec needs at least one state variable")
        object.__setattr__(self, "variables", tuple(self.variables))
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "invariants", tuple(self.invariants))
        object.__setattr__(self, "checks", tuple(self.checks))
        self.validate()

    # -- accessors ---------------------------------------------------------

    def var_map(self) -> dict[str, StateVar]:
        return {v.name: v for v in self.variables}

    def domain_product(self) -> list[dict[str, Any]]:
        """Enumerate the full finite state space (Cartesian product)."""
        names = [v.name for v in self.variables]
        domains = [list(v.domain) for v in self.variables]
        states: list[dict[str, Any]] = [{}]
        for name, domain in zip(names, domains):
            next_states: list[dict[str, Any]] = []
            for prefix in states:
                for value in domain:
                    state = dict(prefix)
                    state[name] = value
                    next_states.append(state)
            states = next_states
        return states

    def validate(self) -> None:
        """Raise ValueError if the IR is internally inconsistent."""
        names = [v.name for v in self.variables]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate state variable names: {names}")
        known = set(names)
        action_names = [a.name for a in self.actions]
        if len(action_names) != len(set(action_names)):
            raise ValueError(f"Duplicate action names: {action_names}")

        def check_expr(expr: Expr, context: str) -> None:
            unknown = expr.free_vars() - known
            if unknown:
                raise ValueError(
                    f"{context} references unknown variables: {sorted(unknown)}"
                )

        check_expr(self.init, "Init")
        for inv in self.invariants:
            check_expr(inv.expr, f"Invariant {inv.name!r}")
        for chk in self.checks:
            check_expr(chk.expr, f"Check {chk.name!r}")
        for action in self.actions:
            check_expr(action.guard, f"Action {action.name!r} guard")
            for assignment in action.assignments:
                if assignment.target not in known:
                    raise ValueError(
                        f"Action {action.name!r} assigns unknown variable "
                        f"{assignment.target!r}"
                    )
                check_expr(assignment.expr, f"Action {action.name!r} assignment")

    # -- serialization -----------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "variables": [v.to_json() for v in self.variables],
            "init": self.init.to_json(),
            "actions": [a.to_json() for a in self.actions],
            "invariants": [i.to_json() for i in self.invariants],
            "checks": [c.to_json() for c in self.checks],
        }

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> "Spec":
        return Spec(
            name=data["name"],
            description=data.get("description", ""),
            variables=tuple(StateVar.from_json(v) for v in data["variables"]),
            init=Expr.from_json(data["init"]),
            actions=tuple(Action.from_json(a) for a in data.get("actions", [])),
            invariants=tuple(Check.from_json(i) for i in data.get("invariants", [])),
            checks=tuple(Check.from_json(c) for c in data.get("checks", [])),
        )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def eval_expr(expr: Expr, state: Mapping[str, Any]) -> Any:
    """Evaluate ``expr`` against a concrete assignment of state variables."""
    if isinstance(expr, Lit):
        return expr.value
    if isinstance(expr, VarRef):
        if expr.name not in state:
            raise KeyError(f"Variable {expr.name!r} not bound in state")
        return state[expr.name]
    if isinstance(expr, Unary):
        if expr.op == "not":
            return not bool(eval_expr(expr.operand, state))
        raise ValueError(f"Unknown unary op: {expr.op!r}")
    if isinstance(expr, BinOp):
        left = eval_expr(expr.left, state)
        right = eval_expr(expr.right, state)
        op = expr.op
        if op == "and":
            return bool(left) and bool(right)
        if op == "or":
            return bool(left) or bool(right)
        if op == "eq":
            return left == right
        if op == "ne":
            return left != right
        if op == "lt":
            return left < right
        if op == "le":
            return left <= right
        if op == "gt":
            return left > right
        if op == "ge":
            return left >= right
        if op == "implies":
            return (not bool(left)) or bool(right)
        if op == "add":
            return left + right
        if op == "sub":
            return left - right
        raise ValueError(f"Unknown binary op: {op!r}")
    raise TypeError(f"Not an expression: {expr!r}")


def apply_action(action: Action, state: Mapping[str, Any]) -> dict[str, Any] | None:
    """If the guard holds, return the successor state; otherwise None."""
    if not eval_expr(action.guard, state):
        return None
    successor = dict(state)
    for assignment in action.assignments:
        successor[assignment.target] = eval_expr(assignment.expr, state)
    return successor
