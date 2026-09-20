"""
Tests for Validol validation: is_int, is_float, is_decimal, is_bool, is_date
Copyright (C) 2023 Azist, MIT License
"""

import pytest
from datetime import date, datetime
from decimal import Decimal

from azos.exceptions import Validol, ValidolBatchError, ValidolError


class Stub:
    """Simple attribute bag for testing"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ───────────────────────── is_int ─────────────────────────

class TestIsInt:

    def test_valid_int(self):
        s = Stub(age=25)
        Validol(s).is_int("age", required=True, min=0, max=200).throw()

    def test_valid_int_no_bounds(self):
        s = Stub(age=-999)
        Validol(s).is_int("age", required=True).throw()

    def test_valid_int_at_min_boundary(self):
        s = Stub(val=0)
        Validol(s).is_int("val", required=True, min=0, max=100).throw()

    def test_valid_int_at_max_boundary(self):
        s = Stub(val=100)
        Validol(s).is_int("val", required=True, min=0, max=100).throw()

    def test_none_optional_passes(self):
        s = Stub(age=None)
        Validol(s).is_int("age", required=False).throw()

    def test_missing_attr_optional_passes(self):
        s = Stub()
        Validol(s).is_int("age", required=False).throw()

    def test_none_required_fails(self):
        s = Stub(age=None)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_int("age", required=True).throw()
        assert exc_info.value.errors[0].field == "age" # type: ignore
        assert "required" in str(exc_info.value.errors[0])

    def test_missing_attr_required_fails(self):
        s = Stub()
        with pytest.raises(ValidolBatchError):
            Validol(s).is_int("age", required=True).throw()

    def test_bool_rejected(self):
        s = Stub(flag=True)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_int("flag", required=True).throw()
        assert "int value" in str(exc_info.value.errors[0])

    def test_float_rejected(self):
        s = Stub(val=3.14)
        with pytest.raises(ValidolBatchError):
            Validol(s).is_int("val", required=True).throw()

    def test_string_rejected(self):
        s = Stub(val="42")
        with pytest.raises(ValidolBatchError):
            Validol(s).is_int("val", required=True).throw()

    def test_below_min(self):
        s = Stub(val=-1)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_int("val", required=True, min=0).throw()
        assert ">= 0" in str(exc_info.value.errors[0])

    def test_above_max(self):
        s = Stub(val=101)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_int("val", required=True, max=100).throw()
        assert "<= 100" in str(exc_info.value.errors[0])

    def test_zero_is_valid(self):
        s = Stub(val=0)
        Validol(s).is_int("val", required=True).throw()

    def test_negative_is_valid(self):
        s = Stub(val=-42)
        Validol(s).is_int("val", required=True, min=-100, max=100).throw()


# ───────────────────────── is_float ─────────────────────────

class TestIsFloat:

    def test_valid_float(self):
        s = Stub(price=19.99)
        Validol(s).is_float("price", required=True, min=0.0, max=1000.0).throw()

    def test_valid_float_no_bounds(self):
        s = Stub(price=-0.001)
        Validol(s).is_float("price", required=True).throw()

    def test_int_accepted_as_float(self):
        s = Stub(price=10)
        Validol(s).is_float("price", required=True, min=0.0, max=100.0).throw()

    def test_none_optional_passes(self):
        s = Stub(price=None)
        Validol(s).is_float("price", required=False).throw()

    def test_missing_attr_optional_passes(self):
        s = Stub()
        Validol(s).is_float("price", required=False).throw()

    def test_none_required_fails(self):
        s = Stub(price=None)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_float("price", required=True).throw()
        assert "required" in str(exc_info.value.errors[0])

    def test_bool_rejected(self):
        s = Stub(val=False)
        with pytest.raises(ValidolBatchError):
            Validol(s).is_float("val", required=True).throw()

    def test_string_rejected(self):
        s = Stub(val="3.14")
        with pytest.raises(ValidolBatchError):
            Validol(s).is_float("val", required=True).throw()

    def test_below_min(self):
        s = Stub(val=-0.01)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_float("val", required=True, min=0.0).throw()
        assert ">= 0.0" in str(exc_info.value.errors[0])

    def test_above_max(self):
        s = Stub(val=100.1)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_float("val", required=True, max=100.0).throw()
        assert "<= 100.0" in str(exc_info.value.errors[0])

    def test_at_min_boundary(self):
        s = Stub(val=0.0)
        Validol(s).is_float("val", required=True, min=0.0, max=100.0).throw()

    def test_at_max_boundary(self):
        s = Stub(val=100.0)
        Validol(s).is_float("val", required=True, min=0.0, max=100.0).throw()


# ───────────────────────── is_decimal ─────────────────────────

class TestIsDecimal:

    def test_valid_decimal(self):
        s = Stub(amount=Decimal("19.99"))
        Validol(s).is_decimal("amount", required=True, min=0, max=1000).throw()

    def test_valid_decimal_no_bounds(self):
        s = Stub(amount=Decimal("-999.123"))
        Validol(s).is_decimal("amount", required=True).throw()

    def test_int_coerced_to_decimal(self):
        s = Stub(amount=42)
        Validol(s).is_decimal("amount", required=True, min=0, max=100).throw()

    def test_float_coerced_to_decimal(self):
        s = Stub(amount=3.14)
        Validol(s).is_decimal("amount", required=True, min=0.0, max=100.0).throw()

    def test_numeric_string_coerced_to_decimal(self):
        s = Stub(amount="99.95")
        Validol(s).is_decimal("amount", required=True, min=0, max=100).throw()

    def test_none_optional_passes(self):
        s = Stub(amount=None)
        Validol(s).is_decimal("amount", required=False).throw()

    def test_missing_attr_optional_passes(self):
        s = Stub()
        Validol(s).is_decimal("amount", required=False).throw()

    def test_none_required_fails(self):
        s = Stub(amount=None)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_decimal("amount", required=True).throw()
        assert "required" in str(exc_info.value.errors[0])

    def test_bool_rejected(self):
        s = Stub(val=True)
        with pytest.raises(ValidolBatchError):
            Validol(s).is_decimal("val", required=True).throw()

    def test_non_numeric_string_rejected(self):
        s = Stub(val="abc")
        with pytest.raises(ValidolBatchError):
            Validol(s).is_decimal("val", required=True).throw()

    def test_list_rejected(self):
        s = Stub(val=[1, 2])
        with pytest.raises(ValidolBatchError):
            Validol(s).is_decimal("val", required=True).throw()

    def test_below_min(self):
        s = Stub(val=Decimal("-0.01"))
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_decimal("val", required=True, min=0).throw()
        assert ">= 0" in str(exc_info.value.errors[0])

    def test_above_max(self):
        s = Stub(val=Decimal("100.01"))
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_decimal("val", required=True, max=100).throw()
        assert "<= 100" in str(exc_info.value.errors[0])

    def test_at_min_boundary(self):
        s = Stub(val=Decimal("0"))
        Validol(s).is_decimal("val", required=True, min=0, max=100).throw()

    def test_at_max_boundary(self):
        s = Stub(val=Decimal("100"))
        Validol(s).is_decimal("val", required=True, min=0, max=100).throw()


# ───────────────────────── is_bool ─────────────────────────

class TestIsBool:

    def test_valid_true(self):
        s = Stub(active=True)
        Validol(s).is_bool("active", required=True).throw()

    def test_valid_false(self):
        s = Stub(active=False)
        Validol(s).is_bool("active", required=True).throw()

    def test_none_optional_passes(self):
        s = Stub(active=None)
        Validol(s).is_bool("active", required=False).throw()

    def test_missing_attr_optional_passes(self):
        s = Stub()
        Validol(s).is_bool("active", required=False).throw()

    def test_none_required_fails(self):
        s = Stub(active=None)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_bool("active", required=True).throw()
        assert "required" in str(exc_info.value.errors[0])

    def test_missing_attr_required_fails(self):
        s = Stub()
        with pytest.raises(ValidolBatchError):
            Validol(s).is_bool("active", required=True).throw()

    def test_int_rejected(self):
        s = Stub(active=1)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_bool("active", required=True).throw()
        assert "bool value" in str(exc_info.value.errors[0])

    def test_zero_rejected(self):
        s = Stub(active=0)
        with pytest.raises(ValidolBatchError):
            Validol(s).is_bool("active", required=True).throw()

    def test_string_rejected(self):
        s = Stub(active="true")
        with pytest.raises(ValidolBatchError):
            Validol(s).is_bool("active", required=True).throw()

    def test_none_string_rejected(self):
        s = Stub(active="")
        with pytest.raises(ValidolBatchError):
            Validol(s).is_bool("active", required=True).throw()


# ───────────────────────── is_date ─────────────────────────

class TestIsDate:

    def test_valid_date(self):
        s = Stub(dob=date(1990, 5, 15))
        Validol(s).is_date("dob", required=True).throw()

    def test_valid_datetime(self):
        s = Stub(created=datetime(2024, 1, 1, 12, 30))
        Validol(s).is_date("created", required=True).throw()

    def test_valid_date_with_bounds(self):
        s = Stub(dob=date(2000, 6, 15))
        Validol(s).is_date("dob", required=True,
                           min=date(1900, 1, 1),
                           max=date(2025, 12, 31)).throw()

    def test_valid_datetime_with_date_bounds(self):
        s = Stub(ts=datetime(2024, 6, 15, 10, 0))
        Validol(s).is_date("ts", required=True,
                           min=date(2024, 1, 1),
                           max=date(2024, 12, 31)).throw()

    def test_at_min_boundary(self):
        s = Stub(d=date(2024, 1, 1))
        Validol(s).is_date("d", required=True,
                           min=date(2024, 1, 1),
                           max=date(2024, 12, 31)).throw()

    def test_at_max_boundary(self):
        s = Stub(d=date(2024, 12, 31))
        Validol(s).is_date("d", required=True,
                           min=date(2024, 1, 1),
                           max=date(2024, 12, 31)).throw()

    def test_none_optional_passes(self):
        s = Stub(dob=None)
        Validol(s).is_date("dob", required=False).throw()

    def test_missing_attr_optional_passes(self):
        s = Stub()
        Validol(s).is_date("dob", required=False).throw()

    def test_none_required_fails(self):
        s = Stub(dob=None)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_date("dob", required=True).throw()
        assert "required" in str(exc_info.value.errors[0])

    def test_missing_attr_required_fails(self):
        s = Stub()
        with pytest.raises(ValidolBatchError):
            Validol(s).is_date("dob", required=True).throw()

    def test_string_rejected(self):
        s = Stub(dob="2024-01-01")
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_date("dob", required=True).throw()
        assert "date or datetime" in str(exc_info.value.errors[0])

    def test_int_rejected(self):
        s = Stub(dob=20240101)
        with pytest.raises(ValidolBatchError):
            Validol(s).is_date("dob", required=True).throw()

    def test_float_rejected(self):
        s = Stub(dob=1719792000.0)
        with pytest.raises(ValidolBatchError):
            Validol(s).is_date("dob", required=True).throw()

    def test_below_min(self):
        s = Stub(d=date(1899, 12, 31))
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_date("d", required=True, min=date(1900, 1, 1)).throw()
        assert ">= 1900-01-01" in str(exc_info.value.errors[0])

    def test_above_max(self):
        s = Stub(d=date(2026, 1, 1))
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).is_date("d", required=True, max=date(2025, 12, 31)).throw()
        assert "<= 2025-12-31" in str(exc_info.value.errors[0])

    def test_datetime_below_min_date(self):
        s = Stub(ts=datetime(2023, 12, 31, 23, 59))
        with pytest.raises(ValidolBatchError):
            Validol(s).is_date("ts", required=True, min=date(2024, 1, 1)).throw()

    def test_datetime_above_max_date(self):
        s = Stub(ts=datetime(2025, 1, 1, 0, 0))
        with pytest.raises(ValidolBatchError):
            Validol(s).is_date("ts", required=True, max=date(2024, 12, 31)).throw()

    def test_min_only(self):
        s = Stub(d=date(2024, 6, 1))
        Validol(s).is_date("d", required=True, min=date(2024, 1, 1)).throw()

    def test_max_only(self):
        s = Stub(d=date(2024, 6, 1))
        Validol(s).is_date("d", required=True, max=date(2025, 1, 1)).throw()


# ───────────────────────── Chaining ─────────────────────────

class TestNumericChaining:

    def test_chain_all_numeric_types(self):
        s = Stub(count=5, ratio=0.75, price=Decimal("9.99"))
        Validol(s) \
            .is_int("count", required=True, min=1, max=100) \
            .is_float("ratio", required=True, min=0.0, max=1.0) \
            .is_decimal("price", required=True, min=0, max=1000) \
            .throw()

    def test_chain_mixed_with_string(self):
        s = Stub(name="Widget", count=5, price=Decimal("9.99"), active=True)
        Validol(s) \
            .is_str("name", required=True, min=1, max=50) \
            .is_int("count", required=True, min=1, max=100) \
            .is_decimal("price", required=True, min=0, max=1000) \
            .is_bool("active", required=True) \
            .throw()

    def test_multiple_errors_collected(self):
        s = Stub(count=-1, ratio=2.0, price=Decimal("9999"))
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s) \
                .is_int("count", required=True, min=0) \
                .is_float("ratio", required=True, max=1.0) \
                .is_decimal("price", required=True, max=100) \
                .throw()
        assert len(exc_info.value.errors) == 3


# ───────────────────────── that (custom predicate) ─────────────────────────

class TestThat:

    def test_that_no_error_passes(self):
        """Predicate that emits nothing — validation passes"""
        s = Stub(x=5)
        Validol(s).that(lambda v: None).throw()

    def test_that_emits_error(self):
        """Predicate emits a custom error — throw raises"""
        s = Stub(x=4)
        with pytest.raises(ValidolBatchError) as exc_info:
            (Validol(s)
                .that(lambda v: v.emit(ValidolError("S", "x", "X must be odd")) if v.target.x % 2 == 0 else None)  # type: ignore
                .throw())
        assert len(exc_info.value.errors) == 1
        assert exc_info.value.errors[0].field == "x" # type: ignore
        assert "odd" in str(exc_info.value.errors[0])

    def test_that_chains_with_builtins(self):
        """that() chains seamlessly with is_str / is_int etc."""
        s = Stub(name="ok", x=10)
        Validol(s) \
            .is_str("name", required=True, min=1, max=50) \
            .that(lambda v: None) \
            .is_int("x", required=True, min=0) \
            .throw()

    def test_that_collects_errors_alongside_builtins(self):
        """Errors from that() accumulate with built-in validator errors"""
        s = Stub(name="", x=10)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s) \
                .is_str("name", required=True, min=1, max=50) \
                .that(lambda v: v.emit(ValidolError("S", "x", "custom fail"))).throw() # type: ignore
        assert len(exc_info.value.errors) == 2

    def test_that_receives_validol_instance(self):
        """Predicate receives the Validol instance with access to target"""
        s = Stub(a=1, b=2)
        received = []
        def check(v):
            received.append(v)
            if v.target.a + v.target.b != 3:
                v.emit(ValidolError("S", "sum", "a+b must be 3"))
        Validol(s).that(check).throw()
        assert len(received) == 1
        assert received[0].target is s

    def test_that_multiple_calls(self):
        """Multiple that() calls each invoke their predicate"""
        s = Stub(x=0)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s) \
                .that(lambda v: v.emit(ValidolError("S", "x", "err1"))).that(lambda v: v.emit(ValidolError("S", "x", "err2"))).throw() # type: ignore
        assert len(exc_info.value.errors) == 2


# ───────────────────────── is_true (predicate-based) ─────────────────────────

class TestIsTrue:

    def test_true_passes(self):
        """Predicate returns True — no error emitted"""
        s = Stub(age=21)
        Validol(s).test("Must be adult", lambda v: v.target.age >= 18).throw()

    def test_false_emits_error(self):
        """Predicate returns False — auto-emits error with field='*'"""
        s = Stub(age=10)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).test("Must be adult", lambda v: v.target.age >= 18).throw()
        assert len(exc_info.value.errors) == 1
        assert exc_info.value.errors[0].field == "*" # type: ignore
        assert "Must be adult" in str(exc_info.value.errors[0])

    def test_chains_with_builtins(self):
        """is_true() chains with is_str / is_int etc."""
        s = Stub(name="Alice", age=25, score=10)
        Validol(s) \
            .is_str("name", required=True, min=1, max=50) \
            .is_int("age", required=True, min=0) \
            .test("Score must be positive", lambda v: v.target.score > 0) \
            .throw()

    def test_collects_errors_alongside_builtins(self):
        """is_true error accumulates with built-in validator errors"""
        s = Stub(name="", score=-1)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s) \
                .is_str("name", required=True, min=1, max=50) \
                .test("Score must be positive", lambda v: v.target.score > 0) \
                .throw()
        assert len(exc_info.value.errors) == 2

    def test_multiple_is_true_calls(self):
        """Multiple is_true() calls each evaluate independently"""
        s = Stub(a=0, b=-1)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s) \
                .test("a must be positive", lambda v: v.target.a > 0) \
                .test("b must be positive", lambda v: v.target.b > 0) \
                .throw()
        assert len(exc_info.value.errors) == 2
        assert all(e.field == "*" for e in exc_info.value.errors) # type: ignore

    def test_schema_auto_populated(self):
        """Schema in the emitted error comes from target class name"""
        s = Stub(x=0)
        with pytest.raises(ValidolBatchError) as exc_info:
            Validol(s).test("bad", lambda v: False).throw()
        assert exc_info.value.errors[0].schema == "Stub" # type: ignore
        assert exc_info.value.errors[0].field == "*" # type: ignore

    def test_chains_with_that(self):
        """is_true() and that() can be mixed in the same chain"""
        s = Stub(x=5, y=10)
        Validol(s) \
            .test("x must be odd", lambda v: v.target.x % 2 != 0) \
            .that(lambda v: None) \
            .throw()
