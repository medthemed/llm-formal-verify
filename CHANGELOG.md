# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-11-16

### Added
- Published Draft 2020-12 JSON Schemas shipped with the package:
  `bmc-report`, `batch-report`, `tla-module`, and `spec`.
- Public exports: `load_schema`, `schema_path`, `KNOWN_SCHEMAS`,
  `BMC_REPORT`, `BATCH_REPORT`, `TLA_MODULE`, `SPEC`.
- `lfv tla --format json` / `--json` emits `{"module": "..."}`.
- `docs/JSON_SCHEMA.md`: interop contract, stability rules, exit codes.

### Changed
- `lfv check --json` is now documented as an alias of `--format json` and
  pinned to `bmc-report` / `batch-report` schemas in tests.

## [0.4.0] - 2026-11-02

### Added
- Batch checking: `lfv check` accepts multiple spec paths and directories of
  `*.json`. Directories expand to their immediate children (sorted).
- Aggregate pass/fail table for multi-spec runs (`SPEC / STATUS / FAILURES / STATES`
  plus a summary line).
- New public exports: `check_many`, `expand_spec_paths`, `BatchCheckResult`,
  `SpecOutcome`.
- `lfv check --format text|json` ( `--json` remains an alias for `--format json` ).

### Changed
- Single-file `lfv check` output is unchanged (verbose report or per-spec JSON).
- Multi-spec exit codes: `0` all pass, `1` any check failed, `2` nothing usable
  was checked (empty expansion / total load failure).

## [0.3.0] - 2026-10-16

### Added
- Project config: `.lfv.json` / `lfv.config.json` sets default `bound` and `search`.
  Lookup order: CLI flag > `.lfv.json` > `lfv.config.json` > built-in defaults.
- `search` strategy on `bounded_model_check` (`bfs` shortest trace, `dfs` depth-first).
  `BMCResult` now reports which strategy was used.
- `lfv init [DIR]` scaffolds a starter `spec.json` and `.lfv.json` so the first
  `lfv check` works immediately.
- New public exports: `ProjectConfig`, `load_config`, `discover_config`,
  `resolve_check_options`, `write_starter`.

### Changed
- `lfv check --bound` default is now resolved from project config (still 8 when absent).
- `bounded_model_check` gained a keyword-only `search` parameter (default `"bfs"`).

## [0.2.0] - 2026-10-02

### Added
- Typed exceptions: `SpecError` for malformed specs, `ModelError` for BMC runtime problems.
  Both subclass `ValueError` so existing handlers keep working through the 0.x line.
- Public API freeze: `__all__` is the compatibility contract; `test_public_api.py`
  pins `SpecBuilder` fluent methods and `bounded_model_check` signatures.
- Integration tests that load `examples/safe_transfer.json` and
  `examples/unsafe_transfer.json` through the public API only.

### Changed
- IR validation, builder helpers, and expression eval now raise `SpecError`.
- BMC raises `ModelError` for negative bounds and out-of-domain successors.
- CLI catches the typed errors explicitly.

### Docs
- `docs/PUBLIC_API.md`: frozen entry points, exception taxonomy, CLI exit codes.

## [0.1.1] - 2026-09-17

### Added
- `lfv check --json` prints a structured BMC report with counterexample paths.
- `to_dict()` / `to_json()` helpers on `BMCResult`, `CheckResult`, `Counterexample`, and `Step`.

### Docs
- Worked walkthrough of reading and fixing a counterexample (`docs/COUNTEREXAMPLE.md`).

## [0.1.0] - 2026-03-16

### Added
- Intermediate representation (IR) for predicates, state variables, transitions, and invariants.
- Python-embedded builder API (`SpecBuilder`) for composing specs programmatically.
- JSON schema for serialized specs.
- TLA+-like text emitter (`lfv tla`).
- Bounded model checker with counterexample traces (`lfv check`).
- CLI entry point and two worked examples (safe / unsafe transfer).
- Pytest suite covering IR, builder, TLA export, and BMC behavior.
