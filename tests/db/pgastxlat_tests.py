import ast
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pytest

from azos.db.pgconnector import PgASTXlat
from azos.exceptions import AzosError


# ----------------------------------------------------------------------------------------------
# A "Person" model used by the tests: column name -> python type the column accepts
# ----------------------------------------------------------------------------------------------

COLUMN_TYPES = {
    "FirstName": str,
    "LastName": str,
    "Notes": str,
    "Age": int,
    "Salary": Decimal,
    "Rating": float,
    "DOB": datetime,
    "IsActive": bool,
}

LIMITS = list(COLUMN_TYPES)


def _bad(column: str, value: object) -> AzosError:
    return AzosError(
        message=f"Bad value for column `{column}`: `{value!r}`",
        topic="test",
        frm="convert()",
        src=0
    )


def convert(xlat: PgASTXlat, column: str, value: object) -> object:
    """Polymorphic conversion by column name, the way an application would do it"""
    expected = COLUMN_TYPES[column]

    if expected is bool:
        if isinstance(value, bool):
            return value
        raise _bad(column, value)

    if isinstance(value, bool):
        raise _bad(column, value)

    if expected is str:
        if isinstance(value, str):
            return value
    elif expected is int:
        if isinstance(value, int):
            return value
    elif expected is float:
        if isinstance(value, (int, float)):
            return float(value)
    elif expected is Decimal:
        if isinstance(value, (int, float, str)):
            try:
                result = Decimal(str(value))
            except InvalidOperation:
                raise _bad(column, value) from None
            if result.is_finite():
                return result
    elif expected is datetime:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise _bad(column, value) from None

    raise _bad(column, value)


def xlat() -> PgASTXlat:
    return PgASTXlat(LIMITS, convert)


# ----------------------------------------------------------------------------------------------
# Valid filters: types
# ----------------------------------------------------------------------------------------------

def test_int_01():
    sql, args = xlat().from_string("Age == 42")
    assert sql == '"Age" = $1'
    assert args == [42]
    assert type(args[0]) is int


def test_int_negative_01():
    sql, args = xlat().from_string("Age > -5")
    assert sql == '"Age" > $1'
    assert args == [-5]


def test_int_explicit_plus_01():
    sql, args = xlat().from_string("Age > +5")
    assert sql == '"Age" > $1'
    assert args == [5]


def test_int_large_01():
    sql, args = xlat().from_string("Age < 9223372036854775807")
    assert args == [9223372036854775807]


def test_decimal_from_int_01():
    sql, args = xlat().from_string("Salary >= 50000")
    assert sql == '"Salary" >= $1'
    assert args == [Decimal("50000")]
    assert type(args[0]) is Decimal


def test_decimal_from_float_01():
    sql, args = xlat().from_string("Salary > 1234.56")
    assert args == [Decimal("1234.56")]
    assert type(args[0]) is Decimal


def test_decimal_from_string_01():
    sql, args = xlat().from_string("Salary == '99999.99'")
    assert args == [Decimal("99999.99")]


def test_decimal_negative_01():
    sql, args = xlat().from_string("Salary < -0.01")
    assert args == [Decimal("-0.01")]


def test_float_01():
    sql, args = xlat().from_string("Rating >= 4.5")
    assert sql == '"Rating" >= $1'
    assert args == [4.5]
    assert type(args[0]) is float


def test_float_from_int_01():
    sql, args = xlat().from_string("Rating > 4")
    assert args == [4.0]
    assert type(args[0]) is float


def test_float_negative_01():
    sql, args = xlat().from_string("Rating < -1.25")
    assert args == [-1.25]


def test_datetime_from_iso_datetime_01():
    sql, args = xlat().from_string("DOB > '1980-01-01T10:30:00'")
    assert sql == '"DOB" > $1'
    assert args == [datetime(1980, 1, 1, 10, 30)]
    assert type(args[0]) is datetime


def test_datetime_from_iso_date_01():
    sql, args = xlat().from_string("DOB >= '1980-01-01'")
    assert args == [datetime(1980, 1, 1)]


def test_string_01():
    sql, args = xlat().from_string("LastName == 'Smith'")
    assert sql == '"LastName" = $1'
    assert args == ["Smith"]


