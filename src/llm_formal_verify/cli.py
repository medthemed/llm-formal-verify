"""Command-line interface for llm-formal-verify.

Subcommands
-----------
lfv check SPEC.json [--bound N] [--json]
    Run the bounded model checker. Exit code 0 = all checks pass, 1 = failure.
    With --json, print a structured report suitable for CI tooling.

lfv tla SPEC.json
    Print a TLA+-like module for the spec.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .bmc import bounded_model_check
from .ir import Spec
from .tla_emit import emit_tla


def _load_spec(path: str | Path) -> Spec:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return Spec.from_json(data)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        spec = _load_spec(args.spec)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        print(f"error: failed to load spec: {exc}", file=sys.stderr)
        return 2

    try:
        result = bounded_model_check(spec, bound=args.bound)
    except ValueError as exc:
        print(f"error: model checking failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json(), end="")
    else:
        print(result.format())
    return 0 if result.ok else 1


def cmd_tla(args: argparse.Namespace) -> int:
    try:
        spec = _load_spec(args.spec)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        print(f"error: failed to load spec: {exc}", file=sys.stderr)
        return 2

    print(emit_tla(spec), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lfv",
        description=(
            "Bounded formal checks for business-logic specs. "
            "Not a full proof assistant — explores finite domains up to a bound."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="run the bounded model checker")
    p_check.add_argument("spec", help="path to a JSON spec file")
    p_check.add_argument(
        "--bound",
        type=int,
        default=8,
        help="maximum transition depth to explore (default: 8)",
    )
    p_check.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable JSON report instead of text",
    )
    p_check.set_defaults(func=cmd_check)

    p_tla = sub.add_parser("tla", help="print a TLA+-like module for the spec")
    p_tla.add_argument("spec", help="path to a JSON spec file")
    p_tla.set_defaults(func=cmd_tla)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
