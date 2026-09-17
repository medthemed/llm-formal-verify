"""Project-level configuration for llm-formal-verify.

A small JSON file sitting next to your specs can set defaults so CI and
local runs agree without repeating flags:

    {
      "bound": 10,
      "search": "bfs"
    }

Lookup order (first hit wins for each key):

1. Explicit CLI flag (``--bound``, ``--search``)
2. ``.lfv.json`` in the current directory
3. ``lfv.config.json`` in the current directory
4. Built-in default (``bound=8``, ``search="bfs"``)

Only the keys ``bound`` and ``search`` are recognised today; extra keys
are ignored so the file can grow without breaking older CLIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import SpecError

#: Filenames probed in the current directory, in order.
CONFIG_FILENAMES = (".lfv.json", "lfv.config.json")

#: Built-in defaults used when no config file is present.
DEFAULT_BOUND = 8
DEFAULT_SEARCH = "bfs"

#: Search strategies understood by the BMC.
VALID_SEARCH_STRATEGIES = frozenset({"bfs", "dfs"})


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved project defaults for ``lfv check``."""

    bound: int = DEFAULT_BOUND
    search: str = DEFAULT_SEARCH
    source: str | None = None  # path of the config file, if any

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"bound": self.bound, "search": self.search}
        if self.source:
            payload["source"] = self.source
        return payload


def _coerce_bound(value: Any, source: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecError(f"{source}: 'bound' must be an integer, got {value!r}")
    if value < 0:
        raise SpecError(f"{source}: 'bound' must be >= 0, got {value}")
    return value


def _coerce_search(value: Any, source: str) -> str:
    if not isinstance(value, str) or value not in VALID_SEARCH_STRATEGIES:
        raise SpecError(
            f"{source}: 'search' must be one of {sorted(VALID_SEARCH_STRATEGIES)}, "
            f"got {value!r}"
        )
    return value


def load_config(path: str | Path) -> ProjectConfig:
    """Load a single config file. Raises :class:`SpecError` on bad content."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"cannot read config {p}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SpecError(f"{p}: not valid JSON: {exc}") from exc
    if not isinstance(data, Mapping):
        raise SpecError(f"{p}: config must be a JSON object, got {type(data).__name__}")

    bound = DEFAULT_BOUND
    search = DEFAULT_SEARCH
    if "bound" in data:
        bound = _coerce_bound(data["bound"], str(p))
    if "search" in data:
        search = _coerce_search(data["search"], str(p))
    return ProjectConfig(bound=bound, search=search, source=str(p))


def discover_config(directory: str | Path | None = None) -> ProjectConfig:
    """Probe ``directory`` (default: cwd) for a known config filename."""
    base = Path(directory) if directory is not None else Path.cwd()
    for name in CONFIG_FILENAMES:
        candidate = base / name
        if candidate.is_file():
            return load_config(candidate)
    return ProjectConfig()


def resolve_check_options(
    *,
    bound: int | None = None,
    search: str | None = None,
    config: ProjectConfig | None = None,
    directory: str | Path | None = None,
) -> tuple[int, str]:
    """Merge CLI flags over project config over built-in defaults.

    Returns ``(bound, search)``.
    """
    cfg = config if config is not None else discover_config(directory)
    resolved_bound = cfg.bound if bound is None else bound
    resolved_search = cfg.search if search is None else search
    if resolved_bound < 0:
        raise SpecError(f"bound must be >= 0, got {resolved_bound}")
    if resolved_search not in VALID_SEARCH_STRATEGIES:
        raise SpecError(
            f"search must be one of {sorted(VALID_SEARCH_STRATEGIES)}, "
            f"got {resolved_search!r}"
        )
    return resolved_bound, resolved_search


__all__ = [
    "CONFIG_FILENAMES",
    "DEFAULT_BOUND",
    "DEFAULT_SEARCH",
    "VALID_SEARCH_STRATEGIES",
    "ProjectConfig",
    "load_config",
    "discover_config",
    "resolve_check_options",
]