def test_string_double_quoted_01():
    sql, args = xlat().from_string('LastName == "Smith"')
    assert args == ["Smith"]


def test_string_unicode_01():
    sql, args = xlat().from_string("LastName == 'Σμιθ-Øvergård'")
    assert args == ["Σμιθ-Øvergård"]


def test_string_empty_01():
    sql, args = xlat().from_string("Notes == ''")
    assert sql == '"Notes" = $1'
    assert args == [""]


def test_bool_01():
    sql, args = xlat().from_string("IsActive == True")
    assert sql == '"IsActive" = $1'
    assert args == [True]


def test_bool_false_01():
    sql, args = xlat().from_string("IsActive != False")
    assert sql == '"IsActive" != $1'
    assert args == [False]


def test_none_eq_01():
    sql, args = xlat().from_string("Notes == None")
    assert sql == '"Notes" IS NULL'
    assert args == []


def test_none_not_eq_01():
    sql, args = xlat().from_string("Notes != None")
    assert sql == '"Notes" IS NOT NULL'
    assert args == []


def test_none_does_not_call_convert_01():
    calls = []

    def spy(x, column, value):
        calls.append((column, value))
        return value

    PgASTXlat(LIMITS, spy).from_string("Notes == None")
    assert calls == []


def test_none_with_other_conditions_01():
    sql, args = xlat().from_string("Notes == None and Age > 18")
    assert sql == '("Notes" IS NULL AND "Age" > $1)'
    assert args == [18]


# ----------------------------------------------------------------------------------------------
# Valid filters: operators
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("py_op, sql_op", [
    ("==", "="),
    ("!=", "!="),
    (">", ">"),
    (">=", ">="),
    ("<", "<"),
    ("<=", "<="),
])
def test_comparison_operators_01(py_op, sql_op):
    sql, args = xlat().from_string(f"Age {py_op} 30")
    assert sql == f'"Age" {sql_op} $1'
    assert args == [30]


def test_reversed_operands_01():
    sql, args = xlat().from_string("18 < Age")
    assert sql == '$1 < "Age"'
    assert args == [18]


def test_reversed_operands_converted_01():
    sql, args = xlat().from_string("'1980-01-01' < DOB")
    assert sql == '$1 < "DOB"'
    assert args == [datetime(1980, 1, 1)]


def test_chained_01():
    sql, args = xlat().from_string("18 <= Age < 65")
    assert sql == '($1 <= "Age" AND "Age" < $2)'
    assert args == [18, 65]


def test_chained_dates_01():
    sql, args = xlat().from_string("'1980-01-01' <= DOB < '1990-01-01'")
    assert sql == '($1 <= "DOB" AND "DOB" < $2)'
    assert args == [datetime(1980, 1, 1), datetime(1990, 1, 1)]


def test_column_vs_column_01():
    sql, args = xlat().from_string("FirstName == LastName")
    assert sql == '"FirstName" = "LastName"'
    assert args == []


def test_column_vs_column_does_not_call_convert_01():
    calls = []
    PgASTXlat(LIMITS, lambda x, c, v: calls.append(c)).from_string("FirstName == LastName")
    assert calls == []


def test_and_01():
    sql, args = xlat().from_string("Age > 18 and IsActive == True")
    assert sql == '("Age" > $1 AND "IsActive" = $2)'
    assert args == [18, True]


def test_or_01():
    sql, args = xlat().from_string("Age < 18 or Age > 65")
    assert sql == '("Age" < $1 OR "Age" > $2)'
    assert args == [18, 65]


def test_and_three_operands_01():
    sql, args = xlat().from_string("Age > 18 and Age < 65 and IsActive == True")
    assert sql == '("Age" > $1 AND "Age" < $2 AND "IsActive" = $3)'
    assert args == [18, 65, True]


def test_and_or_precedence_01():
    sql, args = xlat().from_string("Age > 18 or Age < 5 and IsActive == True")
    assert sql == '("Age" > $1 OR ("Age" < $2 AND "IsActive" = $3))'
    assert args == [18, 5, True]


