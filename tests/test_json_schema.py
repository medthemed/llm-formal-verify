"""Interop tests: published JSON Schemas and `--format json` contracts.

A tiny Draft-2020-12 subset validator is used so the suite stays
dependency-free while still pinning required keys / types / enums.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llm_formal_verify.cli import main
from llm_formal_verify.schemas import (
    BATCH_REPORT,
    BMC_REPORT,
    KNOWN_SCHEMAS,
    SPEC,
    TLA_MODULE,
    load_schema,
    schema_path,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SAFE = EXAMPLES / "safe_transfer.json"
UNSAFE = EXAMPLES / "unsafe_transfer.json"


def _resolve(
    schema: dict[str, Any], root: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "$ref" not in schema:
        return schema, root
    ref = schema["$ref"]
    if ref.startswith("#/"):
        node: Any = root
        for part in ref[2:].split("/"):
            node = node[part]
        return node, root
    # sibling schema file — switch the resolution root
    name = ref.removesuffix(".schema.json")
    loaded = load_schema(name)
    return loaded, loaded


def _type_ok(value: Any, expected: str | list[str]) -> bool:
    names = [expected] if isinstance(expected, str) else expected
    for name in names:
        if name == "string" and isinstance(value, str):
            return True
        if name == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if name == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if name == "boolean" and isinstance(value, bool):
            return True
        if name == "array" and isinstance(value, list):
            return True
        if name == "object" and isinstance(value, dict):
            return True
        if name == "null" and value is None:
            return True
    return False


def validate(instance: Any, schema: dict[str, Any], *, root: dict[str, Any] | None = None) -> None:
    """Validate ``instance`` against a JSON Schema subset. Raises AssertionError."""
    root = schema if root is None else root
    schema, root = _resolve(schema, root)

    if "enum" in schema:
        assert instance in schema["enum"], f"{instance!r} not in {schema['enum']}"

    expected = schema.get("type")
    if expected is not None:
        assert _type_ok(instance, expected), f"{instance!r} is not type {expected}"

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            assert key in instance, f"missing required key {key!r} in {instance!r}"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(props)
            # allow sibling keywords that are not property names
            extra -= {"$schema", "$id", "title", "description", "$defs"}
            assert not extra, f"unexpected keys {sorted(extra)}"
        for key, value in instance.items():
            if key in props:
                validate(value, props[key], root=root)

    if isinstance(instance, list) and "items" in schema:
        for item in instance:
            validate(item, schema["items"], root=root)

    if isinstance(instance, str):
        if "minLength" in schema:
            assert len(instance) >= schema["minLength"]
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema:
            assert instance >= schema["minimum"]


def test_known_schemas_present():
    assert set(KNOWN_SCHEMAS) == {BMC_REPORT, BATCH_REPORT, TLA_MODULE, SPEC}
    for name in KNOWN_SCHEMAS:
        path = schema_path(name)
        assert path.is_file(), path
        data = load_schema(name)
        assert data["$schema"].startswith("https://json-schema.org/draft/2020-12/")
        assert data["$id"]


def test_schema_path_rejects_unknown():
    with pytest.raises(KeyError):
        schema_path("nope")


def test_bmc_report_schema_matches_cli_json(capsys):
    code = main(["check", str(SAFE), "--bound", "6", "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(payload, load_schema(BMC_REPORT))


def test_bmc_report_schema_matches_failing_spec(capsys):
    code = main(["check", str(UNSAFE), "--bound", "6", "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    validate(payload, load_schema(BMC_REPORT))
    failed = next(c for c in payload["checks"] if c["status"] == "failed")
    assert "counterexample" in failed


def test_batch_report_schema_matches_cli_json(capsys):
    code = main(["check", str(SAFE), str(UNSAFE), "--bound", "6", "--format", "json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    validate(payload, load_schema(BATCH_REPORT))


def test_tla_module_schema_matches_cli_json(capsys):
    code = main(["tla", str(SAFE), "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(payload, load_schema(TLA_MODULE))
    assert "MODULE SafeTransfer" in payload["module"]


def test_tla_json_flag_is_alias(capsys):
    code = main(["tla", str(SAFE), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"module"}


def test_spec_schema_matches_example():
    data = json.loads(SAFE.read_text(encoding="utf-8"))
    validate(data, load_schema(SPEC))


def test_spec_schema_rejects_missing_name():
    data = json.loads(SAFE.read_text(encoding="utf-8"))
    del data["name"]
    with pytest.raises(AssertionError):
        validate(data, load_schema(SPEC))
