"""
Tests for override_dict() function in azos.descriptor
"""
import pytest
from azos.chassis import ConfigError
from azos.descriptor import override_dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def od(base, override, **kw):
    """Convenience wrapper: mutates base and returns it."""
    override_dict(base, override, **kw)
    return base


# ===========================================================================
# Basic scalar merging
# ===========================================================================

class TestScalarMerge:
    def test_01_empty_override_leaves_base_unchanged(self):
        """Empty override dict keeps all base keys intact"""
        base = {"a": 1, "b": 2}
        assert od(base, {}) == {"a": 1, "b": 2}

    def test_02_empty_base_gets_all_override_keys(self):
        """All override keys are copied into empty base"""
        base = {}
        assert od(base, {"x": 10, "y": 20}) == {"x": 10, "y": 20}

    def test_03_override_replaces_existing_scalar(self):
        """An existing scalar value is replaced by the override value"""
        base = {"a": 1}
        assert od(base, {"a": 99}) == {"a": 99}

    def test_04_override_adds_new_key(self):
        """A key present only in override is added to base"""
        base = {"a": 1}
        assert od(base, {"b": 2}) == {"a": 1, "b": 2}

    def test_05_both_existing_and_new_keys(self):
        """Mix of existing replacement and new addition"""
        base = {"a": 1, "b": 2}
        assert od(base, {"b": 99, "c": 3}) == {"a": 1, "b": 99, "c": 3}

    def test_06_mutates_base_in_place(self):
        """Returns None and mutates base, does not create a new dict"""
        base = {"a": 1}
        result = override_dict(base, {"a": 2})
        assert result is None
        assert base["a"] == 2

    def test_07_override_value_none(self):
        """None is a valid override value"""
        base = {"a": 1}
        assert od(base, {"a": None}) == {"a": None}

    def test_08_override_value_false(self):
        """False is a valid override value (not confused with missing)"""
        base = {"flag": True}
        assert od(base, {"flag": False}) == {"flag": False}

    def test_09_override_value_zero(self):
        """Zero is a valid override value"""
        base = {"count": 5}
        assert od(base, {"count": 0}) == {"count": 0}

    def test_10_string_overrides_string(self):
        """String replacing a string"""
        base = {"name": "alice"}
        assert od(base, {"name": "bob"}) == {"name": "bob"}


# ===========================================================================
# Recursive dict merging
# ===========================================================================

class TestRecursiveDictMerge:
    def test_01_nested_dict_merges_key_by_key(self):
        """Nested dicts are merged recursively, not replaced wholesale"""
        base = {"cfg": {"a": 1, "b": 2}}
        assert od(base, {"cfg": {"b": 99}}) == {"cfg": {"a": 1, "b": 99}}

    def test_02_nested_dict_adds_new_subkey(self):
        """New key inside nested dict is added"""
        base = {"cfg": {"a": 1}}
        assert od(base, {"cfg": {"z": 9}}) == {"cfg": {"a": 1, "z": 9}}

    def test_03_deeply_nested_merge(self):
        """Three levels of nesting merge correctly"""
        base = {"l1": {"l2": {"l3": {"x": 1, "y": 2}}}}
        assert od(base, {"l1": {"l2": {"l3": {"y": 99, "z": 3}}}}) == \
               {"l1": {"l2": {"l3": {"x": 1, "y": 99, "z": 3}}}}

    def test_04_sibling_keys_untouched(self):
        """Keys not mentioned in override are left intact at every level"""
        base = {"a": {"x": 1, "y": 2}, "b": 42}
        assert od(base, {"a": {"x": 10}}) == {"a": {"x": 10, "y": 2}, "b": 42}

    def test_05_type_mismatch_dict_over_list_replaces(self):
        """Override dict where base has list replaces base"""
        base = {"items": [1, 2, 3]}
        assert od(base, {"items": {"a": 1}}) == {"items": {"a": 1}}

    def test_06_type_mismatch_list_over_dict_replaces(self):
        """Override list where base has dict replaces base"""
        base = {"cfg": {"a": 1}}
        assert od(base, {"cfg": [1, 2]}) == {"cfg": [1, 2]}

    def test_07_type_mismatch_nested_replaces(self):
        """Nested mismatch replaces base"""
        base = {"outer": {"inner": {"val": [1, 2]}}}
        assert od(base, {"outer": {"inner": {"val": {"x": 1}}}}) == {"outer": {"inner": {"val": {"x": 1}}}}

    def test_08_override_pragma_key_in_override_is_merged_normally(self):
        """_override key in the override dict is treated as a regular key and merged into base"""
        base = {"a": 1}
        od(base, {"a": 2, "_override": "stop"})
        # The pragma is read from BASE; _override in override is just a regular key copy
        assert base["a"] == 2
        assert base["_override"] == "stop"  # now set on base for future overrides

    def test_09_scalar_over_scalar_in_nested(self):
        """Scalar in nested dict is replaced"""
        base = {"settings": {"timeout": 30, "retries": 3}}
        assert od(base, {"settings": {"timeout": 60}}) == \
               {"settings": {"timeout": 60, "retries": 3}}

    def test_10_new_nested_dict_added(self):
        """Entirely new nested dict from override is added to base"""
        base = {"a": 1}
        assert od(base, {"sub": {"x": 9}}) == {"a": 1, "sub": {"x": 9}}