def test_parentheses_override_precedence_01():
    sql, args = xlat().from_string("(Age > 18 or Age < 5) and IsActive == True")
    assert sql == '(("Age" > $1 OR "Age" < $2) AND "IsActive" = $3)'
    assert args == [18, 5, True]


def test_not_01():
    sql, args = xlat().from_string("not (Age > 18)")
    assert sql == '(NOT "Age" > $1)'
    assert args == [18]


def test_not_of_group_01():
    sql, args = xlat().from_string("not (Age < 18 or IsActive == False)")
    assert sql == '(NOT ("Age" < $1 OR "IsActive" = $2))'
    assert args == [18, False]


def test_in_strings_01():
    sql, args = xlat().from_string("LastName in ('Smith', 'Jones', 'Brown')")
    assert sql == '"LastName" IN ($1, $2, $3)'
    assert args == ["Smith", "Jones", "Brown"]


def test_in_list_and_set_literals_01():
    sql, args = xlat().from_string("Age in [1, 2]")
    assert sql == '"Age" IN ($1, $2)'
    assert args == [1, 2]

    sql, args = xlat().from_string("Age in {7}")
    assert sql == '"Age" IN ($1)'
    assert args == [7]


def test_not_in_01():
    sql, args = xlat().from_string("LastName not in ('Smith', 'Jones')")
    assert sql == '"LastName" NOT IN ($1, $2)'
    assert args == ["Smith", "Jones"]


def test_in_converts_every_element_01():
    sql, args = xlat().from_string("DOB in ('1980-01-01', '1981-02-03T04:05:06')")
    assert args == [datetime(1980, 1, 1), datetime(1981, 2, 3, 4, 5, 6)]


def test_in_decimal_01():
    sql, args = xlat().from_string("Salary in (1, 2.5, '3.75')")
    assert args == [Decimal("1"), Decimal("2.5"), Decimal("3.75")]


# ----------------------------------------------------------------------------------------------
# Valid filters: realistic combinations
# ----------------------------------------------------------------------------------------------

def test_lastname_in_and_dob_01():
    sql, args = xlat().from_string("LastName in ('Smith', 'Jones', 'Brown') and DOB > '1980-01-01'")
    assert sql == '("LastName" IN ($1, $2, $3) AND "DOB" > $4)'
    assert args == ["Smith", "Jones", "Brown", datetime(1980, 1, 1)]


def test_lastname_or_chain_and_dob_01():
    sql, args = xlat().from_string(
        "(LastName == 'Smith' or LastName == 'Jones' or LastName == 'Brown') and DOB > '1980-01-01'")
    assert sql == '(("LastName" = $1 OR "LastName" = $2 OR "LastName" = $3) AND "DOB" > $4)'
    assert args == ["Smith", "Jones", "Brown", datetime(1980, 1, 1)]


def test_complex_person_filter_01():
    sql, args = xlat().from_string(
        "LastName in ('Smith', 'Jones') and DOB >= '1980-01-01' and DOB < '1990-01-01' "
        "and (Salary > 50000.50 or Rating >= 4.5) and Notes != None and not IsActive == False")
    assert sql == (
        '("LastName" IN ($1, $2) AND "DOB" >= $3 AND "DOB" < $4 '
        'AND ("Salary" > $5 OR "Rating" >= $6) AND "Notes" IS NOT NULL AND (NOT "IsActive" = $7))')
    assert args == [
        "Smith", "Jones",
        datetime(1980, 1, 1), datetime(1990, 1, 1),
        Decimal("50000.50"), 4.5,
        False
    ]


def test_param_numbering_is_sequential_01():
    sql, args = xlat().from_string("Age == 1 or Age == 2 or Age == 3 or Age in (4, 5)")
    assert sql == '("Age" = $1 OR "Age" = $2 OR "Age" = $3 OR "Age" IN ($4, $5))'
    assert args == [1, 2, 3, 4, 5]


def test_same_value_twice_gets_two_params_01():
    sql, args = xlat().from_string("Age == 5 or Age == 5")
    assert sql == '("Age" = $1 OR "Age" = $2)'
    assert args == [5, 5]


