"""
Tests for Descriptor.navigate() — exhaustive coverage of:
  - Plain (non-required) navigation:          "a/b"
  - Required-path navigation (value may be None): "!?a/b"
  - Required-value navigation (value must be set): "!a/b"

The three modes are all dispatched through a single entry-point method,
so these tests exercise its prefix-detection logic as well as the
underlying navigation helpers it delegates to.
"""

import pytest
from types import EllipsisType
from azos.descriptor import Descriptor
from azos.chassis import ConfigError


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

def make_data() -> dict:
    return {
        "a": {
            "b": {
                "c": "leaf",
                "d": None,
                "e": 0,
                "f": False,
                "g": "",
            },
            "nums": [10, 20, 30],
            "items": [
                {"id": 1, "name": "alpha"},
                {"id": 2, "name": "beta"},
            ],
        },
        "top": 42,
        "none_val": None,
        "zero_val": 0,
        "false_val": False,
        "empty_str": "",
        "empty_list": [],
        "empty_dict": {},
    }


# ===========================================================================
# 1.  Plain non-required navigation  ("a/b")
# ===========================================================================

class TestNavigatePlain:
    """navigate() with no prefix: returns value, None, or ... (Ellipsis)."""

    def test_plain_existing_string_value(self):
        """Existing path with a string value returns that string."""
        d = Descriptor(make_data())
        assert d.navigate("a/b/c") == "leaf"

    def test_plain_existing_int_value(self):
        """Existing path with an integer value returns that integer."""
        d = Descriptor(make_data())
        assert d.navigate("top") == 42

    def test_plain_existing_zero_value(self):
        """Falsy integer 0 is a legitimate value — must NOT return Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/b/e")
        assert result == 0
        assert result is not ...

    def test_plain_existing_false_value(self):
        """Falsy boolean False is a legitimate value — must NOT return Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/b/f")
        assert result is False
        assert result is not ...

    def test_plain_existing_empty_string_value(self):
        """Empty string is a legitimate value — must NOT return Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/b/g")
        assert result == ""
        assert result is not ...

    def test_plain_existing_none_value(self):
        """Path that exists with a None value returns None, NOT Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("none_val")
        assert result is None

    def test_plain_nested_none_value(self):
        """Deep path whose terminal value is None returns None."""
        d = Descriptor(make_data())
        result = d.navigate("a/b/d")
        assert result is None

    def test_plain_missing_top_level_key(self):
        """Missing top-level key returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("missing")
        assert result is ...

    def test_plain_missing_nested_key(self):
        """Missing key in an existing intermediate node returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/b/no_such_key")
        assert result is ...

    def test_plain_missing_intermediate_node(self):
        """Path where an intermediate segment does not exist returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/no_such/c")
        assert result is ...

    def test_plain_empty_path_returns_root(self):
        """Empty path returns the entire root dict."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("")
        assert result is data

    def test_plain_leading_slash_is_tolerated(self):
        """Leading slash should be tolerated (empty segment is skipped)."""
        d = Descriptor(make_data())
        assert d.navigate("/top") == 42

    def test_plain_trailing_slash_is_tolerated(self):
        """Trailing slash should be tolerated (empty trailing segment is skipped)."""
        d = Descriptor(make_data())
        assert d.navigate("top/") == 42

    def test_plain_dict_node_value(self):
        """Navigating to an intermediate dict node returns that dict."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("a/b")
        assert isinstance(result, dict)
        assert result is data["a"]["b"]

    def test_plain_list_node_value(self):
        """Navigating to a list node returns that list."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("a/nums")
        assert result == [10, 20, 30]

    def test_plain_empty_list_value(self):
        """Path whose value is an empty list returns []."""
        d = Descriptor(make_data())
        result = d.navigate("empty_list")
        assert result == []
        assert result is not ...

    def test_plain_empty_dict_value(self):
        """Path whose value is an empty dict returns {}."""
        d = Descriptor(make_data())
        result = d.navigate("empty_dict")
        assert result == {}
        assert result is not ...

    def test_plain_list_index_navigation(self):
        """#N segment navigates into a list by index."""
        d = Descriptor(make_data())
        assert d.navigate("a/nums/#0") == 10
        assert d.navigate("a/nums/#2") == 30

    def test_plain_list_index_out_of_range(self):
        """Out-of-range #N returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/nums/#99")
        assert result is ...

    def test_plain_list_index_on_non_list(self):
        """#N on a non-list node returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("top/#0")
        assert result is ...

    def test_plain_attribute_search_navigation(self):
        """$key=value finds first matching dict item in a list."""
        d = Descriptor(make_data())
        result = d.navigate("a/items/$name=alpha")
        assert isinstance(result, dict)
        assert result["id"] == 1

    def test_plain_attribute_search_second_item(self):
        """$key=value finds the second item when first does not match."""
        d = Descriptor(make_data())
        result = d.navigate("a/items/$id=2")
        assert result["name"] == "beta" # type: ignore

    def test_plain_attribute_search_no_match(self):
        """$key=value with no matching item returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("a/items/$name=ghost")
        assert result is ...

    def test_plain_returns_ellipsis_type(self):
        """The returned Ellipsis is the actual ... singleton (EllipsisType)."""
        d = Descriptor(make_data())
        result = d.navigate("does/not/exist")
        assert isinstance(result, EllipsisType)


# ===========================================================================
# 2.  Required-path navigation  ("!?a/b")
# ===========================================================================

class TestNavigateRequiredPath:
    """'!?' prefix: path must exist; value may be None; raises ConfigError if path missing."""

    def test_req_path_existing_string_value(self):
        """Existing path returns the string value unchanged."""
        d = Descriptor(make_data())
        assert d.navigate("!?a/b/c") == "leaf"

    def test_req_path_existing_int_value(self):
        """Existing path returns an integer value."""
        d = Descriptor(make_data())
        assert d.navigate("!?top") == 42

    def test_req_path_existing_zero_value(self):
        """Falsy 0 is a legitimate value."""
        d = Descriptor(make_data())
        assert d.navigate("!?a/b/e") == 0

    def test_req_path_existing_false_value(self):
        """Falsy False is a legitimate value."""
        d = Descriptor(make_data())
        assert d.navigate("!?a/b/f") is False

    def test_req_path_existing_empty_string_value(self):
        """Empty string is a legitimate value."""
        d = Descriptor(make_data())
        assert d.navigate("!?a/b/g") == ""

    def test_req_path_none_value_is_allowed(self):
        """'!?' does NOT raise when the path exists but the value is None."""
        d = Descriptor(make_data())
        result = d.navigate("!?none_val")
        assert result is None

    def test_req_path_nested_none_value_is_allowed(self):
        """'!?' does NOT raise for a deep None value."""
        d = Descriptor(make_data())
        result = d.navigate("!?a/b/d")
        assert result is None

    def test_req_path_missing_top_level_raises(self):
        """Missing top-level key with '!?' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!?missing")

    def test_req_path_missing_nested_key_raises(self):
        """Missing nested key with '!?' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!?a/b/no_such_key")

    def test_req_path_missing_intermediate_raises(self):
        """Missing intermediate segment with '!?' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!?a/no_such/c")

    def test_req_path_empty_path_after_prefix_returns_root(self):
        """'!?' with only the prefix (empty remainder) returns the root dict."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("!?")
        assert result is data

    def test_req_path_dict_node_value(self):
        """'!?' navigating to an intermediate dict returns that dict."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("!?a/b")
        assert result is data["a"]["b"]

    def test_req_path_list_node_value(self):
        """'!?' navigating to a list node returns that list."""
        d = Descriptor(make_data())
        result = d.navigate("!?a/nums")
        assert result == [10, 20, 30]

    def test_req_path_list_index_navigation(self):
        """'!?' works with #N list index segments."""
        d = Descriptor(make_data())
        assert d.navigate("!?a/nums/#1") == 20

    def test_req_path_list_index_out_of_range_raises(self):
        """'!?' with an out-of-range index raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!?a/nums/#99")

    def test_req_path_attribute_search_navigation(self):
        """'!?' works with $key=value attribute search segments."""
        d = Descriptor(make_data())
        result = d.navigate("!?a/items/$name=beta")
        assert result["id"] == 2 # type: ignore

    def test_req_path_attribute_search_no_match_raises(self):
        """'!?' with $key=value that matches nothing raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!?a/items/$name=ghost")

    def test_req_path_does_not_return_ellipsis(self):
        """'!?' never returns Ellipsis — it either returns a value or raises."""
        d = Descriptor(make_data())
        result = d.navigate("!?a/b/c")
        assert result is not ...