# ===========================================================================
# Override pragmas (stop / fail / replace / merge)
# ===========================================================================

class TestOverridePragmas:
    def test_01_pragma_stop_keeps_base_unchanged(self):
        """pragma='stop' prevents any overriding"""
        base = {"_override": "stop", "a": 1}
        assert od(base, {"a": 99, "b": 2}) == {"_override": "stop", "a": 1}

    def test_02_pragma_fail_raises_config_error(self):
        """pragma='fail' raises ConfigError on any override attempt"""
        base = {"_override": "fail", "a": 1}
        with pytest.raises(ConfigError):
            override_dict(base, {"a": 99})

    def test_03_pragma_fail_error_includes_path(self):
        """pragma='fail' error message includes the path"""
        base = {"_override": "fail", "a": 1}
        with pytest.raises(ConfigError) as exc:
            override_dict(base, {"a": 99}, path="root/section")
        assert "root/section" in str(exc.value)

    def test_04_pragma_replace_clears_and_replaces(self):
        """pragma='replace' wipes base and copies all override keys"""
        base = {"_override": "replace", "a": 1, "b": 2}
        assert od(base, {"c": 3}) == {"c": 3}

    def test_05_pragma_replace_does_not_retain_old_keys(self):
        """After replace, no old base keys remain"""
        base = {"_override": "replace", "x": 10, "y": 20}
        od(base, {"z": 30})
        assert "x" not in base
        assert "y" not in base

    def test_06_pragma_merge_is_default(self):
        """Absent pragma behaves as merge"""
        base = {"a": 1, "b": 2}
        assert od(base, {"b": 99, "c": 3}) == {"a": 1, "b": 99, "c": 3}

    def test_07_pragma_merge_explicit(self):
        """Explicit pragma='merge' behaves as merge"""
        base = {"_override": "merge", "a": 1}
        assert od(base, {"a": 99}) == {"_override": "merge", "a": 99}

    def test_08_custom_pragma_key(self):
        """Custom override_pragma key name works correctly"""
        base = {"__mode": "stop", "a": 1}
        assert od(base, {"a": 99}, override_pragma="__mode") == {"__mode": "stop", "a": 1}

    def test_09_nested_pragma_stop(self):
        """pragma='stop' on a nested dict prevents that subtree from being overridden"""
        base = {"outer": {"_override": "stop", "x": 1}, "other": 5}
        od(base, {"outer": {"x": 99}, "other": 50})
        assert base["outer"]["x"] == 1   # stopped
        assert base["other"] == 50       # other key still merges

    def test_10_nested_pragma_replace(self):
        """pragma='replace' on a nested dict replaces only that subtree"""
        base = {"outer": {"_override": "replace", "x": 1, "y": 2}, "keep": 7}
        od(base, {"outer": {"z": 3}, "keep": 77})
        assert base["outer"] == {"z": 3}
        assert base["keep"] == 77


# ===========================================================================
# List merging – append
# ===========================================================================

class TestListAppend:
    def test_01_scalars_appended(self):
        """Scalar override items are appended to base list"""
        base = {"tags": ["a", "b"]}
        assert od(base, {"tags": ["c"]}) == {"tags": ["a", "b", "c"]}

    def test_02_multiple_scalars_appended(self):
        """Multiple scalars all get appended"""
        base = {"ids": [1, 2]}
        assert od(base, {"ids": [3, 4, 5]}) == {"ids": [1, 2, 3, 4, 5]}

    def test_03_dict_item_without_key_appended(self):
        """Dict item lacking list_item_key is appended"""
        base = {"items": [{"val": 1}]}
        assert od(base, {"items": [{"val": 2}]}) == {"items": [{"val": 1}, {"val": 2}]}

    def test_04_empty_override_list_no_change(self):
        """Empty override list leaves base list unchanged"""
        base = {"tags": ["a", "b"]}
        assert od(base, {"tags": []}) == {"tags": ["a", "b"]}

    def test_05_empty_base_list_gets_override_items(self):
        """Override appends into empty base list"""
        base = {"tags": []}
        assert od(base, {"tags": ["x", "y"]}) == {"tags": ["x", "y"]}

    def test_06_list_in_new_key_added_as_is(self):
        """List for a key absent from base is added directly"""
        base = {}
        assert od(base, {"tags": [1, 2, 3]}) == {"tags": [1, 2, 3]}

    def test_07_base_list_object_identity_preserved(self):
        """The original list object in base is mutated, not replaced"""
        original_list = [1, 2]
        base = {"items": original_list}
        override_dict(base, {"items": [3]})
        assert base["items"] is original_list

    def test_08_none_scalar_appended(self):
        """None is a valid list item and gets appended"""
        base = {"vals": [1]}
        assert od(base, {"vals": [None]}) == {"vals": [1, None]}


