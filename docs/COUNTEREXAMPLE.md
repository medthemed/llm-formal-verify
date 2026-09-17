# Reading a counterexample

This page walks through a full run of the bundled unsafe transfer example:
what the invariant means, how to read the trace, how to fix the action, and
when to change `--bound`.

## The setup

`examples/unsafe_transfer.json` models two accounts with balances in
`0..4` and a `locked` flag. Money is supposed to be conserved:

```
balance_a + balance_b == 4
```

That invariant is named `total_conserved`. The initial state is
`(balance_a=2, balance_b=2, locked=false)`, so it holds at depth 0.

The transfer action is intentionally buggy: it debits account A but never
credits account B.

```text
TransferAtoB
  guard: balance_a > 0 and not locked
  effect: balance_a' = balance_a - 1
          (balance_b is left unchanged)
```

## Run the checker

```bash
lfv check examples/unsafe_transfer.json --bound 6
```

You should see something like:

```text
BMC result for 'UnsafeTransfer' (bound=6)
  reachable states (within bound): …
  transitions explored: …
  overall: FAIL

[FAIL] total_conserved (safety) states_examined=…
COUNTEREXAMPLE for 'total_conserved' (safety)
  reason: property violated in state {'balance_a': 1, 'balance_b': 2, 'locked': False}
  trace:
    [0] --Init--> {'balance_a': 2, 'balance_b': 2, 'locked': False}
    [1] --TransferAtoB--> {'balance_a': 1, 'balance_b': 2, 'locked': False}
```

Exit code is `1` (failure). That is the signal CI should gate on.

## How to read the trace

Each step is `--[action]--> state`:

| Step | Action | balance_a | balance_b | total | Why it matters |
| ---: | --- | ---: | ---: | ---: | --- |
| 0 | `Init` | 2 | 2 | 4 | Invariant holds. |
| 1 | `TransferAtoB` | 1 | 2 | 3 | A lost 1, B did not gain it. **Invariant broken.** |

The checker explores breadth-first, so the first safety violation it reports
is a *shortest* path in this state space: one transfer is enough to lose money.
You do not need a deep bound to see the bug — you need the *right* invariant.

The `reason` line names the concrete violating state. The `trace` is the
parent-pointer path reconstructed from that state back to an initial state.

## Machine-readable form

For dashboards or annotation bots:

```bash
lfv check examples/unsafe_transfer.json --bound 6 --json
```

```json
{
  "ok": false,
  "spec": "UnsafeTransfer",
  "bound": 6,
  "failures": ["total_conserved"],
  "checks": [
    {
      "name": "total_conserved",
      "kind": "safety",
      "status": "failed",
      "counterexample": {
        "steps": [
          {"index": 0, "action": "Init", "state": {"balance_a": 2, "balance_b": 2, "locked": false}},
          {"index": 1, "action": "TransferAtoB", "state": {"balance_a": 1, "balance_b": 2, "locked": false}}
        ]
      }
    }
  ]
}
```

## Fix it and re-check

Credit account B in the same action (see `examples/safe_transfer.json`):

```text
TransferAtoB
  guard: balance_a > 0 and balance_b < 4 and not locked
  effect: balance_a' = balance_a - 1
          balance_b' = balance_b + 1
```

```bash
lfv check examples/safe_transfer.json --bound 6
```

```text
overall: PASS
```

If a run still fails after a "fix", copy the printed state into a unit test
— the counterexample is already a minimal reproducer.

## Bound vs domain size

| Situation | What to change |
| --- | --- |
| Bug needs more than N transfers to appear | Raise `--bound` |
| State space is huge / slow | Shrink variable domains |
| Invariant only fails after a long sequence | Usually a sign you need a higher bound *or* a tighter invariant |

`--bound 0` checks only the initial states. `--bound 6` on the bundled
examples is already enough to expose the transfer bug. Keep domains small:
the checker enumerates the full product of domains, so
`prod(len(domain))` is your real cost.

## Takeaway

1. Write the invariant first (`total_conserved`).
2. Run `lfv check` and read the shortest counterexample.
3. Fix the action, re-run until PASS.
4. Feed `--json` output to CI if you want the path in annotations.
