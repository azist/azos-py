"""
Tests for named parameter compilation/binding in pgconnector

Copyright (C) 2011 - 2026 Azist, MIT License
"""

import pytest

import azos.db.pgconnector as pgc
from azos.db.pgconnector import bind
from azos.exceptions import AzosError

compile_named = pgc.__compile_named


# ---------- compile: plain parameters ----------

def test_plain_param_01():
    """Single parameter becomes $1"""
    assert compile_named("select * from t where a = $a") == ("select * from t where a = $1", ("a",))


def test_plain_param_02():
    """Multiple parameters are numbered in order of first appearance"""
    assert compile_named("select $b, $a, $c") == ("select $1, $2, $3", ("b", "a", "c"))


def test_plain_param_03():
    """Same name used many times maps to the same $N"""
    assert compile_named("select $a, $b, $a") == ("select $1, $2, $1", ("a", "b"))


def test_plain_param_04():
    """Casts, underscores and digits in names"""
    assert compile_named("select $user_id1::int, $x_2") == ("select $1::int, $2", ("user_id1", "x_2"))


def test_no_params_01():
    """No parameters leaves text untouched"""
    assert compile_named("select 1") == ("select 1", ())


def test_positional_untouched_01():
    """Native positional $1 is not a named parameter"""
    assert compile_named("select $1, $a") == ("select $1, $1", ("a",))


def test_ident_with_dollar_01():
    """`$` is legal inside identifiers so `foo$bar` is not a parameter"""
    assert compile_named("select foo$bar, $x") == ("select foo$bar, $1", ("x",))


# ---------- compile: skipped constructs ----------

@pytest.mark.parametrize("sql", [
    "select 'Name: $X'",
    "select 'it''s $X'",
    "select '''$X'''",
    "select ''",
    "select 'multi\nline $X'",
    "select 'back\\slash $X'",              # standard string: backslash is literal
    "select 'trail\\'",                     # ... so this string is complete
    "select E'it\\'s $X'",
    "select e'a\\\\' || 'b'",               # escaped backslash then close quote
    "select E'it''s $X'",
    "select B'1010', X'FF', U&'d\\0061t $X'",
    'select "col$X" from t',
    'select "a""$X" from t',
    "select 1 -- comment $X",
    "select 1 -- comment $X\n",
    "select 1 /* $X */",
    "select 1 /* a /* nested $X */ still comment $Y */",
    "select 1 /* multi\nline $X\n*/",
    "select $$ body $X $$",
    "select $fn$ body $X $$ $fn$",
    "select $$ it's ' $X $$",
    "select $a1$ -- not comment /* $X $a1$",
])
def test_skipped_01(sql):
    """Constructs which must not yield parameters leave SQL untouched"""
    assert compile_named(sql) == (sql, ())


def test_skipped_mixed_01():
    """Real parameters around skipped constructs are still bound"""
    sql = "select $a, 'x $b', /* $c */ $d -- $e\n, \"q$f\", $$ $g $$, $h"
    text, names = compile_named(sql)
    assert names == ("a", "d", "h")
    assert text == "select $1, 'x $b', /* $c */ $2 -- $e\n, \"q$f\", $$ $g $$, $3"


def test_skipped_after_string_01():
    """A string closing right before a parameter does not swallow it"""
    assert compile_named("select 'a'||$x") == ("select 'a'||$1", ("x",))
    assert compile_named("select 'a''b'||$x") == ("select 'a''b'||$1", ("x",))


def test_escape_string_vs_standard_01():
    """Backslash-quote ends a standard string but is an escape in E-string"""
    # standard: string is 'a\' then $x is a real parameter then another string 'b'
    assert compile_named("select 'a\\', $x, 'b'") == ("select 'a\\', $1, 'b'", ("x",))
    # escape: \' does not end the string, so $x is inside
    assert compile_named("select E'a\\', $x, ' , $y") == ("select E'a\\', $x, ' , $1", ("y",))


