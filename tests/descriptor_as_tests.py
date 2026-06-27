"""
Tests for Descriptor.as_int / as_float / as_bool / as_str / as_datetime / as_enum

Each section covers:
  - native-typed values stored directly in the dict
  - string coercion (parseable and unparsable)
  - missing path  → default
  - verbatim=True  → variable expressions are NOT expanded
  - verbatim=False (default) → variable expressions ARE expanded using sibling keys
"""

import pytest
from datetime import datetime, timezone, timedelta
from enum import Enum

from azos.chassis import ConfigError
from azos.descriptor import Descriptor


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

DATA = {
    # integers
    "i_native":  42,
    "i_str":     "100",
    "i_str_bad": "not-a-number",
    "i_float":   3.7,         # not int, not str → default for as_int

    # floats
    "f_native":  3.14,
    "f_str":     "2.718",
    "f_str_bad": "abc",
    "f_int":     7,           # int → promoted to float

    # bools
    "b_native_t":  True,
    "b_native_f":  False,
    "b_int_t":     1,
    "b_int_f":     0,
    "b_int_big":   -99,
    "b_str_true":  "true",
    "b_str_True":  "True",
    "b_str_yes":   "YES",
    "b_str_on":    "On",
    "b_str_t":     "t",
    "b_str_y":     "y",
    "b_str_1":     "1",
    "b_str_false": "false",
    "b_str_no":    "NO",
    "b_str_off":   "off",
    "b_str_f":     "f",
    "b_str_n":     "n",
    "b_str_0":     "0",
    "b_str_bad":   "maybe",

    # strings / var interpolation
    "s_native":   "hello",
    "s_int":      123,
    "s_float":    1.5,
    "s_bool":     True,
    "s_none":     None,
    "greeting":   "Hello $(name)!",
    "name":       "Dodik",
    "chain_a":    "$(chain_b) world",
    "chain_b":    "hello",
    "verbatim_t": "$(name)",   # should stay literal under verbatim=True

    # datetimes
    "dt_native":      datetime(2024, 1, 15, 13, 45, 30),
    "dt_unix_int":    1705323930,          # 2024-01-15 13:45:30 UTC
    "dt_unix_float":  1705323930.5,
    "dt_iso_date":    "2024-01-15",
    "dt_iso_dt":      "2024-01-15T13:45:00",
    "dt_iso_z":       "2024-01-15T13:45:00Z",
    "dt_iso_offset":  "2024-01-15T13:45:00+05:00",
    "dt_us_date":     "01/15/2024",
    "dt_us_hhmm_24":  "01/15/2024 13:45",
    "dt_us_hhmmss_24":"01/15/2024 13:45:30",
    "dt_us_hhmm_pm":  "01/15/2024 01:45 PM",
    "dt_us_hhmmss_pm":"01/15/2024 01:45:30 PM",
    "dt_us_hhmm_am":  "01/15/2024 06:00 AM",
    "dt_str_bad":     "not-a-date",
    "dt_var":         "$(dt_iso_date)",  # expands to "2024-01-15"

    # enums
    "e_native": Color.GREEN,
    "e_int": 3,
    "e_str_int": "1",
    "e_str_name": "red",
    "e_str_name_case": "bLuE",
    "e_str_bad": "yellow",
    "e_int_bad": 99,
    "e_var": "$(e_str_name)",
}


@pytest.fixture
def desc() -> Descriptor:
    return Descriptor(DATA)


# ===========================================================================
# as_int
# ===========================================================================

