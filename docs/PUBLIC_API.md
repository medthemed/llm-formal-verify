# Public API and error handling

This page documents the 0.x compatibility promise and the typed exceptions
you should catch.

## Compatibility promise

Everything re-exported from `llm_formal_verify` (see `__all__`) is public
API. Within the 0.x series:

- Existing names and their call signatures stay stable.
- New names may be added.
- Anything not in `__all__` is internal and may change without notice.

The freeze is enforced by `tests/test_public_api.py`. If you need a name
that is not exported, open an issue rather than reaching into private
modules.

### Frozen entry points

| Symbol | Notes |
| --- | --- |
| `bounded_model_check(spec, bound=8)` | Returns `BMCResult`. |
| `SpecBuilder` fluent methods | `var`, `bool_var`, `int_var`, `enum_var`, `init`, `init_eq`, `action`, `invariant`, `safety`, `liveness`, `build`. |
| `BMCResult` fields | `spec_name`, `bound`, `reachable_states`, `transitions_explored`, `results`. |
| `BMCResult` helpers | `ok`, `failures`, `format()`, `to_dict()`, `to_json()`. |

## Typed exceptions

Two exception types, both subclasses of `ValueError` so existing
`except ValueError` handlers keep working:

### `SpecError`

The specification itself is malformed. Raised by:

- IR constructors (`StateVar`, `Action`, `Check`, `Spec`)
- `Spec.validate()` — unknown variables, duplicate names, bad check kinds
- Builder helpers (`int_var` with inverted range, empty `enum_var`)
- `eval_expr` for unknown operators

### `ModelError`

The model checker cannot proceed. Raised by:

- `bounded_model_check` with a negative bound
- An action that produces a successor value outside a declared domain

### Example

```python
from llm_formal_verify import SpecError, ModelError, bounded_model_check

try:
    result = bounded_model_check(spec, bound=10)
except SpecError as exc:
    print(f"spec is broken: {exc}")
except ModelError as exc:
    print(f"cannot explore: {exc}")
```

The CLI maps `SpecError` / `ModelError` to exit code 2 (usage / internal
error), distinct from exit code 1 (a check failed).
