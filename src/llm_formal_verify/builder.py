"""Python-embedded builders for composing specifications.

The builder is a thin ergonomic layer over the IR. It is meant for cases
where writing JSON by hand is annoying (parametric specs, generated specs,
tests).

Example
-------
>>> b = SpecBuilder("Counter")
>>> b.var("n", range(5))
>>> b.init(eq(var("n"), lit(0)))
>>> b.action("inc", guard=lt(var("n"), lit(4)), assign={"n": ...})
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .errors import SpecError
from .ir import (
    Action,
    Assignment,
    Check,
    Expr,
    Spec,
    StateVar,
    TRUE,
    and_,
    eq,
    lit,
    var,
)


class SpecBuilder:
    """Fluent builder for :class:`~llm_formal_verify.ir.Spec`."""

    def __init__(self, name: str, description: str = "") -> None:
        self._name = name
        self._description = description
        self._variables: list[StateVar] = []
        self._init_clauses: list[Expr] = []
        self._actions: list[Action] = []
        self._invariants: list[Check] = []
        self._checks: list[Check] = []

    # -- variables ---------------------------------------------------------

    def var(
        self,
        name: str,
        domain: Iterable[Any],
        comment: str = "",
    ) -> "SpecBuilder":
        self._variables.append(StateVar(name=name, domain=tuple(domain), comment=comment))
        return self

    def bool_var(self, name: str, comment: str = "") -> "SpecBuilder":
        return self.var(name, [False, True], comment=comment)

    def int_var(self, name: str, low: int, high: int, comment: str = "") -> "SpecBuilder":
        """Inclusive integer range ``low..high``."""
        if high < low:
            raise SpecError(f"int_var {name!r}: high {high} < low {low}")
        return self.var(name, range(low, high + 1), comment=comment)

    def enum_var(self, name: str, values: Iterable[Any], comment: str = "") -> "SpecBuilder":
        values_t = tuple(values)
        if not values_t:
            raise SpecError(f"enum_var {name!r} needs at least one value")
        return self.var(name, values_t, comment=comment)

    # -- init --------------------------------------------------------------

    def init(self, *clauses: Expr) -> "SpecBuilder":
        self._init_clauses.extend(clauses)
        return self

    def init_eq(self, name: str, value: Any) -> "SpecBuilder":
        """Shorthand: ``name = value`` in the initial state."""
        return self.init(eq(var(name), lit(value)))

    # -- actions -----------------------------------------------------------

    def action(
        self,
        name: str,
        guard: Expr,
        assign: Mapping[str, Any] | None = None,
        comment: str = "",
    ) -> "SpecBuilder":
        """Register a transition.

        ``assign`` maps variable name -> next value. Values may be:
        - a literal (int / bool / str)
        - an :class:`Expr` (e.g. ``var("x")`` to keep the value)
        """
        assignments: list[Assignment] = []
        for target, value in (assign or {}).items():
            if isinstance(value, Expr):
                assignments.append(Assignment(target=target, expr=value))
            else:
                assignments.append(Assignment(target=target, expr=lit(value)))
        self._actions.append(
            Action(name=name, guard=guard, assignments=tuple(assignments), comment=comment)
        )
        return self

    # -- properties --------------------------------------------------------

    def invariant(self, name: str, expr: Expr, comment: str = "") -> "SpecBuilder":
        self._invariants.append(Check(name=name, kind="safety", expr=expr, comment=comment))
        return self

    def safety(self, name: str, expr: Expr, comment: str = "") -> "SpecBuilder":
        self._checks.append(Check(name=name, kind="safety", expr=expr, comment=comment))
        return self

    def liveness(self, name: str, expr: Expr, comment: str = "") -> "SpecBuilder":
        """Bounded reachability: the property becomes true within the bound."""
        self._checks.append(Check(name=name, kind="liveness", expr=expr, comment=comment))
        return self

    # -- finish ------------------------------------------------------------

    def build(self) -> Spec:
        if not self._init_clauses:
            init: Expr = TRUE
        elif len(self._init_clauses) == 1:
            init = self._init_clauses[0]
        else:
            init = and_(*self._init_clauses)
        return Spec(
            name=self._name,
            description=self._description,
            variables=tuple(self._variables),
            init=init,
            actions=tuple(self._actions),
            invariants=tuple(self._invariants),
            checks=tuple(self._checks),
        )


# Re-export common expression helpers so ``from builder import ...`` works.
__all__ = ["SpecBuilder"]
