"""Command-line interface for llm-formal-verify.

Subcommands
-----------
lfv check SPEC.json [SPEC.json ...] [--bound N] [--search bfs|dfs] [--json|--format json]
    Run the bounded model checker on one or more specs. Directories expand
    to their ``*.json`` children. A single file prints the verbose report;
    multiple paths print an aggregate pass/fail table. Exit 0 = all pass,
    1 = any check failed, 2 = load / model error.
    ``SPEC`` may be ``-`` to read a single JSON spec from stdin instead
    (it cannot be combined with other paths).
    Defaults (bound, search) come from a project config file when present;
    explicit flags always win.
    JSON payloads match schemas ``bmc-report`` / ``batch-report``.

lfv watch SPEC.json [SPEC.json ...] [--bound N] [--search bfs|dfs] [--interval S] [--once]
    Check the specs, then keep polling and re-check whenever a file
    changes (mtime/size). ``--once`` runs a single pass (CI-friendly).
    Ctrl-C exits cleanly. Exit codes match ``lfv check`` batch mode.

lfv tla SPEC.json [--format text|json]
    Print a TLA+-like module for the spec. ``--format json`` wraps the text
    as ``{"module": "..."}`` (schema: ``tla-module``).

lfv init [DIR] [--force]
    Scaffold a starter ``spec.json`` and ``.lfv.json`` project config.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .batch import (
    batch_exit_code,
    check_many,
    expand_spec_paths,
    load_spec_file,
    load_spec_from_stdin,
)
from .bmc import bounded_model_check
from .config import VALID_SEARCH_STRATEGIES, resolve_check_options
from .errors import ModelError, SpecError
from .init import write_starter
from .ir import Spec
from .tla_emit import emit_tla
from .watch import DEFAULT_INTERVAL, watch_specs

#: Errors that mean "this spec could not be loaded" — reported as a clean
#: ``error: ...`` on stderr with exit code 2, never a traceback. ``ValueError``
#: covers JSONDecodeError, UnicodeDecodeError, SpecError and the plain
#: ``ValueError`` the IR raises for unknown expression kinds.
_LOAD_ERRORS = (OSError, ValueError, KeyError, TypeError)


def _load_spec(path: str | Path) -> Spec:
    return load_spec_file(path)


def _wants_json(args: argparse.Namespace) -> bool:
    fmt = getattr(args, "format", None)
    if fmt == "json":
        return True
    return bool(getattr(args, "json", False))


def _report_single(spec: Spec, args: argparse.Namespace, bound: int, search: str) -> int:
    """Run the checker on one spec and print the single-spec report."""
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


def cmd_check(args: argparse.Namespace) -> int:
    try:
        bound, search = resolve_check_options(bound=args.bound, search=args.search)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    specs: list[str] = list(args.specs)

    # ``-`` reads a single spec from stdin; it cannot be combined.
    if "-" in specs:
        if len(specs) > 1:
            print(
                "error: '-' (stdin) cannot be combined with other spec paths",
                file=sys.stderr,
            )
            return 2
        try:
            spec = load_spec_from_stdin()
        except _LOAD_ERRORS as exc:
            print(f"error: failed to load spec from stdin: {exc}", file=sys.stderr)
            return 2
        return _report_single(spec, args, bound, search)

    expanded = expand_spec_paths(specs)
    multi = len(expanded) != 1 or len(specs) > 1 or any(
        Path(p).is_dir() for p in specs
    )

    if not multi:
        # Single file: keep the historical verbose / per-spec JSON report.
        try:
            spec = _load_spec(expanded[0])
        except _LOAD_ERRORS as exc:
            print(f"error: failed to load spec: {exc}", file=sys.stderr)
            return 2
        return _report_single(spec, args, bound, search)

    if not expanded:
        print("error: no spec files found", file=sys.stderr)
        return 2

    batch = check_many(expanded, bound=bound, search=search, expand=False)
    if _wants_json(args):
        print(batch.to_json(), end="")
    else:
        print(batch.format_table(), end="")
    return batch_exit_code(batch)


def cmd_watch(args: argparse.Namespace) -> int:
    try:
        bound, search = resolve_check_options(bound=args.bound, search=args.search)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not expand_spec_paths(list(args.specs)):
        print("error: no spec files found", file=sys.stderr)
        return 2

    try:
        return watch_specs(
            list(args.specs),
            bound=bound,
            search=search,
            interval=args.interval,
            once=args.once,
        )
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def cmd_tla(args: argparse.Namespace) -> int:
    try:
        spec = _load_spec(args.spec)
    except _LOAD_ERRORS as exc:
        print(f"error: failed to load spec: {exc}", file=sys.stderr)
        return 2

    text = emit_tla(spec)
    if _wants_json(args):
        print(json.dumps({"module": text}, indent=2) + "\n", end="")
    else:
        print(text, end="")
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
        help="path(s) to JSON spec file(s); directories expand to *.json; "
        "'-' alone reads one spec from stdin",
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

    p_watch = sub.add_parser(
        "watch",
        help="check specs, then re-check whenever a file changes",
    )
    p_watch.add_argument(
        "specs",
        nargs="+",
        help="path(s) to JSON spec file(s); directories expand to *.json",
    )
    p_watch.add_argument(
        "--bound",
        type=int,
        default=None,
        help=(
            "maximum transition depth to explore "
            "(default: project config, else 8)"
        ),
    )
    p_watch.add_argument(
        "--search",
        choices=sorted(VALID_SEARCH_STRATEGIES),
        default=None,
        help=(
            "exploration order: bfs (shortest counterexample) or dfs "
            "(default: project config, else bfs)"
        ),
    )
    p_watch.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"poll interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    p_watch.add_argument(
        "--once",
        action="store_true",
        help="run a single pass and return (CI-friendly)",
    )
    p_watch.set_defaults(func=cmd_watch)

    p_tla = sub.add_parser("tla", help="print a TLA+-like module for the spec")
    p_tla.add_argument("spec", help="path to a JSON spec file")
    p_tla.add_argument(
        "--json",
        action="store_true",
        help="emit {\"module\": \"...\"} JSON (schema: tla-module)",
    )
    p_tla.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text; --json is an alias for --format json)",
    )
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
