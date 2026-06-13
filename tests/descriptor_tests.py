"""
Tests for azos.descriptor.Descriptor — try_navigate / navigate / __contains__ / __getitem__
and the override_dict helper.
"""

import pytest
from azos.descriptor import Descriptor, override_dict


# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

def make_deep() -> dict:
    """Canonical nested structure used across many tests."""
    return {
        "a": {
            "b": {
                "c": "leaf",
                "d": None,
                "e": 0,
                "f": False,
            },
            "nums": [10, 20, 30, 40, 50],
            "items": [
                {"id": 1,   "name": "alpha"},
                {"id": 2,   "name": "beta"},
                {"id": 3,   "name": "gamma"},
                {"id": "x", "name": "delta"},
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


class SimpleObj:
    """Plain object for testing attribute-based $ navigation."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ===========================================================================
# 1. Construction
# ===========================================================================

class TestConstruction:
    def test_default_data_is_empty_dict(self):
        d = Descriptor()
        assert d.data == {}

    def test_none_becomes_empty_dict(self):
        d = Descriptor(None)
        assert d.data == {}

    def test_provided_dict_is_stored(self):
        raw = {"x": 1}
        d = Descriptor(raw)
        assert d.data is raw


# ===========================================================================
# 2. Empty / trivial paths
# ===========================================================================

class TestEmptyPath:
    def test_empty_string_returns_root(self):
        raw = {"x": 1}
        d = Descriptor(raw)
        ok, val = d.try_navigate("")
        assert ok is True
        assert val is raw

    def test_none_path_returns_root(self):
        """None is falsy so treated the same as empty."""
        raw = {"x": 1}
        d = Descriptor(raw)
        ok, val = d.try_navigate(None)
        assert ok is True
        assert val is raw

    def test_navigate_empty_returns_root(self):
        raw = {"x": 1}
        d = Descriptor(raw)
        assert d.navigate("") is raw

    def test_navigate_leading_slash_skips_empty_segment(self):
        d = Descriptor({"a": 1})
        assert d.navigate("/a") == 1

    def test_navigate_trailing_slash_is_ignored(self):
        d = Descriptor({"a": 1})
        assert d.navigate("a/") == 1

    def test_navigate_multiple_slashes_skipped(self):
        d = Descriptor({"a": {"b": 7}})
        assert d.navigate("a//b") == 7


# ===========================================================================
# 3. Simple dict key navigation
# ===========================================================================

class TestDictNavigation:
    def setup_method(self):
        self.d = Descriptor(make_deep())

    def test_single_top_level_key(self):
        ok, val = self.d.try_navigate("top")
        assert ok is True
        assert val == 42

    def test_two_levels(self):
        ok, val = self.d.try_navigate("a/b")
        assert ok is True
        assert isinstance(val, dict)

    def test_three_levels(self):
        ok, val = self.d.try_navigate("a/b/c")
        assert ok is True
        assert val == "leaf"

    def test_value_is_none_still_success(self):
        """None is a valid value; success must be True."""
        ok, val = self.d.try_navigate("none_val")
        assert ok is True
        assert val is None

    def test_value_is_zero_still_success(self):
        ok, val = self.d.try_navigate("zero_val")
        assert ok is True
        assert val == 0

    def test_value_is_false_still_success(self):
        ok, val = self.d.try_navigate("false_val")
        assert ok is True
        assert val is False

    def test_value_is_empty_string_still_success(self):
        ok, val = self.d.try_navigate("empty_str")
        assert ok is True
        assert val == ""

    def test_value_is_empty_list_still_success(self):
        ok, val = self.d.try_navigate("empty_list")
        assert ok is True
        assert val == []

    def test_value_is_empty_dict_still_success(self):
        ok, val = self.d.try_navigate("empty_dict")
        assert ok is True
        assert val == {}

    def test_nested_none_leaf(self):
        ok, val = self.d.try_navigate("a/b/d")
        assert ok is True
        assert val is None

    def test_nested_zero_leaf(self):
        ok, val = self.d.try_navigate("a/b/e")
        assert ok is True
        assert val == 0

    def test_nested_false_leaf(self):
        ok, val = self.d.try_navigate("a/b/f")
        assert ok is True
        assert val is False

    # --- Failures ---

    def test_missing_top_level_key(self):
        ok, val = self.d.try_navigate("missing")
        assert ok is False
        assert val is self.d.data  # partial: stayed at root

    def test_missing_nested_key(self):
        ok, val = self.d.try_navigate("a/b/NOPE")
        assert ok is False
        assert val == {"c": "leaf", "d": None, "e": 0, "f": False}  # partial: landed on a/b

    def test_key_on_non_dict_node(self):
        """'top' is an int; going deeper should fail."""
        ok, val = self.d.try_navigate("top/x")
        assert ok is False
        assert val == 42  # partial: landed on 'top'

    def test_key_on_list_node(self):
        """'a/nums' is a list; plain key navigation should fail."""
        ok, val = self.d.try_navigate("a/nums/foo")
        assert ok is False
        assert val == [10, 20, 30, 40, 50]  # partial: landed on 'a/nums'

    def test_key_on_none_leaf(self):
        ok, val = self.d.try_navigate("none_val/x")
        assert ok is False
        assert val is None  # partial: landed on None


# ===========================================================================
# 4. List index (#) navigation
# ===========================================================================

class TestIndexNavigation:
    def setup_method(self):
        self.d = Descriptor(make_deep())

    def test_first_element(self):
        ok, val = self.d.try_navigate("a/nums/#0")
        assert ok is True
        assert val == 10

    def test_last_element(self):
        ok, val = self.d.try_navigate("a/nums/#4")
        assert ok is True
        assert val == 50

    def test_middle_element(self):
        ok, val = self.d.try_navigate("a/nums/#2")
        assert ok is True
        assert val == 30

    def test_index_into_dict_items_list(self):
        ok, val = self.d.try_navigate("a/items/#1")
        assert ok is True
        assert val == {"id": 2, "name": "beta"}

    def test_chained_after_index(self):
        """Navigate into a dict element obtained via index."""
        ok, val = self.d.try_navigate("a/items/#0/name")
        assert ok is True
        assert val == "alpha"

    def test_index_out_of_bounds_positive(self):
        ok, val = self.d.try_navigate("a/nums/#99")
        assert ok is False
        assert val == [10, 20, 30, 40, 50]  # partial: landed on the list

    def test_index_zero_on_empty_list(self):
        ok, val = self.d.try_navigate("empty_list/#0")
        assert ok is False
        assert val == []  # partial: landed on the empty list

    def test_negative_index_fails(self):
        """Negative indices are not supported."""
        ok, val = self.d.try_navigate("a/nums/#-1")
        assert ok is False
        assert val == [10, 20, 30, 40, 50]  # partial: landed on the list

    def test_hash_on_non_list(self):
        """Applying # to a dict node should fail."""
        ok, val = self.d.try_navigate("a/#0")
        assert ok is False
        assert isinstance(val, dict)  # partial: landed on 'a' dict

    def test_hash_on_scalar(self):
        ok, val = self.d.try_navigate("top/#0")
        assert ok is False
        assert val == 42  # partial: landed on 'top'

    def test_hash_non_integer_suffix(self):
        ok, val = self.d.try_navigate("a/nums/#abc")
        assert ok is False
        assert val == [10, 20, 30, 40, 50]  # partial: landed on the list

    def test_hash_empty_suffix(self):
        ok, val = self.d.try_navigate("a/nums/#")
        assert ok is False
        assert val == [10, 20, 30, 40, 50]  # partial: landed on the list

    def test_hash_float_suffix(self):
        ok, val = self.d.try_navigate("a/nums/#1.5")
        assert ok is False
        assert val == [10, 20, 30, 40, 50]  # partial: landed on the list

    def test_deeply_nested_list_of_lists(self):
        d = Descriptor({"matrix": [[1, 2, 3], [4, 5, 6]]})
        ok, val = d.try_navigate("matrix/#1/#2")
        assert ok is True
        assert val == 6

    def test_index_then_missing_key(self):
        ok, val = self.d.try_navigate("a/items/#0/NOPE")
        assert ok is False
        assert val == {"id": 1, "name": "alpha"}  # partial: landed on items[0]


# ===========================================================================
# 5. Attribute search ($) navigation — dict items
# ===========================================================================

class TestAttrSearchDictNavigation:
    def setup_method(self):
        self.d = Descriptor(make_deep())

    def test_find_by_int_id(self):
        ok, val = self.d.try_navigate("a/items/$id=1")
        assert ok is True
        assert val is not ... and val is not None
        assert val["name"] == "alpha"

    def test_find_by_int_id_second_match(self):
        ok, val = self.d.try_navigate("a/items/$id=2")
        assert ok is True
        assert val is not ... and val is not None
        assert val["name"] == "beta"

    def test_find_by_string_id(self):
        """id="x" — value stored as string."""
        ok, val = self.d.try_navigate("a/items/$id=x")
        assert ok is True
        assert val is not ... and val is not None
        assert val["name"] == "delta"

    def test_find_by_name_attr(self):
        ok, val = self.d.try_navigate("a/items/$name=gamma")
        assert ok is True
        assert val is not ... and val is not None
        assert val["id"] == 3

    def test_returns_first_match_only(self):
        """When multiple items match, return the first one."""
        d = Descriptor({"lst": [{"k": "v", "n": 1}, {"k": "v", "n": 2}]})
        ok, val = d.try_navigate("lst/$k=v")
        assert ok is True
        assert val is not ... and val is not None
        assert val["n"] == 1

    def test_no_match_returns_ellipsis(self):
        ok, val = self.d.try_navigate("a/items/$id=999")
        assert ok is False
        assert isinstance(val, list)  # partial: landed on items list

    def test_attr_not_present_on_any_item(self):
        ok, val = self.d.try_navigate("a/items/$nonexistent=1")
        assert ok is False
        assert isinstance(val, list)  # partial: landed on items list

    def test_dollar_on_non_list(self):
        ok, val = self.d.try_navigate("a/b/$id=1")
        assert ok is False
        assert isinstance(val, dict)  # partial: landed on a/b dict

    def test_dollar_on_scalar(self):
        ok, val = self.d.try_navigate("top/$id=1")
        assert ok is False
        assert val == 42  # partial: landed on 'top'

    def test_dollar_missing_equals(self):
        ok, val = self.d.try_navigate("a/items/$id")
        assert ok is False
        assert isinstance(val, list)  # partial: landed on items list

    def test_dollar_only_equals_sign(self):
        """$=value — empty attribute name."""
        ok, val = self.d.try_navigate("a/items/$=1")
        assert ok is False
        assert isinstance(val, list)  # partial: landed on items list

    def test_dollar_empty_value(self):
        d = Descriptor({"lst": [{"k": ""}]})
        ok, val = d.try_navigate("lst/$k=")
        assert ok is True
        assert val is not ... and val is not None
        assert val == {"k": ""}

    def test_dollar_value_with_equals_inside(self):
        """Value part may itself contain '='."""
        d = Descriptor({"lst": [{"expr": "a=b"}]})
        ok, val = d.try_navigate("lst/$expr=a=b")
        assert ok is True
        assert val is not ... and val is not None
        assert val["expr"] == "a=b"

    def test_chained_after_dollar(self):
        ok, val = self.d.try_navigate("a/items/$id=3/name")
        assert ok is True
        assert val is not ... and val is not None
        assert val == "gamma"

    def test_dollar_on_empty_list(self):
        ok, val = self.d.try_navigate("empty_list/$id=1")
        assert ok is False
        assert val == []  # partial: landed on empty list


# ===========================================================================
# 6. Attribute search ($) navigation — plain objects
# ===========================================================================

class TestAttrSearchObjectNavigation:
    def setup_method(self):
        objs = [
            SimpleObj(id=10, role="admin"),
            SimpleObj(id=20, role="user"),
            SimpleObj(id=30, role="user"),
        ]
        self.d = Descriptor({"users": objs})

    def test_find_by_int_attr(self):
        ok, val = self.d.try_navigate("users/$id=20")
        assert ok is True
        assert val is not ... and val is not None
        assert val.role == "user"

    def test_find_first_of_duplicate_role(self):
        ok, val = self.d.try_navigate("users/$role=user")
        assert ok is True
        assert val is not ... and val is not None
        assert val.id == 20

    def test_no_match_on_objects(self):
        ok, val = self.d.try_navigate("users/$id=99")
        assert ok is False
        assert isinstance(val, list)  # partial: landed on users list

    def test_missing_attr_on_objects(self):
        ok, val = self.d.try_navigate("users/$email=x@x.com")
        assert ok is False
        assert isinstance(val, list)  # partial: landed on users list

    def test_chained_after_object_dollar_plain_key_fails(self):
        """
        Plain key segments require a dict node.  A SimpleObj is not a dict, so
        attempting to continue navigation with a plain key after landing on one
        must fail — this is correct, expected behaviour.
        """
        objs = [SimpleObj(id=1, nested={"deep": "found"})]
        d = Descriptor({"lst": objs})
        ok, val = d.try_navigate("lst/$id=1/nested/deep")
        assert ok is False
        assert isinstance(val, SimpleObj)  # partial: landed on the matched object

    def test_chained_after_dict_dollar(self):
        """After $-searching a dict item, further key navigation works fine."""
        d = Descriptor({"lst": [{"id": 1, "nested": {"deep": "found"}}]})
        ok, val = d.try_navigate("lst/$id=1/nested/deep")
        assert ok is True
        assert val == "found"


# ===========================================================================
# 7. Mixed navigation combinations
# ===========================================================================

class TestMixedNavigation:
    def test_key_then_index_then_key(self):
        d = Descriptor({"users": [{"name": "Alice"}, {"name": "Bob"}]})
        ok, val = d.try_navigate("users/#1/name")
        assert ok is True
        assert val == "Bob"

    def test_key_then_dollar_then_index(self):
        d = Descriptor({
            "groups": [
                {"id": "g1", "members": ["a", "b", "c"]},
                {"id": "g2", "members": ["x", "y"]},
            ]
        })
        ok, val = d.try_navigate("groups/$id=g2/members/#0")
        assert ok is True
        assert val == "x"

    def test_index_then_dollar_then_key(self):
        d = Descriptor({
            "matrix": [
                [{"k": 1, "v": "one"}, {"k": 2, "v": "two"}],
                [{"k": 3, "v": "three"}],
            ]
        })
        ok, val = d.try_navigate("matrix/#0/$k=2/v")
        assert ok is True
        assert val == "two"

    def test_deeply_nested_four_levels(self):
        d = Descriptor({"l1": {"l2": {"l3": {"l4": "deep"}}}})
        ok, val = d.try_navigate("l1/l2/l3/l4")
        assert ok is True
        assert val == "deep"

    def test_partial_path_wrong_midway(self):
        d = Descriptor({"a": {"b": [1, 2, 3]}})
        ok, val = d.try_navigate("a/b/c")  # b is a list, not a dict
        assert ok is False
        assert val == [1, 2, 3]  # partial: landed on 'a/b'

    def test_index_in_middle_of_path(self):
        d = Descriptor({"rows": [{"cells": ["x", "y", "z"]}]})
        ok, val = d.try_navigate("rows/#0/cells/#2")
        assert ok is True
        assert val == "z"


# ===========================================================================
# 8. navigate() wrapper (returns value or ...)
# ===========================================================================

class TestNavigate:
    def setup_method(self):
        self.d = Descriptor(make_deep())

    def test_success_returns_value(self):
        assert self.d.navigate("top") == 42

    def test_failure_returns_ellipsis(self):
        assert self.d.navigate("missing") is ...

    def test_none_value_returned_as_none(self):
        assert self.d.navigate("none_val") is None

    def test_false_value_returned_as_false(self):
        assert self.d.navigate("false_val") is False

    def test_zero_value_returned_as_zero(self):
        assert self.d.navigate("zero_val") == 0

    def test_nested_success(self):
        assert self.d.navigate("a/b/c") == "leaf"

    def test_nested_failure(self):
        assert self.d.navigate("a/b/NOPE") is ...

    def test_index_success(self):
        assert self.d.navigate("a/nums/#2") == 30

    def test_index_failure(self):
        assert self.d.navigate("a/nums/#100") is ...

    def test_dollar_success(self):
        result = self.d.navigate("a/items/$name=beta")
        assert result == {"id": 2, "name": "beta"}

    def test_dollar_failure(self):
        assert self.d.navigate("a/items/$id=999") is ...


# ===========================================================================
# 9. __getitem__ (d[path]) and __contains__ (path in d)
# ===========================================================================

class TestDunderMethods:
    def setup_method(self):
        self.d = Descriptor(make_deep())

    def test_getitem_success(self):
        assert self.d["top"] == 42

    def test_getitem_failure_returns_ellipsis(self):
        assert self.d["missing"] is ...

    def test_getitem_none_value(self):
        assert self.d["none_val"] is None

    def test_getitem_nested(self):
        assert self.d["a/b/c"] == "leaf"

    def test_getitem_index(self):
        assert self.d["a/nums/#0"] == 10

    def test_getitem_dollar(self):
        assert self.d["a/items/$id=1"] == {"id": 1, "name": "alpha"}

    def test_contains_existing_key(self):
        assert ("top" in self.d) is True

    def test_contains_missing_key(self):
        assert ("missing" in self.d) is False

    def test_contains_nested(self):
        assert ("a/b/c" in self.d) is True

    def test_contains_nested_missing(self):
        assert ("a/b/NOPE" in self.d) is False

    def test_contains_index(self):
        assert ("a/nums/#3" in self.d) is True

    def test_contains_index_oob(self):
        assert ("a/nums/#99" in self.d) is False

    def test_contains_dollar_match(self):
        assert ("a/items/$id=2" in self.d) is True

    def test_contains_dollar_no_match(self):
        assert ("a/items/$id=999" in self.d) is False

    def test_contains_none_value_is_true(self):
        """A key whose value is None still counts as present."""
        assert ("none_val" in self.d) is True

    def test_contains_false_value_is_true(self):
        assert ("false_val" in self.d) is True

    def test_contains_zero_value_is_true(self):
        assert ("zero_val" in self.d) is True


# ===========================================================================
# 10. Subclassing Descriptor
# ===========================================================================

class MyDescriptor(Descriptor):
    @property
    def top(self) -> int | None:
        v = self.navigate("top")
        return v if v is not ... else None


class TestSubclass:
    def test_typed_accessor(self):
        d = MyDescriptor({"top": 99})
        assert d.top == 99

    def test_typed_accessor_missing(self):
        d = MyDescriptor({})
        assert d.top is None

    def test_inherited_navigate(self):
        d = MyDescriptor({"x": {"y": 7}})
        assert d.navigate("x/y") == 7


# ===========================================================================
# 11. override_dict helper
# ===========================================================================

class TestOverrideDict:
    def test_shallow_override(self):
        base = {"a": 1, "b": 2}
        over = {"b": 99}
        result = override_dict(base, over)
        assert result == {"a": 1, "b": 99}

    def test_original_not_mutated_by_default(self):
        base = {"a": 1}
        over = {"a": 2}
        override_dict(base, over)
        assert base["a"] == 1

    def test_inplace_mutates_base(self):
        base = {"a": 1}
        over = {"a": 2}
        result = override_dict(base, over, inplace=True)
        assert base["a"] == 2
        assert result is base

    def test_deep_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        over = {"a": {"y": 99, "z": 3}}
        result = override_dict(base, over)
        assert result == {"a": {"x": 1, "y": 99, "z": 3}}

    def test_shallow_flag_replaces_nested_dict(self):
        base = {"a": {"x": 1}}
        over = {"a": {"y": 2}}
        result = override_dict(base, over, deep=False)
        assert result == {"a": {"y": 2}}

    def test_new_top_level_key_added(self):
        base = {"a": 1}
        over = {"b": 2}
        result = override_dict(base, over)
        assert result == {"a": 1, "b": 2}

    def test_override_with_none_value(self):
        base = {"a": 1}
        over = {"a": None}
        result = override_dict(base, over)
        assert result["a"] is None

    def test_empty_override_unchanged(self):
        base = {"a": 1}
        result = override_dict(base, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        result = override_dict({}, {"a": 1})
        assert result == {"a": 1}

    def test_returns_new_dict_not_base(self):
        base = {"a": 1}
        result = override_dict(base, {"b": 2})
        assert result is not base

    def test_deep_three_levels(self):
        base = {"l1": {"l2": {"l3": "orig"}}}
        over = {"l1": {"l2": {"l3": "new", "extra": True}}}
        result = override_dict(base, over)
        assert result == {"l1": {"l2": {"l3": "new", "extra": True}}}