class TestAsInt:
    def test_native_int(self, desc):
        """Integer stored directly is returned unchanged."""
        assert desc.as_int("i_native") == 42

    def test_string_parses_to_int(self, desc):
        """Numeric string is coerced to int."""
        assert desc.as_int("i_str") == 100

    def test_string_bad_returns_default(self, desc):
        """Non-numeric string returns the default."""
        assert desc.as_int("i_str_bad") is None
        assert desc.as_int("i_str_bad", default=-1) == -1

    def test_float_value_returns_rounded(self, desc):
        """Float stored natively is rounded to the nearest integer."""
        assert desc.as_int("f_native")  == 3

    def test_missing_path_returns_default(self, desc):
        """Completely absent key returns the default."""
        assert desc.as_int("no_such_key") is None
        assert desc.as_int("no_such_key", default=0) == 0

    def test_var_expression_expanded(self):
        """String containing $(ref) is resolved before int conversion."""
        d = Descriptor({"val": "$(src)", "src": "55"})
        assert d.as_int("val") == 55

    def test_verbatim_skips_expansion(self):
        """verbatim=True: $(src) is NOT expanded, parse fails → default."""
        d = Descriptor({"val": "$(src)", "src": "55"})
        assert d.as_int("val", verbatim=True) is None

    def test_default_value_returned_on_missing(self, desc):
        """Explicit default is returned when path is missing."""
        assert desc.as_int("missing", default=999) == 999


# ===========================================================================
# as_float
# ===========================================================================

class TestAsFloat:
    def test_native_float(self, desc):
        """Float stored directly is returned unchanged."""
        assert desc.as_float("f_native") == pytest.approx(3.14)

    def test_int_promoted_to_float(self, desc):
        """Integer is promoted to float."""
        result = desc.as_float("f_int")
        assert isinstance(result, float)
        assert result == 7.0

    def test_native_int_field_promoted(self, desc):
        """i_native (42) is also promoted."""
        assert desc.as_float("i_native") == 42.0

    def test_string_parses_to_float(self, desc):
        """Numeric float string is coerced."""
        assert desc.as_float("f_str") == pytest.approx(2.718)

    def test_string_bad_returns_default(self, desc):
        """Non-numeric string returns default."""
        assert desc.as_float("f_str_bad") is None
        assert desc.as_float("f_str_bad", default=-1.0) == -1.0

    def test_missing_path_returns_default(self, desc):
        assert desc.as_float("no_such_key") is None
        assert desc.as_float("no_such_key", default=0.0) == 0.0

    def test_var_expression_expanded(self):
        """$(ref) is resolved and then parsed as float."""
        d = Descriptor({"val": "$(src)", "src": "3.14"})
        assert d.as_float("val") == pytest.approx(3.14)

    def test_verbatim_skips_expansion(self):
        """verbatim=True: expression stays literal → parse fails → default."""
        d = Descriptor({"val": "$(src)", "src": "3.14"})
        assert d.as_float("val", verbatim=True) is None


# ===========================================================================
# as_bool
# ===========================================================================

class TestAsBool:
    def test_native_true(self, desc):
        assert desc.as_bool("b_native_t") is True

    def test_native_false(self, desc):
        assert desc.as_bool("b_native_f") is False

    def test_int_nonzero_is_true(self, desc):
        assert desc.as_bool("b_int_t") is True

    def test_int_zero_is_false(self, desc):
        assert desc.as_bool("b_int_f") is False

    def test_int_negative_is_true(self, desc):
        """Any non-zero int is truthy."""
        assert desc.as_bool("b_int_big") is True

    @pytest.mark.parametrize("key", [
        "b_str_true", "b_str_True", "b_str_yes", "b_str_on", "b_str_t", "b_str_y", "b_str_1",
    ])
    def test_truthy_strings(self, desc, key):
        """All recognised truthy strings return True."""
        assert desc.as_bool(key) is True

    @pytest.mark.parametrize("key", [
        "b_str_false", "b_str_no", "b_str_off", "b_str_f", "b_str_n", "b_str_0",
    ])
    def test_falsy_strings(self, desc, key):
        """All recognised falsy strings return False."""
        assert desc.as_bool(key) is False

    def test_unrecognised_string_returns_default(self, desc):
        assert desc.as_bool("b_str_bad") is None
        assert desc.as_bool("b_str_bad", default=False) is False

    def test_missing_path_returns_default(self, desc):
        assert desc.as_bool("missing") is None

    def test_var_expression_expanded_truthy(self):
        """$(ref) resolved to 'yes' → True."""
        d = Descriptor({"flag": "$(src)", "src": "yes"})
        assert d.as_bool("flag") is True

    def test_var_expression_expanded_falsy(self):
        """$(ref) resolved to 'off' → False."""
        d = Descriptor({"flag": "$(src)", "src": "off"})
        assert d.as_bool("flag") is False

    def test_verbatim_skips_expansion(self):
        """verbatim=True: $(src) treated literally → unrecognised → default."""
        d = Descriptor({"flag": "$(src)", "src": "yes"})
        assert d.as_bool("flag", verbatim=True) is None


