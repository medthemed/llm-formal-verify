"""Typed exceptions for llm-formal-verify.

Two families:

- :class:`SpecError`  -- the specification itself is malformed (unknown
  variables, duplicate names, empty domains, bad check kinds, …).
- :class:`ModelError` -- the model checker hit a runtime problem (negative
  bound, an action produced an out-of-domain successor value, …).

Both inherit from :class:`ValueError` so existing ``except ValueError``
call sites keep working through the 0.x line.
"""

from __future__ import annotations


class SpecError(ValueError):
    """A specification is internally inconsistent or malformed.

    Raised by IR constructors, :meth:`Spec.validate`, and the builder
    helpers when the caller asks for something that cannot form a legal
    finite-state model.
    """


class ModelError(ValueError):
    """The bounded model checker cannot proceed.

    Raised for invalid exploration parameters (e.g. a negative bound) and
    for actions that step outside a declared finite domain.
    """


__all__ = ["SpecError", "ModelError"]
