# JSON Schema interop

Published machine-readable contracts for `llm-formal-verify`. All schemas
are Draft 2020-12 and ship inside the package:

```
llm_formal_verify/schemas/*.schema.json
```

## Loading a schema

```python
from llm_formal_verify import load_schema, schema_path, BMC_REPORT

schema = load_schema(BMC_REPORT)   # dict
path = schema_path(BMC_REPORT)     # Path to the .schema.json file
```

Or from the CLI help text / repo: `src/llm_formal_verify/schemas/`.

## Catalog

| Name | CLI / API | `$id` |
| --- | --- | --- |
| `bmc-report` | `lfv check SPEC --format json` (single file) | `.../bmc-report.schema.json` |
| `batch-report` | `lfv check SPEC... --format json` (multi) | `.../batch-report.schema.json` |
| `tla-module` | `lfv tla SPEC --format json` | `.../tla-module.schema.json` |
| `spec` | input `SPEC.json` for `check` / `tla` | `.../spec.schema.json` |

`--json` is an alias for `--format json` on both `check` and `tla`.

## Stability

Within the 0.x series:

- Required properties of `bmc-report` will not be removed.
- New optional properties may be added.
- Enum values for `status` / `search` / `kind` may gain members; consumers
  should treat unknown members as opaque.
- `batch-report.results[].result` embeds a full `bmc-report` when that file
  checked successfully.

## Exit codes (unchanged)

| Code | Meaning |
| --- | --- |
| 0 | all checks pass |
| 1 | at least one check failed |
| 2 | usage / load / model error |

## Example

```bash
lfv check examples/safe_transfer.json --bound 6 --format json > report.json
# validate report.json against schemas/bmc-report.schema.json
```