# ===========================================================================
# as_str
# ===========================================================================

class TestAsStr:
    def test_native_string(self, desc):
        assert desc.as_str("s_native") == "hello"

    def test_int_converted_to_str(self, desc):
        assert desc.as_str("s_int") == "123"

    def test_float_converted_to_str(self, desc):
        assert desc.as_str("s_float") == "1.5"

    def test_bool_converted_to_str(self, desc):
        """Python str(True) == 'True'."""
        assert desc.as_str("s_bool") == "True"

    def test_none_returns_default(self, desc):
        """None value at path returns the default, not 'None'."""
        assert desc.as_str("s_none") is None
        assert desc.as_str("s_none", default="fallback") == "fallback"

    def test_missing_path_returns_default(self, desc):
        assert desc.as_str("missing") is None
        assert desc.as_str("missing", default="x") == "x"

    def test_var_expression_expanded(self, desc):
        """'Hello $(name)!' resolves to 'Hello Dodik!'."""
        assert desc.as_str("greeting") == "Hello Dodik!"

    def test_cross_key_reference(self, desc):
        """The user's canonical example: a references b, b is a sibling key."""
        d = Descriptor({"a": "Hello $(b)!", "b": "Dodik"})
        assert d.as_str("a") == "Hello Dodik!"

    def test_chained_var_expansion(self, desc):
        """chain_a → '$(chain_b) world', chain_b → 'hello' → 'hello world'."""
        assert desc.as_str("chain_a") == "hello world"

    def test_verbatim_true_no_expansion(self, desc):
        """verbatim=True: expression template is returned as-is."""
        assert desc.as_str("greeting", verbatim=True) == "Hello $(name)!"

    def test_verbatim_true_keeps_expr_token(self, desc):
        """verbatim on a plain $(name) ref returns the raw token."""
        assert desc.as_str("verbatim_t", verbatim=True) == "$(name)"

    def test_var_expression_deep_path(self):
        """Variable resolution works when the referenced key is nested."""
        d = Descriptor({
            "msg": "Value is $(cfg/timeout)",
            "cfg": {"timeout": "30"},
        })
        assert d.as_str("msg") == "Value is 30"

    def test_multiple_vars_in_one_string(self):
        """Multiple $(x) tokens in a single string are all expanded."""
        d = Descriptor({
            "tmpl": "$(first) and $(second)",
            "first": "foo",
            "second": "bar",
        })
        assert d.as_str("tmpl") == "foo and bar"


# ===========================================================================
# as_datetime
# ===========================================================================

