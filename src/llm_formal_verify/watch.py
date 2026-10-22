"""Watch mode: re-check specs whenever their files change.

Polling-based, on purpose: a fingerprint of (mtime, size) per file is
cheap, portable, and needs no OS-specific file-watcher dependency —
the same trade-off the CLI takes elsewhere (stdlib only).

``watch_specs`` runs the batch check once, then (unless ``once``) keeps
polling and re-runs the whole batch whenever any watched file's
fingerprint changes. A file that does not exist yet fingerprints as
``None``, so creating it later also triggers a re-check. Ctrl-C exits
cleanly, returning the most recent run's exit code.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Sequence

from .batch import BatchCheckResult, batch_exit_code, check_many, expand_spec_paths
from .errors import SpecError

#: Default seconds between polls.
DEFAULT_INTERVAL = 2.0


def _fingerprint(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _snapshot(paths: Sequence[Path]) -> dict[str, tuple[int, int] | None]:
    return {str(p): _fingerprint(p) for p in paths}


def watch_specs(
    paths: Sequence[str | Path],
    *,
    bound: int = 8,
    search: str = "bfs",
    interval: float = DEFAULT_INTERVAL,
    once: bool = False,
    emit: Callable[[BatchCheckResult], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Check ``paths`` now, then re-check when any file changes.

    Parameters
    ----------
    bound, search:
        Passed through to :func:`~llm_formal_verify.batch.check_many`.
    interval:
        Poll interval in seconds (must be > 0).
    once:
        Run a single pass and return — the CI-friendly form.
    emit:
        Called with each :class:`BatchCheckResult`. Defaults to printing
        the aggregate table.
    sleep:
        Injectable sleep function (tests pass a fake to drive the loop
        deterministically).

    Returns the exit code of the most recent run: ``0`` all pass,
    ``1`` any check failed, ``2`` nothing usable was checked.
    """
    if interval <= 0:
        raise SpecError(f"watch interval must be > 0 seconds, got {interval}")
    resolved = expand_spec_paths(paths)
    if not resolved:
        raise SpecError("no spec files found to watch")

    if emit is None:

        def emit(batch: BatchCheckResult) -> None:  # noqa: F811
            print(batch.format_table(), end="")

    def run_once() -> int:
        batch = check_many(resolved, bound=bound, search=search, expand=False)
        emit(batch)
        return batch_exit_code(batch)

    code = run_once()
    if once:
        return code

    snapshot = _snapshot(resolved)
    try:
        while True:
            sleep(interval)
            current = _snapshot(resolved)
            if current != snapshot:
                snapshot = current
                code = run_once()
    except KeyboardInterrupt:
        return code


__all__ = ["DEFAULT_INTERVAL", "watch_specs"]
