"""Bounded model checker.

Explores the finite state space of a :class:`~llm_formal_verify.ir.Spec`
breadth-first, up to a configurable depth bound. Reports either:

- every safety / invariant check holds on all reachable states within the
  bound, or
- a concrete counterexample trace (sequence of states and actions) that
  violates a check.

Liveness checks here are *bounded reachability*: "does a state satisfying
P appear within the bound?" — not unbounded temporal liveness.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .ir import Action, Check, Spec, apply_action, eval_expr


@dataclass(frozen=True)
class Step:
    """One transition in a counterexample trace."""

    action: str
    state: dict[str, Any]

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"--[{self.action}]-->{self.state}"

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "state": dict(self.state)}


@dataclass
class Counterexample:
    """A concrete trace from an initial state to a violating state."""

    check_name: str
    kind: str  # "safety" | "liveness"
    reason: str
    steps: list[Step] = field(default_factory=list)

    def trace_length(self) -> int:
        return len(self.steps)

    def format(self) -> str:
        lines = [
            f"COUNTEREXAMPLE for {self.check_name!r} ({self.kind})",
            f"  reason: {self.reason}",
            "  trace:",
        ]
        for i, step in enumerate(self.steps):
            lines.append(f"    [{i}] --{step.action}--> {step.state}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check_name,
            "kind": self.kind,
            "reason": self.reason,
            "length": self.trace_length(),
            "steps": [
                {"index": i, **step.to_dict()} for i, step in enumerate(self.steps)
            ],
        }


@dataclass
class CheckResult:
    name: str
    kind: str
    status: str  # "ok" | "failed" | "unreachable"
    counterexample: Counterexample | None = None
    states_examined: int = 0
    witness: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def format(self) -> str:
        mark = {"ok": "PASS", "failed": "FAIL", "unreachable": "UNREACH"}[self.status]
        head = f"[{mark}] {self.name} ({self.kind}) states_examined={self.states_examined}"
        if self.status == "failed" and self.counterexample is not None:
            return head + "\n" + self.counterexample.format()
        if self.status == "ok" and self.witness is not None:
            return head + f"\n  witness: {self.witness}"
        if self.status == "unreachable":
            return head + "\n  property never became true within the bound"
        return head

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "states_examined": self.states_examined,
        }
        if self.counterexample is not None:
            payload["counterexample"] = self.counterexample.to_dict()
        if self.witness is not None:
            payload["witness"] = dict(self.witness)
        return payload


@dataclass
class BMCResult:
    spec_name: str
    bound: int
    reachable_states: int
    transitions_explored: int
    results: list[CheckResult]

    @property
    def ok(self) -> bool:
        return all(r.status in ("ok", "unreachable") for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "failed"]

    def format(self) -> str:
        lines = [
            f"BMC result for {self.spec_name!r} (bound={self.bound})",
            f"  reachable states (within bound): {self.reachable_states}",
            f"  transitions explored: {self.transitions_explored}",
            f"  overall: {'PASS' if self.ok else 'FAIL'}",
            "",
        ]
        for r in self.results:
            lines.append(r.format())
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec_name,
            "bound": self.bound,
            "ok": self.ok,
            "reachable_states": self.reachable_states,
            "transitions_explored": self.transitions_explored,
            "checks": [r.to_dict() for r in self.results],
            "failures": [r.name for r in self.failures],
        }

    def to_json(self, *, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, sort_keys=False) + "\n"


def _freeze(state: Mapping[str, Any]) -> tuple:
    """Canonical hashable key for a state dict."""
    return tuple(sorted(state.items()))


def _all_checks(spec: Spec) -> list[Check]:
    return list(spec.invariants) + list(spec.checks)


def bounded_model_check(spec: Spec, bound: int = 8) -> BMCResult:
    """Explore states reachable within ``bound`` transition steps.

    Parameters
    ----------
    spec:
        The specification to check.
    bound:
        Maximum transition depth. Depth 0 means "check initial states only".
    """
    if bound < 0:
        raise ValueError("bound must be >= 0")

    vmap = spec.var_map()
    initial_states = [s for s in spec.domain_product() if eval_expr(spec.init, s)]

    # BFS over depth-bounded reachable set.
    # visited maps frozen-state -> (state, depth, parent_frozen, action_name)
    visited: dict[tuple, tuple[dict[str, Any], int, tuple | None, str | None]] = {}
    queue: deque[tuple] = deque()
    transitions_explored = 0

    for state in initial_states:
        key = _freeze(state)
        if key not in visited:
            visited[key] = (state, 0, None, None)
            queue.append(key)

    reachable_at_depth: dict[int, list[tuple]] = {0: list(visited.keys())}

    while queue:
        key = queue.popleft()
        state, depth, _, _ = visited[key]
        if depth >= bound:
            continue
        for action in spec.actions:
            successor = apply_action(action, state)
            if successor is None:
                continue
            transitions_explored += 1
            # Sanity: successor must stay inside declared domains.
            for name, value in successor.items():
                if value not in vmap[name].domain:
                    raise ValueError(
                        f"Action {action.name!r} produced out-of-domain value "
                        f"{value!r} for {name!r} (domain={list(vmap[name].domain)})"
                    )
            succ_key = _freeze(successor)
            if succ_key not in visited:
                visited[succ_key] = (successor, depth + 1, key, action.name)
                queue.append(succ_key)
                reachable_at_depth.setdefault(depth + 1, []).append(succ_key)

    # Build parent map for traces.
    def trace_to(key: tuple) -> list[Step]:
        chain: list[Step] = []
        current: tuple | None = key
        while current is not None:
            state, _, parent, action_name = visited[current]
            chain.append(Step(action=action_name or "Init", state=dict(state)))
            current = parent
        chain.reverse()
        return chain

    results: list[CheckResult] = []

    for check in _all_checks(spec):
        if check.kind == "safety":
            violation: Counterexample | None = None
            examined = 0
            for key, (state, _, _, _) in visited.items():
                examined += 1
                if not eval_expr(check.expr, state):
                    violation = Counterexample(
                        check_name=check.name,
                        kind="safety",
                        reason=f"property violated in state {state}",
                        steps=trace_to(key),
                    )
                    break
            results.append(
                CheckResult(
                    name=check.name,
                    kind="safety",
                    status="failed" if violation else "ok",
                    counterexample=violation,
                    states_examined=examined,
                )
            )
        else:  # liveness / bounded reachability
            witness_state: dict[str, Any] | None = None
            witness_key: tuple | None = None
            examined = 0
            for key, (state, _, _, _) in visited.items():
                examined += 1
                if eval_expr(check.expr, state):
                    witness_state = state
                    witness_key = key
                    break
            if witness_state is None:
                results.append(
                    CheckResult(
                        name=check.name,
                        kind="liveness",
                        status="unreachable",
                        counterexample=None,
                        states_examined=examined,
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=check.name,
                        kind="liveness",
                        status="ok",
                        counterexample=None,
                        states_examined=examined,
                        witness=dict(witness_state),
                    )
                )

    return BMCResult(
        spec_name=spec.name,
        bound=bound,
        reachable_states=len(visited),
        transitions_explored=transitions_explored,
        results=results,
    )