# ===========================================================================
# List merging – clear pragma
# ===========================================================================

class TestListClearPragma:
    def test_01_clear_pragma_wipes_base_list(self):
        """_clear sentinel causes base list to be cleared before merging"""
        base = {"tags": ["a", "b", "c"]}
        assert od(base, {"tags": ["_clear", "x"]}) == {"tags": ["x"]}

    def test_02_clear_pragma_alone_leaves_empty_list(self):
        """_clear alone (no following items) results in empty list"""
        base = {"tags": ["a", "b"]}
        assert od(base, {"tags": ["_clear"]}) == {"tags": []}

    def test_03_clear_pragma_sentinel_not_in_result(self):
        """The _clear sentinel value itself is never present in the result"""
        base = {"tags": ["a"]}
        od(base, {"tags": ["_clear", "b"]})
        assert "_clear" not in base["tags"]

    def test_04_clear_pragma_in_middle_still_clears(self):
        """_clear anywhere in the override list triggers a clear"""
        base = {"tags": ["a", "b"]}
        assert od(base, {"tags": ["x", "_clear", "y"]}) == {"tags": ["x", "y"]}

    def test_05_custom_clear_pragma_value(self):
        """Custom clear_list_pragma value works correctly"""
        base = {"tags": ["a", "b"]}
        assert od(base, {"tags": ["__RESET__", "z"]}, clear_list_pragma="__RESET__") == {"tags": ["z"]}

    def test_06_default_clear_not_triggered_by_other_values(self):
        """Values similar to but not equal to _clear do not trigger clear"""
        base = {"tags": ["a"]}
        assert od(base, {"tags": ["_Clear", "_CLEAR", "__clear"]}) == \
               {"tags": ["a", "_Clear", "_CLEAR", "__clear"]}


# ===========================================================================
# List merging – keyed item replacement
# ===========================================================================

class TestListKeyedReplacement:
    def test_01_item_with_matching_key_is_replaced(self):
        """Dict item whose list_item_key matches an existing item replaces it"""
        base = {"items": [{"name": "a", "v": 1}, {"name": "b", "v": 2}]}
        od(base, {"items": [{"name": "b", "v": 99}]})
        assert base["items"] == [{"name": "a", "v": 1}, {"name": "b", "v": 99}]

    def test_02_item_with_no_match_is_appended(self):
        """Dict item with list_item_key not found in base is appended"""
        base = {"items": [{"name": "a", "v": 1}]}
        od(base, {"items": [{"name": "z", "v": 9}]})
        assert base["items"] == [{"name": "a", "v": 1}, {"name": "z", "v": 9}]

    def test_03_first_matching_item_is_replaced(self):
        """Only the first matching item gets replaced"""
        base = {"items": [{"name": "a", "v": 1}, {"name": "a", "v": 2}]}
        od(base, {"items": [{"name": "a", "v": 99}]})
        assert base["items"][0] == {"name": "a", "v": 99}
        assert base["items"][1] == {"name": "a", "v": 2}

    def test_04_multiple_keyed_replacements(self):
        """Multiple keyed replacements in one override all apply correctly"""
        base = {"items": [{"name": "a", "v": 1}, {"name": "b", "v": 2}, {"name": "c", "v": 3}]}
        od(base, {"items": [{"name": "c", "v": 30}, {"name": "a", "v": 10}]})
        assert {"name": "a", "v": 10} in base["items"]
        assert {"name": "c", "v": 30} in base["items"]
        assert {"name": "b", "v": 2} in base["items"]

    def test_05_custom_list_item_key(self):
        """Custom list_item_key parameter is respected"""
        base = {"items": [{"id": 1, "x": "old"}]}
        od(base, {"items": [{"id": 1, "x": "new"}]}, list_item_key="id")
        assert base["items"] == [{"id": 1, "x": "new"}]

    def test_06_mix_keyed_and_plain_items(self):
        """Mix of keyed-replacement items and plain scalars in same override"""
        base = {"items": [{"name": "a", "v": 1}], "tags": ["x"]}
        od(base, {"items": [{"name": "a", "v": 9}], "tags": ["y"]})
        assert base["items"] == [{"name": "a", "v": 9}]
        assert base["tags"] == ["x", "y"]

    def test_07_clear_then_keyed_replacement(self):
        """_clear followed by keyed items starts fresh"""
        base = {"items": [{"name": "old", "v": 0}]}
        od(base, {"items": ["_clear", {"name": "new", "v": 1}]})
        assert base["items"] == [{"name": "new", "v": 1}]

    def test_08_item_missing_key_appended_even_if_match_possible(self):
        """Dict item without list_item_key is always appended regardless of content"""
        base = {"items": [{"name": "a", "v": 1}]}
        od(base, {"items": [{"v": 1}]})  # no 'name' key → append
        assert len(base["items"]) == 2


