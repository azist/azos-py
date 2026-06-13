"""
Dynamic data descriptors
"""

from types import EllipsisType
from typing import Any


def override_dict(base: dict, override: dict, deep: bool = True, inplace: bool = False) -> dict:
    """
    Overrides the base dictionary with the values from the override dictionary. If deep is True, it will recursively
    override nested dictionaries. If inplace is True, it will modify the base dictionary in place and return it.
    Otherwise, it will create a copy of the base dictionary and return the modified copy.
    """
    result = base if inplace else base.copy()
    for key, value in override.items():
        if deep and isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = override_dict(result[key], value, deep=deep, inplace=inplace)
        else:
            result[key] = value
    return result


class Descriptor:
    """
    A descriptor is a wrapper around a dictionary of key-value pairs. It provides a convenient way
     to access and navigate various descriptor data structures, such as JWT claims, configuration sections, rulesets,
     or any other structured data that can be represented as a hierarchical dictionary.

    You can subclass `Descriptor` to create custom data fields and typed accessors and business logic for the underlying data,
    for example provide access to common JWT fields like `exp` and `iat` as `datetime` objects instead of raw timestamps.
    """
    def __init__(self, data: dict | None = None):
        self._data: dict = data if data is not None else {}

    def __getitem__(self, path) -> Any | None | EllipsisType:
        """Returns the value associated with the given key in the descriptor if it exists or ... to indicate that such key is not present"""
        return self.navigate(path)

    def __contains__(self, path):
        """Checks if the given path exists in the data"""
        ok, _ = self.try_navigate(path)
        return ok

    @property
    def data(self) -> dict:
        """Returns underlying raw data dictionary"""
        return self._data

    def try_navigate(self, path) -> tuple[bool, Any | None | EllipsisType]:
        """
        Tries to navigate the data using the given path as far as possible. Returns a tuple of (success, value) where
        success is a boolean indicating whether the navigation was successful navigating the whole path and value is the
        navigated value (including None) or ellipsis if nothing could be returned at all (e.g. the first key in the
          path is missing).

        Path segments are separated by "/":
          - Plain name: dictionary key lookup, e.g. "a/b/c"
          - "#N":       index into a list, e.g. "a/#3"
          - "$k=v":     find the first item in a list whose attribute/key "k" equals "v", e.g. "a/$id=123"
        """
        if not path:
            return True, self._data

        node: Any = self._data
        segments: list[str] = path.split("/")

        for seg in segments:
            if seg == "":
                continue  # skip empty segments produced by leading/trailing slashes

            if seg[0] == "#":
                # List index navigation
                if not isinstance(node, list):
                    return False, ...
                try:
                    idx = int(seg[1:])
                except ValueError:
                    return False, ...
                if idx < 0 or idx >= len(node):
                    return False, ...
                node = node[idx]

            elif seg[0] == "$":
                # Attribute search navigation: $key=value
                if not isinstance(node, list):
                    return False, ...
                eq = seg.find("=", 1)
                if eq < 0:
                    return False, ...
                attr = seg[1:eq]
                val = seg[eq + 1:]
                found = None
                found_flag = False
                for item in node:
                    # Support both dict items and objects with attributes
                    if isinstance(item, dict):
                        if attr in item and str(item[attr]) == val:
                            found = item
                            found_flag = True
                            break
                    else:
                        try:
                            if str(getattr(item, attr)) == val:
                                found = item
                                found_flag = True
                                break
                        except AttributeError:
                            pass
                if not found_flag:
                    return False, ...
                node = found

            else:
                # Plain dictionary key navigation
                if not isinstance(node, dict):
                    return False, ...
                if seg not in node:
                    return False, ...
                node = node[seg]

        return True, node

    def navigate(self, path) -> Any | None | EllipsisType:
        """
        Navigates the data using the given path. Returns the value associated with the path if it exists (including None),
        or ... to indicate that such path did not land at an existing descriptor node.
        """
        ok, value = self.try_navigate(path)
        return value if ok else ...

