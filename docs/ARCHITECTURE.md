# Architecture

## Goals

Give teams a **machine-checkable** intermediate form for business rules that
LLMs (or humans) write, so the rules can be exhaustively explored on small
finite domains instead of only sampled by unit tests.

Non-goals for v0.1:

- Full first-order logic, quantifiers, unbounded integers.
- Unbounded temporal logic (LTL/CTL). "Liveness" here means bounded reachability.
- Integration with TLC, Apalache, Coq, or any external prover.

## Pipeline

```
  builder.py  ──►  ir.Spec  ──►  bmc.bounded_model_check  ──►  BMCResult
                      │
                      └──────►  tla_emit.emit_tla         ──►  TLA+-like text
                      │
                      └──────►  JSON (cli load)            ◄──  examples/*.json
```

## Modules

| Module | Responsibility |
| --- | --- |
| `ir.py` | Core dataclasses: `StateVar`, `Expr` tree, `Action`, `Check`, `Spec`. Evaluation (`eval_expr`, `apply_action`) and JSON round-trip. |
| `builder.py` | Fluent `SpecBuilder` over the IR. Sugar for int/bool/enum vars and mixed literal/expression assignments. |
| `bmc.py` | Breadth-first bounded explorer. Produces `BMCResult` with per-check `CheckResult` and counterexample traces. |
| `tla_emit.py` | Pretty-printer that turns a `Spec` into a TLA+-like module (TypeOK, Init, Next, Invariants, Safety). Liveness is emitted as a comment. |
| `cli.py` | `argparse` front-end: `lfv check`, `lfv tla`. Exit codes: 0 pass, 1 check failure, 2 load/internal error. |

## IR design notes

### Expressions

Expressions are a closed ADT (`Lit`, `VarRef`, `Unary`, `BinOp`) stored as
frozen dataclasses so they hash cleanly. Operators:

- Boolean: `and`, `or`, `not`, `implies`
- Comparison: `eq`, `ne`, `lt`, `le`, `gt`, `ge`
- Arithmetic: `add`, `sub` (results must stay inside the declared domain;
  the checker raises if an action produces an out-of-domain value)

No quantifiers. Free-variable analysis is used by `Spec.validate()` to reject
typos before any exploration starts.

### Finite domains

Every state variable carries an explicit domain. The checker never invents
values outside those domains. This is what makes exhaustive exploration
terminating and cheap: `|States| = Π |domain(v)|`.

### Actions and frame conditions

An action is `(name, guard, assignments)`. Variables absent from
`assignments` keep their current value. The TLA+ emitter writes this as an
explicit `x' = x` frame condition.

### Checks

- **safety** — must hold in *every* reachable state within the bound.
- **liveness** — a *bounded reachability* claim: some reachable state within
  the bound satisfies the predicate. Status `unreachable` is reported but
  does not fail the overall run (it is not a safety violation).

## BMC algorithm

```
visited := {}
queue   := BFS queue of frozen states

for s in domains where Init(s):
    enqueue s at depth 0

while queue:
    s, d := pop
    if d >= bound: continue
    for a in actions:
        s' := apply(a, s)   # None if guard false
        if s' is new:
            record parent pointer (s, a)
            enqueue s' at d+1

for each safety check:
    scan visited; on violation, walk parent pointers → Counterexample

for each liveness check:
    scan visited for a witness
```

Parent pointers reconstruct a shortest-ish (BFS) counterexample trace, which
is what makes the output actionable for a human reading a failing PR.

## Serialization

`Spec.to_json()` / `Spec.from_json()` are the wire format used by the CLI.
Expression trees serialize as `{kind, ...}` objects. This is intentionally
boring and greppable.

## Extension points (post-MVP)

- Arithmetic beyond `add`/`sub` (`mul`, `mod`, min/max).
- Symmetry reduction on interchangeable variables.
- Inductive invariant candidates (prove Init ⇒ Inv and Inv ∧ Next ⇒ Inv').
- Optional TLC/Apalache export backends that emit *runnable* modules rather
  than review-oriented text.

## Testing strategy

- Unit tests for IR evaluation and JSON round-trips.
- Builder sugar tests (including mixed literal/expression assignments).
- BMC: a safe transfer spec must pass; a money-destroying transfer must fail
  with a counterexample whose final total is wrong.
- TLA export: module structure, invariant names, action names.
- CLI: exit codes, missing file handling, packaged example end-to-end.