def test_dollar_quote_same_tag_only_01():
    """A dollar-quote closes only on the same tag"""
    sql = "select $a$ $b$ $X $a$, $y"
    assert compile_named(sql) == ("select $a$ $b$ $X $a$, $1", ("y",))


def test_dollar_function_body_01():
    """Typical function body in dollar quotes containing parameter-like text"""
    sql = "create function f() returns int as $body$ begin return $X; end; $body$ language plpgsql where a = $a"
    text, names = compile_named(sql)
    assert names == ("a",)
    assert "$body$ begin return $X; end; $body$" in text
    assert text.endswith("where a = $1")


def test_line_comment_eof_01():
    """Line comment may end at EOF without newline, and ends at newline"""
    assert compile_named("select $a -- $b\n, $c") == ("select $1 -- $b\n, $2", ("a", "c"))


def test_comment_markers_in_string_01():
    """Comment markers inside strings are not comments"""
    assert compile_named("select '-- not', $a, '/* not', $b") == ("select '-- not', $1, '/* not', $2", ("a", "b"))


def test_string_markers_in_comment_01():
    """Quote characters inside comments do not open strings"""
    assert compile_named("select 1 -- it's\n, $a") == ("select 1 -- it's\n, $1", ("a",))
    assert compile_named("select 1 /* it's */, $a") == ("select 1 /* it's */, $1", ("a",))


def test_cache_stable_01():
    """Translation is cached and stable for the same source"""
    sql = "select $a, 'x $b'"
    assert compile_named(sql) is compile_named(sql)

# ---------- compile: errors ----------

@pytest.mark.parametrize("sql", [
    "select 'abc $X",
    "select 'abc'' $X",
    "select E'abc\\' $X",
    'select "abc $X',
    "select $$ abc $X",
    "select $t$ abc $X $u$",
    "select 1 /* abc $X",
    "select 1 /* a /* b */ $X",
])
def test_unterminated_01(sql):
    """Unterminated string/identifier/dollar-quote/block comment raise AzosError"""
    with pytest.raises(AzosError) as ei:
        compile_named(sql)
    assert "Unterminated" in str(ei.value)


def test_unterminated_position_01():
    """Error reports position of the opener"""
    with pytest.raises(AzosError) as ei:
        compile_named("select 1, 'oops $a")
    assert "position 10" in str(ei.value)


def test_unterminated_no_hang_01():
    """Long unterminated input fails fast, with no catastrophic backtracking"""
    with pytest.raises(AzosError):
        compile_named("select '" + "''" * 20000 + " $x")  # opener + escaped quotes, never closed
    with pytest.raises(AzosError):
        compile_named("select '" + "x" * 100000)


# ---------- bind ----------

def test_bind_01():
    """Binds named params to positional args"""
    assert bind("select * from t where a = $a and b = $b", a=1, b="x") == ("select * from t where a = $1 and b = $2", 1, "x")


def test_bind_02():
    """Args follow order of first appearance, not kwarg order"""
    assert bind("select $b, $a", a=1, b=2) == ("select $1, $2", 2, 1)


def test_bind_03():
    """Repeated name yields single arg"""
    assert bind("select $a, $a, $b, $a", a=1, b=2) == ("select $1, $1, $2, $1", 1, 2)


def test_bind_04():
    """Extra params are ignored"""
    assert bind("select $a", a=1, zzz=99, yyy=None) == ("select $1", 1)


def test_bind_05():
    """No params yields SQL only"""
    assert bind("select 1") == ("select 1",)
    assert bind("select 1", a=1) == ("select 1",)


def test_bind_06():
    """None and falsy values are legit values"""
    assert bind("select $a, $b, $c", a=None, b=0, c="") == ("select $1, $2, $3", None, 0, "")


def test_bind_07():
    """Params inside strings/comments do not need to be supplied"""
    assert bind("select 'Name: $X' -- $Y\n, $a /* $Z */", a=5) == ("select 'Name: $X' -- $Y\n, $1 /* $Z */", 5)


