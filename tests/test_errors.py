"""Tests for typed SpecError / ModelError exceptions."""

from __future__ import annotations

import pytest

from llm_formal_verify import (
    ModelError,
    SpecError,
    SpecBuilder,
    bounded_model_check,
    eq,
    lit,
    var,
)


def test_spec_error_is_value_error():
    """Existing ``except ValueError`` handlers must keep working."""
    assert issubclass(SpecError, ValueError)
    assert issubclass(ModelError, ValueError)


def test_empty_var_name_raises_spec_error():
    with pytest.raises(SpecError, match="StateVar.name must be non-empty"):
        SpecBuilder("X").var("", [1, 2]).build()


def test_empty_domain_raises_spec_error():
    with pytest.raises(SpecError, match="needs a non-empty domain"):
        SpecBuilder("X").var("x", []).build()


def test_int_var_inverted_range_raises_spec_error():
    with pytest.raises(SpecError, match="high 1 < low 5"):
        SpecBuilder("X").int_var("n", 5, 1)


def test_enum_var_empty_raises_spec_error():
    with pytest.raises(SpecError, match="needs at least one value"):
        SpecBuilder("X").enum_var("e", [])


def test_unknown_var_in_init_raises_spec_error():
    b = SpecBuilder("X")
    b.var("a", [0, 1])
    b.init(eq(var("missing"), lit(0)))
    with pytest.raises(SpecError, match="unknown variables"):
        b.build()


def test_unknown_var_in_action_raises_spec_error():
    b = SpecBuilder("X")
    b.var("a", [0, 1])
    b.init(eq(var("a"), lit(0)))
    b.action("step", guard=eq(var("ghost"), lit(1)), assign={"a": 1})
    with pytest.raises(SpecError, match="unknown variables"):
        b.build()


def test_action_assigns_unknown_var_raises_spec_error():
    b = SpecBuilder("X")
    b.var("a", [0, 1])
    b.init(eq(var("a"), lit(0)))
    b.action("step", guard=lit(True), assign={"ghost": 1})
    with pytest.raises(SpecError, match="assigns unknown variable"):
        b.build()


def test_negative_bound_raises_model_error():
    b = SpecBuilder("Tiny")
    b.var("x", [0, 1])
    b.init(eq(var("x"), lit(0)))
    spec = b.build()
    with pytest.raises(ModelError, match="bound must be >= 0"):
        bounded_model_check(spec, bound=-1)


def test_out_of_domain_successor_raises_model_error():
    """An action that steps outside a declared domain is a model error."""
    b = SpecBuilder("Overflow")
    b.var("n", [0, 1])
    b.init(eq(var("n"), lit(0)))
    # Assign a literal that is not in the domain.
    b.action("boom", guard=lit(True), assign={"n": 99})
    spec = b.build()
    with pytest.raises(ModelError, match="out-of-domain value"):
        bounded_model_check(spec, bound=1)
