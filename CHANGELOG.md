# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