def test_whitespace_and_newlines_01():
    sql, args = xlat().from_string("(\n  Age   >   18\n  and\n  IsActive   ==   True\n)")
    assert sql == '("Age" > $1 AND "IsActive" = $2)'
    assert args == [18, True]


# ----------------------------------------------------------------------------------------------
# Instance behavior
# ----------------------------------------------------------------------------------------------

def test_instance_reuse_resets_state_01():
    x = xlat()
    sql1, args1 = x.from_string("Age == 1")
    sql2, args2 = x.from_string("LastName == 'X'")
    assert (sql1, args1) == ('"Age" = $1', [1])
    assert (sql2, args2) == ('"LastName" = $1', ["X"])


def test_from_expression_01():
    expr = ast.parse("Age > 18 and LastName == 'Smith'", mode="eval")
    sql, args = xlat().from_expression(expr)
    assert sql == '("Age" > $1 AND "LastName" = $2)'
    assert args == [18, "Smith"]


def test_from_expression_does_not_mutate_input_01():
    expr = ast.parse("Age > -18 and DOB > '1980-01-01'", mode="eval")
    before = ast.dump(expr)
    xlat().from_expression(expr)
    assert ast.dump(expr) == before


def test_from_expression_same_ast_twice_01():
    expr = ast.parse("DOB > '1980-01-01'", mode="eval")
    x = xlat()
    assert x.from_expression(expr) == x.from_expression(expr)


def test_no_limits_no_convert_defaults_01():
    sql, args = PgASTXlat().from_string("Anything > 5 and Whatever == 'x'")
    assert sql == '("Anything" > $1 AND "Whatever" = $2)'
    assert args == [5, "x"]


def test_empty_limits_means_any_column_01():
    sql, args = PgASTXlat([]).from_string("Anything == 1")
    assert sql == '"Anything" = $1'


def test_limits_without_convert_01():
    sql, args = PgASTXlat(["Age"]).from_string("Age == 'not checked'")
    assert args == ["not checked"]


def test_convert_receives_xlat_column_value_01():
    calls = []

    def spy(x, column, value):
        calls.append((x, column, value))
        return value

    x = PgASTXlat(["Age", "LastName"], spy)
    x.from_string("Age > 5 and 'S' < LastName")
    assert calls == [(x, "Age", 5), (x, "LastName", "S")]


def test_convert_result_is_used_01():
    x = PgASTXlat(["Age"], lambda x, c, v: v * 2) # type: ignore
    sql, args = x.from_string("Age == 21")
    assert args == [42]


def test_convert_result_can_be_any_object_01():
    marker = object()
    x = PgASTXlat(["Age"], lambda x, c, v: marker)
    sql, args = x.from_string("Age == 21")
    assert args[0] is marker


def test_do_convert_override_01():
    class MyXlat(PgASTXlat):
        def do_convert(self, column, value):
            return f"{column}:{value}"

    sql, args = MyXlat().from_string("a == 1 and b in (2, 3)")
    assert args == ["a:1", "b:2", "b:3"]


def test_do_convert_override_wins_over_lambda_01():
    class MyXlat(PgASTXlat):
        def do_convert(self, column, value):
            return "override"

    sql, args = MyXlat(None, lambda x, c, v: "lambda").from_string("a == 1")
    assert args == ["override"]


def test_do_convert_override_can_call_super_01():
    class MyXlat(PgASTXlat):
        def do_convert(self, column, value):
            return super().do_convert(column, value) + 1 # type: ignore

    sql, args = MyXlat(None, lambda x, c, v: v * 10).from_string("a == 1") # type: ignore
    assert args == [11]


def test_do_convert_override_can_reject_01():
    class MyXlat(PgASTXlat):
        def do_convert(self, column, value):
            raise AzosError(message="nope", topic="t", frm="f", src=0)

    with pytest.raises(AzosError):
        MyXlat().from_string("a == 1")


