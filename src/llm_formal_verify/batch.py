"""Batch bounded-model-check across many spec files.

Lets CI and local review run one command over a folder of specs and get an
aggregate pass/fail table instead of one process per file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .bmc import BMCResult, bounded_model_check
from .errors import ModelError, SpecError
from .ir import Spec

SPEC_SUFFIXES = (".json",)


def expand_spec_paths(paths: Sequence[str | Path]) -> list[Path]:
    """Expand directories to the ``*.json`` specs they contain.

    Files are returned as-is (even if missing) so the caller can report a
    per-path load error. Directories contribute their immediate ``*.json``
    children, sorted for stable tables.
    """
    expanded: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            children = sorted(
                p for p in path.iterdir() if p.is_file() and p.suffix in SPEC_SUFFIXES
            )
            expanded.extend(children)
        else:
            expanded.append(path)
    return expanded


def load_spec_file(path: str | Path) -> Spec:
    """Read a JSON spec from disk and build the IR."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return Spec.from_json(data)


@dataclass
class SpecOutcome:
    """Outcome of checking one spec path."""

    path: str
    result: BMCResult | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.result is not None and self.result.ok

    @property
    def status(self) -> str:
        if self.error is not None or self.result is None:
            return "error"
        return "pass" if self.result.ok else "fail"

    @property
    def label(self) -> str:
        return Path(self.path).name or self.path

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "status": self.status,
        }
        if self.error is not None:
            payload["error"] = self.error
        if self.result is not None:
            payload["result"] = self.result.to_dict()
        return payload


@dataclass
class BatchCheckResult:
    """Aggregate of checking many specs with one bound / search setting."""

    outcomes: list[SpecOutcome] = field(default_factory=list)
    bound: int = 8
    search: str = "bfs"

    @property
    def ok(self) -> bool:
        return bool(self.outcomes) and all(o.ok for o in self.outcomes)

    @property
    def passed(self) -> list[SpecOutcome]:
        return [o for o in self.outcomes if o.status == "pass"]

    @property
    def failed(self) -> list[SpecOutcome]:
        return [o for o in self.outcomes if o.status == "fail"]

    @property
    def errors(self) -> list[SpecOutcome]:
        return [o for o in self.outcomes if o.status == "error"]

    def format_table(self) -> str:
        """Human-readable aggregate pass/fail table."""
        header = ("SPEC", "STATUS", "FAILURES", "STATES")
        rows: list[tuple[str, str, str, str]] = [header]
        for outcome in self.outcomes:
            if outcome.result is not None:
                failures = str(len(outcome.result.failures))
                states = str(outcome.result.reachable_states)
            else:
                failures = "-"
                states = "-"
            rows.append((outcome.label, outcome.status.upper(), failures, states))

        widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
        lines: list[str] = []
        for index, row in enumerate(rows):
            lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
            if index == 0:
                lines.append("  ".join("-" * widths[i] for i in range(len(header))))

        lines.append("")
        lines.append(
            f"{len(self.outcomes)} checked, "
            f"{len(self.passed)} passed, "
            f"{len(self.failed)} failed, "
            f"{len(self.errors)} errors "
            f"(bound={self.bound}, search={self.search})"
        )
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "bound": self.bound,
            "search": self.search,
            "ok": self.ok,
            "count": len(self.outcomes),
            "passed": len(self.passed),
            "failed": len(self.failed),
            "errors": len(self.errors),
            "results": [o.to_dict() for o in self.outcomes],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False) + "\n"


_LOAD_ERRORS = (
    OSError,
    json.JSONDecodeError,
    KeyError,
    SpecError,
    ModelError,
    TypeError,
    ValueError,
)


def check_many(
    paths: Sequence[str | Path],
    *,
    bound: int = 8,
    search: str = "bfs",
    expand: bool = True,
) -> BatchCheckResult:
    """Check every path and aggregate results.

    ``expand=True`` (default) expands directories to contained ``*.json``
    files first. Load and model-check failures become ``error`` outcomes
    rather than raising, so one broken file does not hide the rest.
    """
    resolved = expand_spec_paths(paths) if expand else [Path(p) for p in paths]
    outcomes: list[SpecOutcome] = []
    for path in resolved:
        label = str(path)
        try:
            spec = load_spec_file(path)
            result = bounded_model_check(spec, bound=bound, search=search)
        except _LOAD_ERRORS as exc:
            outcomes.append(SpecOutcome(path=label, error=str(exc)))
            continue
        outcomes.append(SpecOutcome(path=label, result=result))
    return BatchCheckResult(outcomes=outcomes, bound=bound, search=search)