# ===========================================================================
# 3.  Required-value navigation  ("!a/b")
# ===========================================================================

class TestNavigateRequiredValue:
    """'!' prefix: path must exist AND value must not be None; raises ConfigError otherwise."""

    def test_req_val_existing_string_value(self):
        """Existing non-None string value is returned."""
        d = Descriptor(make_data())
        assert d.navigate("!a/b/c") == "leaf"

    def test_req_val_existing_int_value(self):
        """Existing non-None integer is returned."""
        d = Descriptor(make_data())
        assert d.navigate("!top") == 42

    def test_req_val_zero_is_allowed(self):
        """'!' does NOT raise for 0 — zero is not None."""
        d = Descriptor(make_data())
        assert d.navigate("!a/b/e") == 0

    def test_req_val_false_is_allowed(self):
        """'!' does NOT raise for False — False is not None."""
        d = Descriptor(make_data())
        assert d.navigate("!a/b/f") is False

    def test_req_val_empty_string_is_allowed(self):
        """'!' does NOT raise for empty string — "" is not None."""
        d = Descriptor(make_data())
        assert d.navigate("!a/b/g") == ""

    def test_req_val_none_value_raises(self):
        """Path exists but value is None → '!' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!none_val")

    def test_req_val_nested_none_value_raises(self):
        """Deep path whose value is None → '!' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!a/b/d")

    def test_req_val_missing_top_level_raises(self):
        """Missing top-level key with '!' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!missing")

    def test_req_val_missing_nested_key_raises(self):
        """Missing nested key with '!' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!a/b/no_such_key")

    def test_req_val_missing_intermediate_raises(self):
        """Missing intermediate segment with '!' raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!a/no_such/c")

    def test_req_val_empty_path_after_prefix_returns_root(self):
        """'!' with empty remainder returns the root dict (dict is not None)."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("!")
        assert result is data

    def test_req_val_dict_node_value(self):
        """'!' navigating to an intermediate dict returns that dict."""
        data = make_data()
        d = Descriptor(data)
        result = d.navigate("!a/b")
        assert result is data["a"]["b"]

    def test_req_val_list_node_value(self):
        """'!' navigating to a list node returns that list."""
        d = Descriptor(make_data())
        result = d.navigate("!a/nums")
        assert result == [10, 20, 30]

    def test_req_val_list_index_navigation(self):
        """'!' works with #N list index segments."""
        d = Descriptor(make_data())
        assert d.navigate("!a/nums/#0") == 10

    def test_req_val_list_index_out_of_range_raises(self):
        """'!' with an out-of-range index raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!a/nums/#99")

    def test_req_val_attribute_search_navigation(self):
        """'!' works with $key=value attribute search segments."""
        d = Descriptor(make_data())
        result = d.navigate("!a/items/$id=1")
        assert result["name"] == "alpha" # type: ignore

    def test_req_val_attribute_search_no_match_raises(self):
        """'!' with $key=value that matches nothing raises ConfigError."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!a/items/$name=ghost")

    def test_req_val_does_not_return_ellipsis(self):
        """'!' never returns Ellipsis — it either returns a value or raises."""
        d = Descriptor(make_data())
        result = d.navigate("!a/b/c")
        assert result is not ...


