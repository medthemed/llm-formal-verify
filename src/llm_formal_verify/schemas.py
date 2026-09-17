"""Access to the published JSON Schemas for machine-readable output.

Schemas live next to the package (``llm_formal_verify/schemas/*.schema.json``)
so consumers can vendor them or point a validator at a stable path. Loading is
stdlib-only; no ``jsonschema`` dependency is required to *read* a schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

#: Canonical schema names shipped with the package.
BMC_REPORT = "bmc-report"
BATCH_REPORT = "batch-report"
TLA_MODULE = "tla-module"
SPEC = "spec"

KNOWN_SCHEMAS: tuple[str, ...] = (BMC_REPORT, BATCH_REPORT, TLA_MODULE, SPEC)


def schema_path(name: str) -> Path:
    """Return the filesystem path of a published schema file.

    ``name`` may be ``"bmc-report"`` or ``"bmc-report.schema.json"``.
    Raises :class:`KeyError` for unknown names.
    """
    stem = name.removesuffix(".schema.json")
    if stem not in KNOWN_SCHEMAS:
        raise KeyError(
            f"unknown schema {name!r}; expected one of {list(KNOWN_SCHEMAS)}"
        )
    return SCHEMA_DIR / f"{stem}.schema.json"


def load_schema(name: str) -> dict[str, Any]:
    """Load a published schema as a Python dict."""
    path = schema_path(name)
    return json.loads(path.read_text(encoding="utf-8"))


def schema_ids() -> dict[str, str]:
    """Map schema name -> ``$id`` URI (stable interop identifier)."""
    return {name: str(load_schema(name).get("$id", "")) for name in KNOWN_SCHEMAS}