# ===========================================================================
# Combined / integration scenarios
# ===========================================================================

class TestCombined:
    def test_01_nested_dict_with_list(self):
        """Nested dict containing a list merges both correctly"""
        base = {
            "server": {
                "host": "localhost",
                "ports": [8080, 8081],
            }
        }
        od(base, {"server": {"host": "prod.example.com", "ports": [9090]}})
        assert base == {
            "server": {
                "host": "prod.example.com",
                "ports": [8080, 8081, 9090],
            }
        }

    def test_02_list_of_dicts_with_nested_merge(self):
        """List item keyed replacement combined with nested dict override"""
        base = {
            "plugins": [
                {"name": "auth", "enabled": True, "cfg": {"timeout": 30}},
                {"name": "cache", "enabled": True},
            ]
        }
        # Replace the "auth" plugin entry wholesale (keyed replacement, not recursive merge)
        od(base, {"plugins": [{"name": "auth", "enabled": False, "cfg": {"timeout": 60}}]})
        auth = next(p for p in base["plugins"] if p["name"] == "auth")
        assert auth == {"name": "auth", "enabled": False, "cfg": {"timeout": 60}}

    def test_03_deep_mixed_structure(self):
        """Multi-level merge of scalars, dicts, and lists"""
        base = {
            "a": 1,
            "b": {"x": 10, "y": [1, 2]},
            "c": [{"name": "item1", "val": 0}],
        }
        override = {
            "a": 2,
            "b": {"x": 20, "y": [3]},
            "c": [{"name": "item1", "val": 99}, {"name": "item2", "val": 5}],
        }
        od(base, override)
        assert base["a"] == 2
        assert base["b"] == {"x": 20, "y": [1, 2, 3]}
        assert {"name": "item1", "val": 99} in base["c"]
        assert {"name": "item2", "val": 5} in base["c"]

    def test_04_pragma_replace_nested_with_list(self):
        """replace pragma on nested dict discards old list too"""
        base = {
            "cfg": {
                "_override": "replace",
                "items": [1, 2, 3],
                "flag": True,
            }
        }
        od(base, {"cfg": {"items": [9]}})
        assert base["cfg"] == {"items": [9]}

    def test_05_stop_nested_preserves_sibling_list(self):
        """stop on one nested dict doesn't affect sibling list key"""
        base = {
            "locked": {"_override": "stop", "val": 1},
            "tags": ["a"],
        }
        od(base, {"locked": {"val": 99}, "tags": ["b"]})
        assert base["locked"]["val"] == 1
        assert base["tags"] == ["a", "b"]

    def test_06_clear_and_keyed_replacement_deep(self):
        """Clear + keyed replacement inside a nested dict works end-to-end"""
        base = {
            "env": {
                "vars": [
                    {"name": "HOST", "value": "localhost"},
                    {"name": "PORT", "value": "8080"},
                ]
            }
        }
        od(base, {"env": {"vars": ["_clear", {"name": "HOST", "value": "prod.host"}]}})
        assert base["env"]["vars"] == [{"name": "HOST", "value": "prod.host"}]

    def test_07_all_three_pragmas_in_one_structure(self):
        """stop, fail, and replace pragmas all work correctly in same top-level override"""
        base = {
            "locked": {"_override": "stop", "x": 1},
            "readonly": {"_override": "fail", "y": 2},
            "mutable": {"_override": "merge", "z": 3},
        }
        # Only mutable should be changed; locked stays, readonly raises
        od(base, {"locked": {"x": 99}, "mutable": {"z": 30}})
        assert base["locked"]["x"] == 1
        assert base["mutable"]["z"] == 30

        with pytest.raises(ConfigError):
            override_dict(base, {"readonly": {"y": 99}})

    def test_08_nested_type_mismatch_replaces(self):
        """Deeply nested type mismatch replaces base"""
        base = {"a": {"b": {"c": [1, 2, 3]}}}
        assert od(base, {"a": {"b": {"c": {"key": "val"}}}}) == {"a": {"b": {"c": {"key": "val"}}}}
