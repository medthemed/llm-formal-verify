"""Command-line interface for llm-formal-verify.

Subcommands
-----------
lfv check SPEC.json [SPEC.json ...] [--bound N] [--search bfs|dfs] [--json]
    Run the bounded model checker on one or more specs. Directories expand
    to their ``*.json`` children. A single file prints the verbose report;
    multiple paths print an aggregate pass/fail table. Exit 0 = all pass,
    1 = any check failed, 2 = load / model error.
    Defaults (bound, search) come from a project config file when present;
    explicit flags always win.

lfv tla SPEC.json
    Print a TLA+-like module for the spec.

lfv init [DIR] [--force]
    Scaffold a starter ``spec.json`` and ``.lfv.json`` project config.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .batch import check_many, expand_spec_paths
from .bmc import bounded_model_check
from .config import VALID_SEARCH_STRATEGIES, resolve_check_options
from .errors import ModelError, SpecError
from .init import write_starter
from .ir import Spec
from .tla_emit import emit_tla


def _load_spec(path: str | Path) -> Spec:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return Spec.from_json(data)


def _wants_json(args: argparse.Namespace) -> bool:
    fmt = getattr(args, "format", None)
    if fmt == "json":
        return True
    return bool(getattr(args, "json", False))


def cmd_check(args: argparse.Namespace) -> int:
    try:
        bound, search = resolve_check_options(bound=args.bound, search=args.search)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    specs: list[str] = list(args.specs)
    expanded = expand_spec_paths(specs)
    multi = len(expanded) != 1 or len(specs) > 1 or any(
        Path(p).is_dir() for p in specs
    )

    if not multi:
        # Single file: keep the historical verbose / per-spec JSON report.
        try:
            spec = _load_spec(expanded[0])
        except (OSError, json.JSONDecodeError, KeyError, SpecError, TypeError) as exc:
            print(f"error: failed to load spec: {exc}", file=sys.stderr)
            return 2

        try:
            result = bounded_model_check(spec, bound=bound, search=search)
        except (ModelError, SpecError) as exc:
            print(f"error: model checking failed: {exc}", file=sys.stderr)
            return 2

        if _wants_json(args):
            print(result.to_json(), end="")
        else:
            print(result.format())
        return 0 if result.ok else 1

    if not expanded:
        print("error: no spec files found", file=sys.stderr)
        return 2

    batch = check_many(expanded, bound=bound, search=search, expand=False)
    if _wants_json(args):
        print(batch.to_json(), end="")
    else:
        print(batch.format_table(), end="")
    if batch.errors and not batch.outcomes:
        return 2
    if batch.errors and not batch.failed and not batch.passed:
        return 2
    return 0 if batch.ok else 1


def cmd_tla(args: argparse.Namespace) -> int:
    try:
        spec = _load_spec(args.spec)
    except (OSError, json.JSONDecodeError, KeyError, SpecError, TypeError) as exc:
        print(f"error: failed to load spec: {exc}", file=sys.stderr)
        return 2

    print(emit_tla(spec), end="")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    directory = args.directory or "."
    try:
        written = write_starter(directory, force=args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: cannot write starter files: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(f"wrote {path}")
    print("Next: lfv check spec.json")
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

    p_check = sub.add_parser(
        "check",
        help="run the bounded model checker on one or more specs",
    )
    p_check.add_argument(
        "specs",
        nargs="+",
        help="path(s) to JSON spec file(s); directories expand to *.json",
    )
    p_check.add_argument(
        "--bound",
        type=int,
        default=None,
        help=(
            "maximum transition depth to explore "
            "(default: project config, else 8)"
        ),
    )
    p_check.add_argument(
        "--search",
        choices=sorted(VALID_SEARCH_STRATEGIES),
        default=None,
        help=(
            "exploration order: bfs (shortest counterexample) or dfs "
            "(default: project config, else bfs)"
        ),
    )
    p_check.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable JSON report instead of text",
    )
    p_check.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text; --json is an alias for --format json)",
    )
    p_check.set_defaults(func=cmd_check)

    p_tla = sub.add_parser("tla", help="print a TLA+-like module for the spec")
    p_tla.add_argument("spec", help="path to a JSON spec file")
    p_tla.set_defaults(func=cmd_tla)

    p_init = sub.add_parser(
        "init",
        help="scaffold a starter spec.json and .lfv.json project config",
    )
    p_init.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="target directory (default: current directory)",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing starter files",
    )
    p_init.set_defaults(func=cmd_init)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