class TestAsDatetime:
    def test_native_datetime(self, desc):
        """datetime object is returned unchanged."""
        assert desc.as_datetime("dt_native") == datetime(2024, 1, 15, 13, 45, 30)

    def test_unix_int_timestamp(self, desc):
        """Integer Unix timestamp is converted via utcfromtimestamp."""
        result = desc.as_datetime("dt_unix_int")
        assert result == datetime.fromtimestamp(1705323930, timezone.utc)

    def test_unix_float_timestamp(self, desc):
        """Float Unix timestamp is also accepted."""
        result = desc.as_datetime("dt_unix_float")
        assert result == datetime.fromtimestamp(1705323930.5, timezone.utc)

    def test_iso_date_only(self, desc):
        """ISO 8601 date-only string."""
        result = desc.as_datetime("dt_iso_date")
        assert result == datetime(2024, 1, 15)

    def test_iso_datetime(self, desc):
        """ISO 8601 datetime without timezone."""
        result = desc.as_datetime("dt_iso_dt")
        assert result == datetime(2024, 1, 15, 13, 45, 0)

    def test_iso_z_suffix(self, desc):
        """ISO 8601 with Z timezone suffix (Python 3.11+ fromisoformat handles Z)."""
        result = desc.as_datetime("dt_iso_z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 13
        assert result.minute == 45

    def test_iso_with_offset(self, desc):
        """ISO 8601 with UTC offset."""
        result = desc.as_datetime("dt_iso_offset")
        assert result is not None
        assert result.utcoffset() == timedelta(hours=5)

    def test_us_date_only(self, desc):
        """mm/dd/yyyy without time."""
        result = desc.as_datetime("dt_us_date")
        assert result == datetime(2024, 1, 15)

    def test_us_24h_hhmm(self, desc):
        """mm/dd/yyyy HH:MM 24-hour format."""
        result = desc.as_datetime("dt_us_hhmm_24")
        assert result == datetime(2024, 1, 15, 13, 45)

    def test_us_24h_hhmmss(self, desc):
        """mm/dd/yyyy HH:MM:SS 24-hour format."""
        result = desc.as_datetime("dt_us_hhmmss_24")
        assert result == datetime(2024, 1, 15, 13, 45, 30)

    def test_us_12h_pm(self, desc):
        """mm/dd/yyyy hh:MM PM 12-hour format."""
        result = desc.as_datetime("dt_us_hhmm_pm")
        assert result == datetime(2024, 1, 15, 13, 45)

    def test_us_12h_pm_with_seconds(self, desc):
        """mm/dd/yyyy hh:MM:SS PM 12-hour format."""
        result = desc.as_datetime("dt_us_hhmmss_pm")
        assert result == datetime(2024, 1, 15, 13, 45, 30)

    def test_us_12h_am(self, desc):
        """mm/dd/yyyy hh:MM AM 12-hour format."""
        result = desc.as_datetime("dt_us_hhmm_am")
        assert result == datetime(2024, 1, 15, 6, 0)

    def test_bad_string_returns_default(self, desc):
        """Unrecognized string returns default."""
        assert desc.as_datetime("dt_str_bad") is None
        assert desc.as_datetime("dt_str_bad", default=datetime(2000, 1, 1)) == datetime(2000, 1, 1)

    def test_missing_path_returns_default(self, desc):
        """Absent key returns default."""
        assert desc.as_datetime("no_such_key") is None

    def test_var_expression_expanded(self, desc):
        """$(dt_iso_date) resolves to '2024-01-15' and parses to a date."""
        result = desc.as_datetime("dt_var")
        assert result == datetime(2024, 1, 15)

    def test_verbatim_skips_expansion(self, desc):
        """verbatim=True: '$(dt_iso_date)' is NOT expanded → parse fails → default."""
        assert desc.as_datetime("dt_var", verbatim=True) is None

    def test_var_expression_resolves_to_us_date(self):
        """Variable that resolves to a US-format date string is parsed correctly."""
        d = Descriptor({"when": "$(raw_date)", "raw_date": "06/12/2026"})
        result = d.as_datetime("when")
        assert result == datetime(2026, 6, 12)


# ===========================================================================
# as_enum
# ===========================================================================

class TestAsEnum:
    def test_native_enum(self, desc):
        """Enum stored directly is returned unchanged."""
        assert desc.as_enum("e_native", Color) == Color.GREEN

    def test_int_value(self, desc):
        """Integer matching enum value is coerced."""
        assert desc.as_enum("e_int", Color) == Color.BLUE

    def test_str_int_value(self, desc):
        """String of integer matching enum value is coerced."""
        assert desc.as_enum("e_str_int", Color) == Color.RED

    def test_str_name(self, desc):
        """String matching enum name case-insensitively is coerced."""
        assert desc.as_enum("e_str_name", Color) == Color.RED
        assert desc.as_enum("e_str_name_case", Color) == Color.BLUE

    def test_bad_str_returns_default(self, desc):
        """Unrecognized string returns default."""
        assert desc.as_enum("e_str_bad", Color) is None
        assert desc.as_enum("e_str_bad", Color, default=Color.GREEN) == Color.GREEN

    def test_bad_int_returns_default(self, desc):
        """Unrecognized integer returns default."""
        assert desc.as_enum("e_int_bad", Color) is None
        assert desc.as_enum("e_int_bad", Color, default=Color.RED) == Color.RED

    def test_missing_path_returns_default(self, desc):
        """Absent key returns default."""
        assert desc.as_enum("no_such_key", Color) is None
        assert desc.as_enum("no_such_key", Color, default=Color.BLUE) == Color.BLUE

    def test_var_expression_expanded(self, desc):
        """$(e_str_name) resolves to 'red' and parses to Color.RED."""
        assert desc.as_enum("e_var", Color) == Color.RED

    def test_verbatim_skips_expansion(self, desc):
        """verbatim=True: '$(e_str_name)' is NOT expanded → parse fails → default."""
        assert desc.as_enum("e_var", Color, verbatim=True) is None


# ===========================================================================
# Circular / deep variable reference chains
# ===========================================================================

class TestCircularAndChainedVarRefs:
    def test_direct_self_reference_raises(self):
        """a → $(a): single-key self-loop must raise ConfigError."""
        d = Descriptor({"a": "$(a)"})
        with pytest.raises(ConfigError):
            d.as_str("a")

    def test_two_key_cycle_raises(self):
        """a → $(b), b → $(a): two-node cycle must raise ConfigError."""
        d = Descriptor({"a": "$(b)", "b": "$(a)"})
        with pytest.raises(ConfigError):
            d.as_str("a")

    def test_longer_cycle_raises(self):
        """a→b→c→d→f→a: five-node cycle must raise ConfigError."""
        d = Descriptor({
            "a": "$(b)",
            "b": "$(c)",
            "c": "$(d)",
            "d": "$(f)",
            "f": "$(a)",
        })
        with pytest.raises(ConfigError):
            d.as_str("a")

    def test_deep_non_circular_chain_resolves(self):
        """a→b→c→d→f→'end': a valid deep chain (no cycle) must resolve fully."""
        d = Descriptor({
            "a": "$(b)",
            "b": "$(c)",
            "c": "$(d)",
            "d": "$(f)",
            "f": "end",
        })
        assert d.as_str("a") == "end"

    def test_two_key_chain_resolves(self):
        """a → $(b), b → 'value': simplest non-trivial chain resolves."""
        d = Descriptor({"a": "$(b)", "b": "value"})
        assert d.as_str("a") == "value"

    def test_chain_with_prefix_and_suffix(self):
        """Interpolation around the token: 'pre-$(b)-suf' through a chain."""
        d = Descriptor({
            "a": "pre-$(b)-suf",
            "b": "$(c)",
            "c": "mid",
        })
        assert d.as_str("a") == "pre-mid-suf"

    def test_cycle_detected_from_middle_of_chain(self):
        """x→a, and a→b→a forms a cycle; resolving from x must still raise."""
        d = Descriptor({
            "x": "start $(a) end",
            "a": "$(b)",
            "b": "$(a)",
        })
        with pytest.raises(ConfigError):
            d.as_str("x")