# ----------------------------------------------------------------------------------------------
# Disallowed columns
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flt", [
    "Password == 'x'",
    "'x' == Password",
    "Age > Password",
    "Password > Age",
    "Password == None",
    "Password != None",
    "Password in ('a', 'b')",
    "Password not in ('a', 'b')",
    "Age > 5 and Password == 'x'",
    "Password == 'x' or Age > 5",
    "Age > 5 or (LastName == 'Smith' and Password == 'x')",
    "not Password == 'x'",
    "18 < Age < Password",
    "Age == 1 or Age == 2 or Secret > 3",
])
def test_disallowed_column_01(flt):
    with pytest.raises(AzosError) as exc_info:
        xlat().from_string(flt)
    assert "not allowed" in str(exc_info.value)


def test_column_names_are_case_sensitive_01():
    with pytest.raises(AzosError):
        xlat().from_string("lastname == 'Smith'")


def test_dunder_column_name_not_allowed_01():
    with pytest.raises(AzosError):
        xlat().from_string("__class__ == 1")


def test_disallowed_column_with_no_limits_is_fine_01():
    sql, args = PgASTXlat(None, convert=None).from_string("Password == 'x'")
    assert sql == '"Password" = $1'


# ----------------------------------------------------------------------------------------------
# Bad types / values (rejected by convert)
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flt", [
    "Age == 'abc'",
    "Age == '42'",
    "Age == 1.5",
    "Age == True",
    "Age == b'1'",
    "Age == 1j",
    "Age == ...",
    "Age > 'x'",
    "'x' < Age",
    "Age in (1, 'two', 3)",
    "Age in (1, 2.5)",
    "Salary == 'abc'",
    "Salary == 'NaN'",
    "Salary == 'Infinity'",
    "Salary == True",
    "Salary == 1e999",
    "Rating == 'x'",
    "Rating == True",
    "DOB == 'not a date'",
    "DOB == '1980-13-45'",
    "DOB == '31/12/1980'",
    "DOB == ''",
    "DOB == 5",
    "DOB == 1.5",
    "DOB > True",
    "LastName == 5",
    "LastName == 1.5",
    "LastName == True",
    "LastName == b'bytes'",
    "LastName in ('Smith', 5)",
    "IsActive == 1",
    "IsActive == 'true'",
    "IsActive == 0",
    "Age > 5 and LastName == 7",
    "Age > 5 or DOB == 'junk'",
])
def test_bad_type_or_value_01(flt):
    with pytest.raises(AzosError) as exc_info:
        xlat().from_string(flt)
    assert "Bad value" in str(exc_info.value)


def test_bad_type_error_raised_by_default_convert_hook_01():
    # `Age` is a plain int column here; the string is rejected by user supplied rule
    def only_ints(x, column, value):
        if type(value) is not int:
            raise AzosError(message="int only", topic="t", frm="f", src=0)
        return value

    x = PgASTXlat(["Age"], only_ints)
    assert x.from_string("Age == 1")[1] == [1]
    with pytest.raises(AzosError):
        x.from_string("Age == '1'")