def test_bind_08():
    """Params inside strings/comments are not bound even when supplied"""
    assert bind("select 'Name: $X', $a", a=1, X=2) == ("select 'Name: $X', $1", 1)


def test_bind_09():
    """Dollar-quoted body with parameter-like text, plus real parameter"""
    assert bind("do $$ begin perform $X; end $$; select $a", a=7) == ("do $$ begin perform $X; end $$; select $1", 7)


def test_bind_10():
    """Complex values (lists, dicts, bytes) are passed through as is"""
    lst, dct, raw = [1, 2], {"k": 1}, b"\x00"
    assert bind("select $l, $d, $r", l=lst, d=dct, r=raw) == ("select $1, $2, $3", lst, dct, raw)


def test_bind_11():
    """Realistic multi-line statement"""
    sql = """
        -- find user by $id (this is only a comment)
        select id, name
        from "user$tbl"
        where id = $id
          and note <> 'id: $id'
          and tag = any($tags::text[])
          /* old: and x = $x */
    """
    res = bind(sql, id=10, tags=["a"], x=0)
    assert res[1:] == (10, ["a"])
    assert "id = $1" in res[0]
    assert "any($2::text[])" in res[0]
    assert "'id: $id'" in res[0] and "$id (this" in res[0] and "$x */" in res[0]


def test_bind_missing_01():
    """Missing parameter raises AzosError naming it"""
    with pytest.raises(AzosError) as ei:
        bind("select $a, $b", a=1)
    assert "`b`" in str(ei.value)


def test_bind_missing_02():
    """Parameter present only in a string literal is not required, but a real one still is"""
    with pytest.raises(AzosError):
        bind("select 'x $a', $b", a=1)


def test_bind_unterminated_01():
    """Unterminated literal surfaces as AzosError from bind"""
    with pytest.raises(AzosError):
        bind("select 'oops $a", a=1)

def test_realistic_01():
    sql, *pars = bind("""
-- This is an $b example
/* of various
 comments   $a
 */
 select a as "tezt", $b+t.age
 from table t
 where
  t.counter = $a and
  t.age > $b and exists (
   select 1 from CUSTOMER C where C.last_Name=$last_name

  )
""", a=123, b=230, last_name="Kutz")

    print(sql)
    print(pars)
    assert sql.index("t.counter = $2") > 0
    assert sql.index("C.last_Name=$3") > 0
    assert [230,123,"Kutz"]==pars


# ---------- cache effectiveness alarm ----------

def test_cache_alarm_dynamic_sql_01(monkeypatch):
    """Compiling more distinct SQL texts than SQL_CACHE_SIZE logs CRITICAL on every further compilation"""
    calls = []
    monkeypatch.setattr(pgc._LOG, "critical", lambda msg, *a, **k: calls.append(msg))
    monkeypatch.setattr(pgc, "_sql_cache_compiles", 0)
    compile_named.cache_clear()

    extra = 10
    for i in range(pgc.SQL_CACHE_SIZE + extra):
        compile_named(f"select * from t where id = {i} and a = $a")

    assert len(calls) == extra
    assert "overused" in calls[0] and "dynamically" in calls[0]
    compile_named.cache_clear()


def test_cache_alarm_static_sql_01(monkeypatch):
    """Up to SQL_CACHE_SIZE distinct statements, repeated, never alarm"""
    calls = []
    monkeypatch.setattr(pgc._LOG, "critical", lambda msg, *a, **k: calls.append(msg))
    monkeypatch.setattr(pgc, "_sql_cache_compiles", 0)
    compile_named.cache_clear()

    stmts = [f"select {i}, $a" for i in range(pgc.SQL_CACHE_SIZE)]
    for _ in range(3):
        for s in stmts:
            compile_named(s)

    assert calls == []
    compile_named.cache_clear()
