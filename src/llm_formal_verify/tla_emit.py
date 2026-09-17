"""TLA+-like text emitter.

Produces a readable TLA+-style module for human review and for pasting into
tooling that understands a TLA+ subset. This is an *export format*, not a
full TLA+ toolchain integration: it does not run TLC and does not implement
the full TLA+ language.

What maps cleanly:
- State variables and their finite domains  -> VARIABLES + TypeOK
- Init                                     -> Init
- Actions                                  -> Next disjuncts
- Invariants / safety checks               -> Invariant / Safety

Liveness checks are emitted as comments because full temporal logic is out
of scope for this MVP.
"""

from __future__ import annotations

from typing import Any, Mapping

from .ir import (
    Action,
    Assignment,
    Check,
    Expr,
    Spec,
    StateVar,
)


def _sanitize_ident(name: str) -> str:
    """Make a name safe as a TLA+ identifier."""
    out = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    ident = "".join(out)
    if not ident or ident[0].isdigit():
        ident = "x_" + ident
    return ident


def _tla_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace('"', '\\"') + '"'
    raise TypeError(f"Cannot emit TLA+ literal for {value!r}")


def _tla_domain(domain: tuple[Any, ...]) -> str:
    if len(domain) == 1:
        return "{" + _tla_literal(domain[0]) + "}"
    return "{" + ", ".join(_tla_literal(v) for v in domain) + "}"


def _tla_expr(expr: Expr) -> str:
    from .ir import BinOp, Lit, Unary, VarRef

    if isinstance(expr, Lit):
        return _tla_literal(expr.value)
    if isinstance(expr, VarRef):
        return _sanitize_ident(expr.name)
    if isinstance(expr, Unary):
        if expr.op == "not":
            return f"~({_tla_expr(expr.operand)})"
        raise ValueError(f"Unknown unary op for TLA+: {expr.op}")
    if isinstance(expr, BinOp):
        left = _tla_expr(expr.left)
        right = _tla_expr(expr.right)
        op = expr.op
        mapping = {
            "and": "/\\",
            "or": "\\/",
            "eq": "=",
            "ne": "/=",
            "lt": "<",
            "le": "<=",
            "gt": ">",
            "ge": ">=",
            "add": "+",
            "sub": "-",
        }
        if op == "implies":
            return f"({left}) => ({right})"
        if op not in mapping:
            raise ValueError(f"Unknown binary op for TLA+: {op}")
        return f"({left}) {mapping[op]} ({right})"
    raise TypeError(f"Not an expression: {expr!r}")


def _tla_assignment(assignment: Assignment) -> str:
    return f"{_sanitize_ident(assignment.target)}' = {_tla_expr(assignment.expr)}"


def _tla_action(action: Action, var_names: list[str]) -> str:
    lines = [f"{_sanitize_ident(action.name)} =="]
    if action.comment:
        lines.append(f"    \\* {action.comment}")
    lines.append(f"    /\\ {_tla_expr(action.guard)}")
    assigned = {a.target for a in action.assignments}
    for name in var_names:
        ident = _sanitize_ident(name)
        if name in assigned:
            match = next(a for a in action.assignments if a.target == name)
            lines.append(f"    /\\ {_tla_assignment(match)}")
        else:
            # frame condition: unchanged
            lines.append(f"    /\\ {ident}' = {ident}")
    return "\n".join(lines)


def _tla_typeok(variables: tuple[StateVar, ...]) -> str:
    parts = [f"{_sanitize_ident(v.name)} \\in {_tla_domain(v.domain)}" for v in variables]
    body = "\n    /\\ ".join(parts)
    return "TypeOK ==\n    /\\ " + body


def emit_tla(spec: Spec) -> str:
    """Render ``spec`` as a TLA+-like module string."""
    module_name = _sanitize_ident(spec.name.replace(" ", "_"))
    var_names = [v.name for v in spec.variables]
    var_idents = [_sanitize_ident(n) for n in var_names]

    parts: list[str] = []
    parts.append(f"---- MODULE {module_name} ----")
    parts.append("EXTENDS Naturals, FiniteSets, Sequences, TLC")
    if spec.description:
        parts.append("")
        parts.append("\\* " + spec.description.replace("\n", "\n\\* "))
    parts.append("")
    parts.append("VARIABLES " + ", ".join(var_idents))
    parts.append("")
    parts.append("vars == << " + ", ".join(var_idents) + " >>")
    parts.append("")

    # TypeOK
    parts.append(_tla_typeok(spec.variables))
    parts.append("")

    # Init
    parts.append("Init ==")
    parts.append(f"    {_tla_expr(spec.init)}")
    parts.append("")

    # Next
    if spec.actions:
        action_ids = [_sanitize_ident(a.name) for a in spec.actions]
        parts.append("Next ==")
        for i, aid in enumerate(action_ids):
            prefix = "    \\/ " if i == 0 else "    \\/ "
            parts.append(f"{prefix}{aid}")
    else:
        parts.append("Next ==")
        parts.append("    FALSE  \\* no actions defined")
    parts.append("")

    # Spec formula
    parts.append(f"Spec == Init /\\ [][Next]_vars")
    parts.append("")

    # Actions
    for action in spec.actions:
        parts.append(_tla_action(action, var_names))
        parts.append("")

    # Invariants
    if spec.invariants:
        conjuncts = " /\\ ".join(f"({_tla_expr(i.expr)})" for i in spec.invariants)
        parts.append("Invariants ==")
        for inv in spec.invariants:
            parts.append(f"    \\* {inv.name}: {inv.comment or ''}".rstrip())
        parts.append(f"    {conjuncts}")
        parts.append("")

    # Safety checks
    safety = [c for c in spec.checks if c.kind == "safety"]
    if safety:
        conjuncts = " /\\ ".join(f"({_tla_expr(c.expr)})" for c in safety)
        parts.append("Safety ==")
        for c in safety:
            parts.append(f"    \\* {c.name}: {c.comment or ''}".rstrip())
        parts.append(f"    {conjuncts}")
        parts.append("")

    # Liveness as comments (bounded, not temporal)
    live = [c for c in spec.checks if c.kind == "liveness"]
    if live:
        parts.append("\\* Bounded reachability properties (NOT full TLA+ liveness):")
        for c in live:
            parts.append(f"\\*   {c.name}: {_tla_expr(c.expr)}")
        parts.append("")

    parts.append("====")
    return "\n".join(parts) + "\n"