# ----------------------------------------------------------------------------------------------
# Python code injection attempts
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flt", [
    "__import__('os').system('echo pwned') == 0",
    "Age == __import__('os').getpid()",
    "Age == eval('1')",
    "Age == exec('x=1')",
    "Age == open('/etc/passwd').read()",
    "Age == compile('1', 'x', 'eval')",
    "Age == getattr(Age, 'real')",
    "LastName == str(5)",
    "Age == int('5')",
    "Age == (lambda: 1)()",
    "Age == (lambda: 1)",
    "lambda: 1",
    "Age == [x for x in range(3)]",
    "Age in [x for x in range(3)]",
    "Age in (x for x in range(3))",
    "Age == {1: 2}",
    "Age == {x: x for x in range(3)}",
    "Age == Age.real",
    "Age.real > 1",
    "LastName.upper() == 'SMITH'",
    "LastName.__class__ == 1",
    "Age == ().__class__.__bases__[0].__subclasses__()",
    "Age == Age[0]",
    "LastName[0] == 'S'",
    "Age == f'{Age}'",
    "LastName == f'{__import__(\"os\")}'",
    "Age == (x := 5)",
    "(x := 5) > 1",
    "Age + 1 > 5",
    "Age > 1 + 1",
    "Age * 2 == 10",
    "Age ** 2 == 100",
    "Age % 2 == 0",
    "Age // 2 == 1",
    "Age | 1 == 1",
    "~Age == 1",
    "-Age == 1",
    "+Age == 1",
    "'a' + LastName == 'aSmith'",
    "'a' 'b' + 'c' == LastName",
    "Age == 1 if True else 2",
    "(Age if True else Age) == 1",
    "Age == *[1, 2]",
    "Age in (*[1, 2],)",
    "Age is None",
    "Age is not None",
    "Age is 5",
    "LastName in 'Smith'",
    "LastName in LastName",
    "LastName in FirstName",
    "Age in range(10)",
    "Age in {1: 2}",
    "Age in ()",
    "Age in []",
    "Age in 5",
    "Age in (1, None)",
    "Age in (1, Age)",
    "Age in (1, (2, 3))",
    "Age in ((1, 2),)",
    "Age in [[1], [2]]",
    "Age in ([1] + [2])",
    "5 in (1, 2)",
    "'x' in (1, 2)",
    "(Age, 1) in ((1, 2),)",
    "(Age, Age) == (1, 2)",
    "Age == (1, 2)",
    "Age == [1, 2]",
    "Age == {1, 2}",
    "Age",
    "5",
    "'text'",
    "None",
    "True",
    "Age and IsActive",
    "Age > 1 and IsActive",
    "not Age",
    "not 5",
    "Age > 1 and 5",
    "Age > 1 or 'x'",
    "[Age > 1]",
    "(Age > 1, Age < 5)",
    "{Age > 1}",
    "...",
])
def test_python_code_injection_rejected_01(flt):
    with pytest.raises(AzosError):
        xlat().from_string(flt)


@pytest.mark.parametrize("flt", [
    "__import__('os').system('echo pwned') == 0",
    "Age == (lambda: 1)()",
    "Age.real > 1",
    "LastName == f'{x}'",
    "Age + 1 > 5",
    "Age in (1, Age)",
])
def test_python_code_injection_rejected_without_limits_01(flt):
    with pytest.raises(AzosError):
        PgASTXlat().from_string(flt)


def test_injected_code_is_never_executed_01(tmp_path):
    marker = tmp_path / "pwned.txt"
    flt = f"Age == open({str(marker)!r}, 'w').write('x')"
    with pytest.raises(AzosError):
        xlat().from_string(flt)
    assert not marker.exists()


def test_injected_code_is_never_executed_without_limits_01(tmp_path):
    marker = tmp_path / "pwned.txt"
    flt = f"Age == open({str(marker)!r}, 'w').write('x')"
    with pytest.raises(AzosError):
        PgASTXlat().from_string(flt)
    assert not marker.exists()


# ----------------------------------------------------------------------------------------------
# Malformed / non-expression input
# ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flt", [
    "",
    "   ",
    "Age ==",
    "== 5",
    "Age == == 5",
    "Age = 5",
    "Age == 5;",
    "Age == 5; Password == 'x'",
    "Age == 5\nPassword == 'x'",
    "import os",
    "import os; Age == 1",
    "x = 1",
    "def f(): pass",
    "class A: pass",
    "for i in x: pass",
    "del Age",
    "Age == (",
    "Age == )",
    "Age == 'unterminated",
    "Age == 5 and",
    "Age > 5 or or Age < 3",
    "Age; DROP TABLE users",
    "Age == 1; DROP TABLE users; --",
    "Age == 1 -- comment",
    "Age == 1 /* comment */",
    "Age == 1 UNION SELECT * FROM users",
    "Age == 1 OR 1=1",
    "Age == 1 AND 1 = 1",
    '"Age"; DROP TABLE users; -- == 1',
    "Age == 1\x00",
])
def test_malformed_input_raises_azos_error_01(flt):
    with pytest.raises(AzosError):
        xlat().from_string(flt)


def test_malformed_input_error_chains_cause_01():
    with pytest.raises(AzosError) as exc_info:
        xlat().from_string("Age ==")
    assert isinstance(exc_info.value.__cause__, SyntaxError)


# ----------------------------------------------------------------------------------------------
# SQL injection attempts: values must stay parameters, identifiers must stay quoted
# ----------------------------------------------------------------------------------------------