# ===========================================================================
# 4.  Prefix detection edge-cases & disambiguation
# ===========================================================================

class TestNavigatePrefixDetection:
    """Ensure prefix parsing is correct and the three modes are mutually exclusive."""

    def test_bang_question_is_req_path_not_req_value(self):
        """'!?' is required-path (None allowed), not required-value (would raise on None)."""
        d = Descriptor(make_data())
        # none_val exists but is None; '!?' must NOT raise
        result = d.navigate("!?none_val")
        assert result is None

    def test_bang_only_raises_on_none(self):
        """'!' raises on None while '!?' does not — confirms they are different modes."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!none_val")

    def test_plain_path_with_exclamation_in_middle_is_literal_key(self):
        """A '!' that is NOT at position 0 is treated as a plain key character, not a modifier."""
        data = {"a!b": "val"}
        d = Descriptor(data)
        # plain navigation — key literally contains '!'
        result = d.navigate("a!b")
        assert result == "val"

    def test_double_bang_is_not_a_modifier(self):
        """'!!' is not a recognised modifier — treated as a '!' prefix stripping one '!' before navigating."""
        data = {"!key": "val"}
        d = Descriptor(data)
        # '!!' -> strips one '!' -> navigates '!key' with navigate_required_value
        result = d.navigate("!!key")
        assert result == "val"

    def test_question_only_prefix_is_plain_navigation(self):
        """'?' alone is not a modifier — treated as a literal key character."""
        data = {"?key": "yes"}
        d = Descriptor(data)
        result = d.navigate("?key")
        assert result == "yes"

    def test_req_path_prefix_stripped_before_navigate(self):
        """The '!?' characters are stripped so the actual path used starts after them."""
        data = {"!?key": "literal", "key": "correct"}
        d = Descriptor(data)
        result = d.navigate("!?key")
        assert result == "correct"

    def test_req_value_prefix_stripped_before_navigate(self):
        """The '!' character is stripped so the actual path used starts after it."""
        data = {"!key": "literal", "key": "correct"}
        d = Descriptor(data)
        result = d.navigate("!key")
        assert result == "correct"

    def test_plain_missing_returns_ellipsis_not_raises(self):
        """Plain navigation never raises — missing path returns Ellipsis."""
        d = Descriptor(make_data())
        result = d.navigate("x/y/z")
        assert result is ...

    def test_req_path_and_req_value_both_raise_for_missing_path(self):
        """Both '!' and '!?' raise ConfigError when the path is absent."""
        d = Descriptor(make_data())
        with pytest.raises(ConfigError):
            d.navigate("!missing")
        with pytest.raises(ConfigError):
            d.navigate("!?missing")

    def test_all_three_modes_on_same_existing_non_none_path(self):
        """All three modes return the same value when path exists and value is not None."""
        d = Descriptor(make_data())
        path = "a/b/c"
        plain   = d.navigate(path)
        req_p   = d.navigate(f"!?{path}")
        req_v   = d.navigate(f"!{path}")
        assert plain == req_p == req_v == "leaf"

    def test_plain_vs_req_path_on_none_value(self):
        """Plain returns None; '!?' returns None; '!' raises — for an existing None value."""
        d = Descriptor(make_data())
        assert d.navigate("none_val") is None
        assert d.navigate("!?none_val") is None
        with pytest.raises(ConfigError):
            d.navigate("!none_val")

    def test_plain_vs_req_modes_on_missing_path(self):
        """Plain returns ...; both '!' and '!?' raise — for a missing path."""
        d = Descriptor(make_data())
        assert d.navigate("gone") is ...
        with pytest.raises(ConfigError):
            d.navigate("!gone")
        with pytest.raises(ConfigError):
            d.navigate("!?gone")
