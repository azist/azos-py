"""
Provides custom exceptions and validation boilerplate (Validol)

Copyright (C) 2023 Azist, MIT License
"""

from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class AzosError(Exception):
    """Exception thrown by Azos interop code

    Attributes:
        topic -- exception topic string
        frm -- string specifier of the "from" place in code/system/component
        src -- error/source code (int)
        message -- explanation of the error
    """

    def __init__(self, message: str ="Azos unspecified error", topic: str = "azos", frm: str = "", src: int = 0):
        self.topic = topic
        self.frm = frm
        self.src = src
        self.message = message
        super().__init__(self.message)


class ValidolError(AzosError):
    """Exception thrown by Validol validation logic for a single field error.

    Attributes:
        field -- field name that failed validation
        schema -- validation schema name (stored in AzosError.frm)
    """

    def __init__(self, schema: str, field: str, message: str, src: int = 0):
        self.field = field
        super().__init__(message=message, topic="validol", frm=schema, src=src)

    @property
    def schema(self) -> str:
        """Validation schema name (alias for `frm`)"""
        return self.frm

    def __str__(self) -> str:
        return f"[{self.frm}.{self.field}] {self.message}"

    def __repr__(self) -> str:
        return f"ValidolError(schema={self.frm!r}, field={self.field!r}, message={self.message!r}, src={self.src})"