SQL_ATTACKS = [
    "'; DROP TABLE users; --",
    "x' OR '1'='1",
    "x\" OR \"1\"=\"1",
    "1; DELETE FROM users",
    "Smith') OR ('1'='1",
    "\\'; DROP TABLE users; --",
    "%s",
    "{0}",
    "Robert'); DROP TABLE Students;--",
    "\x00",
    "/* x */ OR 1=1",
]


@pytest.mark.parametrize("attack", SQL_ATTACKS)
def test_sql_injection_in_string_value_stays_a_parameter_01(attack):
    sql, args = xlat().from_string(f"LastName == {attack!r}")
    assert sql == '"LastName" = $1'
    assert args == [attack]


@pytest.mark.parametrize("attack", SQL_ATTACKS)
def test_sql_injection_in_in_list_stays_parameters_01(attack):
    sql, args = xlat().from_string(f"LastName in ('Smith', {attack!r})")
    assert sql == '"LastName" IN ($1, $2)'
    assert args == ["Smith", attack]


@pytest.mark.parametrize("attack", SQL_ATTACKS)
def test_sql_injection_never_appears_in_sql_text_01(attack):
    sql, args = xlat().from_string(f"LastName == {attack!r} and FirstName != {attack!r}")
    assert sql == '("LastName" = $1 AND "FirstName" != $2)'
    assert attack not in sql


def test_sql_text_contains_only_known_tokens_01():
    sql, args = xlat().from_string(
        "LastName in ('a', 'b') and (Age > 1 or Salary < 2.5) and not IsActive == False and Notes == None")
    stripped = sql
    for token in ['"LastName"', '"Age"', '"Salary"', '"IsActive"', '"Notes"',
                  "IN", "AND", "OR", "NOT", "IS NULL", "$1", "$2", "$3", "$4", "$5", "=", ">", "<", "(", ")", ",", " "]:
        stripped = stripped.replace(token, "")
    assert stripped == ""


def test_constant_only_comparison_rejected_01():
    for flt in ["1 == 1", "'a' == 'a'", "1 == 1 or Age > 5", "Age > 5 and 1 < 2", "1 < 2 < Age", "None == None"]:
        with pytest.raises(AzosError) as exc_info:
            xlat().from_string(flt)
        assert "at least one column" in str(exc_info.value)


def test_none_literal_on_left_01():
    assert xlat().from_string("None == Notes") == ('"Notes" IS NULL', [])
    assert xlat().from_string("None != Notes") == ('"Notes" IS NOT NULL', [])


@pytest.mark.parametrize("flt", [
    "Notes > None",
    "Notes >= None",
    "Notes < None",
    "Notes <= None",
    "None < Notes",
    "Age in (None,)",
])
def test_none_with_ordering_operators_rejected_01(flt):
    with pytest.raises(AzosError):
        xlat().from_string(flt)


def test_convert_not_called_for_disallowed_column_01():
    calls = []

    def spy(x, column, value):
        calls.append(column)
        return value

    with pytest.raises(AzosError):
        PgASTXlat(["Age"], spy).from_string("Password == 'x'")
    assert calls == []


def test_sql_injection_via_column_name_is_not_expressible_01():
    # Anything that is not a plain Python identifier cannot become a column name
    for flt in ['"Age"" OR 1=1 --" == 1', "Age OR 1=1", "Age--", "Age; --", "Age' == 1", "`Age` == 1"]:
        with pytest.raises(AzosError):
            xlat().from_string(flt)


def test_sql_injection_via_column_name_unlimited_stays_quoted_01():
    # Without limits any identifier is allowed, but it is always emitted as a quoted identifier
    sql, args = PgASTXlat().from_string("DROP == 1")
    assert sql == '"DROP" = $1'


def test_unicode_identifier_column_01():
    sql, args = PgASTXlat().from_string("Фамилия == 'Иванов'")
    assert sql == '"Фамилия" = $1'
    assert args == ["Иванов"]


def test_non_string_numeric_values_are_params_01():
    sql, args = xlat().from_string("Age == 1")
    assert "1" not in sql.replace("$1", "")