class ValidolBatchError(ExceptionGroup[ValidolError], AzosError):
    """Aggregate validation exception containing multiple `ValidolError` instances.

    Follows the Python 3.11+ `ExceptionGroup` (PEP 654) convention for
    batch/aggregate exceptions. This enables the `except*` syntax for
    structured matching of individual validation errors.

    Usage with `except*`::

        try:
            validol.throw()
        except* ValidolError as eg:
            for err in eg.exceptions:
                print(err.field, err.message)

    Attributes:
        schema -- validation schema name (stored in AzosError.frm)
        errors -- tuple of contained `ValidolError` instances
    """

    # ExceptionGroup.__new__ requires (message, exceptions) positional args.
    # We override __new__ because ExceptionGroup is immutable after creation.
    def __new__(cls, schema: str, errors: list[ValidolError], src: int = 0):
        msg = f"Validation of `{schema}` failed with {len(errors)} error(s)"
        instance = super().__new__(cls, msg, errors)
        return instance

    def __init__(self, schema: str, errors: list[ValidolError], src: int = 0):
        # ExceptionGroup is already initialized in __new__, we just set Azos fields
        self.topic = "validol"
        self.frm = schema
        self.src = src
        self._message = f"Validation of `{schema}` failed with {len(errors)} error(s)"
        self.field = "*"

    @property
    def schema(self) -> str:
        """Validation schema name (alias for `frm`)"""
        return self.frm

    @property
    def errors(self) -> tuple[ValidolError | ExceptionGroup[ValidolError], ...]:
        """Tuple of contained validation errors (alias for `exceptions`)"""
        return self.exceptions

    def derive(self, excs: Sequence[BaseException]) -> "ValidolBatchError":
        """Required by ExceptionGroup to create subgroups of the same type"""
        return ValidolBatchError(schema=self.frm, errors=list(excs), src=self.src)  # type: ignore[arg-type]

    def __str__(self) -> str:
        lines = [f"Validation of `{self.frm}` failed with {len(self.exceptions)} error(s):"]
        for i, err in enumerate(self.exceptions, 1):
            lines.append(f"  {i}. {err}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"ValidolBatchError(schema={self.frm!r}, "
                f"errors={list(self.exceptions)!r}, src={self.src})")



class Validol:
    """Reusable validation logic that inspects target object fields via getattr"""

    def __init__(self, target: Any):
        self._target = target
        self._errors: list[ValidolError] | None = None


    @property
    def target(self) -> Any:
        """Validation target object"""
        return self._target


    def emit(self, error: ValidolError) -> "Validol":
        """Appends a validation error to the batch"""
        if not self._errors:
            self._errors = []

        self._errors.append(error)
        return self


    def throw(self) -> None:
        """Raises `ValidolBatchError` (ExceptionGroup) if any validation errors were emitted.

        The raised exception is an `ExceptionGroup` and can be caught with `except*`.
        """
        if self._errors:
            raise ValidolBatchError(
                schema=self._target.__class__.__name__,
                errors=self._errors,
                src=0)


    def that(self, predicate: Callable[["Validol"], None]) -> "Validol":
        """Invokes a custom validation lambda/function passing this Validol instance.

        The predicate receives the Validol instance and can emit errors via `self.emit()`.
        Returns self for fluent chaining.

        Example::

            Validol(obj) \\
                .is_str("name", required=True, min=1, max=100) \\
                .that(lambda v: v.emit(ValidolError("MySchema", "x", "X must be odd")) if v.target.x % 2 == 0 else None) \\
                .throw()
        """
        predicate(self)
        return self


    def test(self, message: str, predicate: Callable[["Validol"], bool]) -> "Validol":
        """Validates that a custom predicate returns True, emitting an error if it returns False.

        Similar to `that()` but auto-emits a `ValidolError` when the predicate returns False,
        so callers don't need to call `emit()` themselves.
        The field is always set to ``"*"`` because the predicate may analyze multiple fields.

        Example::

            Validol(obj) \\
                .test("Must be adult", lambda v: v.target.age >= 18) \\
                .throw()
        """
        if not predicate(self):
            self.emit(ValidolError(
                schema=self._target.__class__.__name__,
                field="*",
                message=message))
        return self


    def is_str(self, attr: str, required: bool, min: int, max: int) -> "Validol":
        val = getattr(self._target, attr, None)

        if val is not None and not isinstance(val, str):
            self.emit(ValidolError(
                schema=self._target.__class__.__name__,
                field=attr,
                message=f"Field '{attr}' must contain a string value"))
            return self

        if val is None or not val.strip():
            if required:
                self.emit(ValidolError(
                    schema=self._target.__class__.__name__,
                    field=attr,
                    message=f"String field '{attr}' must be a non-blank"))
            return self

        vl = len(val)

        if vl < min:
            self.emit(ValidolError(
                schema=self._target.__class__.__name__,
                field=attr,
                message=f"String field '{attr}' must be at least {min} chars long"))
            return self

        if vl > max:
            self.emit(ValidolError(
                schema=self._target.__class__.__name__,
                field=attr,
                message=f"String field '{attr}' must be at most {max} chars long"))
            return self

        return self


    def is_int(self, attr: str, required: bool, min: int | None = None, max: int | None = None) -> "Validol":
        """Validates that a field contains an integer value.

        When `required` is False and the value is None, validation passes.
        When present, the value must be an int (bool excluded) and within [min..max] bounds.
        """
        val = getattr(self._target, attr, None)
        schema = self._target.__class__.__name__

        if val is None:
            if required:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Int field '{attr}' is required"))
            return self

        # bool is subclass of int, but we do not accept it as integer
        if not isinstance(val, int) or isinstance(val, bool):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Field '{attr}' must contain an int value"))
            return self

        if min is not None and val < min:
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Int field '{attr}' must be >= {min}"))
            return self

        if max is not None and val > max:
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Int field '{attr}' must be <= {max}"))
            return self

        return self


    def is_float(self, attr: str, required: bool, min: float | None = None, max: float | None = None) -> "Validol":
        """Validates that a field contains a float (or int-coercible-to-float) value.

        When `required` is False and the value is None, validation passes.
        When present, the value must be int or float (bool excluded) and within [min..max] bounds.
        """
        val = getattr(self._target, attr, None)
        schema = self._target.__class__.__name__

        if val is None:
            if required:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Float field '{attr}' is required"))
            return self

        # Accept int or float, but not bool
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Field '{attr}' must contain a float value"))
            return self

        fval = float(val)

        if min is not None and fval < min:
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Float field '{attr}' must be >= {min}"))
            return self

        if max is not None and fval > max:
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Float field '{attr}' must be <= {max}"))
            return self

        return self


    def is_decimal(self, attr: str, required: bool, min: Decimal | float | None = None, max: Decimal | float | None = None) -> "Validol":
        """Validates that a field contains a Decimal value.

        When `required` is False and the value is None, validation passes.
        When present, the value must be a Decimal (or int/float/str coercible to Decimal)
        and within [min..max] bounds.
        """
        val = getattr(self._target, attr, None)
        schema = self._target.__class__.__name__

        if val is None:
            if required:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Decimal field '{attr}' is required"))
            return self

        # Try to coerce to Decimal: accept Decimal, int, float, numeric str
        if isinstance(val, bool):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Field '{attr}' must contain a Decimal value"))
            return self

        try:
            dval = Decimal(val) if not isinstance(val, Decimal) else val
        except (InvalidOperation, TypeError, ValueError):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Field '{attr}' must contain a Decimal value"))
            return self

        if min is not None and dval < Decimal(str(min)):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Decimal field '{attr}' must be >= {min}"))
            return self

        if max is not None and dval > Decimal(str(max)):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Decimal field '{attr}' must be <= {max}"))
            return self

        return self


    def is_bool(self, attr: str, required: bool) -> "Validol":
        """Validates that a field contains a boolean value.

        When `required` is False and the value is None, validation passes.
        When present, the value must be strictly a bool (not int or other truthy/falsy types).
        """
        val = getattr(self._target, attr, None)
        schema = self._target.__class__.__name__

        if val is None:
            if required:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Bool field '{attr}' is required"))
            return self

        if not isinstance(val, bool):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Field '{attr}' must contain a bool value"))
            return self

        return self


    def is_date(self, attr: str, required: bool, min: date | None = None, max: date | None = None) -> "Validol":
        """Validates that a field contains a date or datetime value.

        When `required` is False and the value is None, validation passes.
        When present, the value must be a `date` or `datetime` instance
        and within [min..max] bounds. Comparison is done on the date portion only.
        """
        val = getattr(self._target, attr, None)
        schema = self._target.__class__.__name__

        if val is None:
            if required:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Date field '{attr}' is required"))
            return self

        if not isinstance(val, (date, datetime)):
            self.emit(ValidolError(schema=schema, field=attr,
                message=f"Field '{attr}' must contain a date or datetime value"))
            return self

        # Normalize to date for comparison (datetime is subclass of date)
        dval = val if isinstance(val, date) and not isinstance(val, datetime) else val.date() if isinstance(val, datetime) else val

        if min is not None:
            min_date = min.date() if isinstance(min, datetime) else min
            if dval < min_date:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Date field '{attr}' must be >= {min_date}"))
                return self

        if max is not None:
            max_date = max.date() if isinstance(max, datetime) else max
            if dval > max_date:
                self.emit(ValidolError(schema=schema, field=attr,
                    message=f"Date field '{attr}' must be <= {max_date}"))
                return self

        return self

