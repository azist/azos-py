"""
Dynamic data descriptors
"""

from datetime import datetime
from types import EllipsisType
from typing import Any

from azos.chassis import AppChassis, expand_var_expressions


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

    Arguments:
     - data: The underlying dictionary of the descriptor. If not provided, an empty dictionary will be used.
     - chassis: An optional AppChassis instance that can be used for evaluating variable expressions in the descriptor values.
    """
    def __init__(self, data: dict | None = None, chassis: AppChassis | None = None):
        self._data: dict = data if data is not None else {}
        self._chassis: AppChassis | None = chassis


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


    @property
    def chassis(self) -> AppChassis | None:
        """
        Returns the chassis associated with this descriptor, if any or None. The chassis is used for evaluating
        variable expressions in the descriptor values.
        """
        return self._chassis


    def try_navigate(self, path: str) -> tuple[bool, Any | None | EllipsisType]:
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


    def navigate(self, path: str) -> Any | None | EllipsisType:
        """
        Navigates the data using the given path. Returns the value associated with the path if it exists (including None),
        or ... to indicate that such path did not land at an existing descriptor node.
        """
        ok, value = self.try_navigate(path)
        return value if ok else ...


    def _var_resolver(self, var_name: str) -> tuple[bool, str]:
        # todo
        return True, ""


    def as_int(self, path: str, default: int | None = None, verbatim: bool = False) -> int | None:
        """
        Navigates to the given path and returns the value as an integer if possible, otherwise returns the default value.
        If verbatim is False and the value is a string, it will attempt to evaluate variable expressions in the string
        using the chassis before converting to int.
        """
        ok, value = self.try_navigate(path)
        if not ok:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            if not verbatim:
                # value = eval(value)  EVALUATE string
                value = expand_var_expressions(value, resolver=self._var_resolver, chassis=self._chassis)
                if value is None:
                    return default
            try:
                return int(value)
            except ValueError:
                return default
        return default


    def as_float(self, path: str, default: float | None = None, verbatim: bool = False) -> float | None:
        """
        Navigates to the given path and returns the value as a float if possible, otherwise returns the default value.
        If verbatim is False and the value is a string, it will attempt to evaluate variable expressions in the string
        using the chassis before converting to float.
        """
        ok, value = self.try_navigate(path)
        if not ok:
            return default
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if isinstance(value, str):
            if not verbatim:
                value = expand_var_expressions(value, resolver=self._var_resolver, chassis=self._chassis)
                if value is None:
                    return default
            try:
                return float(value)
            except ValueError:
                return default
        return default


    _BOOL_TRUE  = frozenset(("true", "yes", "on",  "1", "t", "y"))
    _BOOL_FALSE = frozenset(("false", "no",  "off", "0", "f", "n"))

    def as_bool(self, path: str, default: bool | None = None, verbatim: bool = False) -> bool | None:
        """
        Navigates to the given path and returns the value as a bool if possible, otherwise returns the default value.
        Strings are matched case-insensitively: truthy words (true/yes/on/1/t/y) and falsy words (false/no/off/0/f/n).
        Non-zero integers are True, zero is False.
        If verbatim is False and the value is a string, variable expressions are expanded before conversion.
        """
        ok, value = self.try_navigate(path)
        if not ok:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            if not verbatim:
                value = expand_var_expressions(value, resolver=self._var_resolver, chassis=self._chassis)
                if value is None:
                    return default
            lv = value.strip().lower()
            if lv in Descriptor._BOOL_TRUE:
                return True
            if lv in Descriptor._BOOL_FALSE:
                return False
        return default


    def as_str(self, path: str, default: str | None = None, verbatim: bool = False) -> str | None:
        """
        Navigates to the given path and returns the value as a string if possible, otherwise returns the default value.
        If verbatim is False and the value is a string, variable expressions are expanded before returning.
        Non-string values are converted via str().
        """
        ok, value = self.try_navigate(path)
        if not ok:
            return default
        if value is None:
            return default
        if isinstance(value, str):
            if not verbatim:
                expanded = expand_var_expressions(value, resolver=self._var_resolver, chassis=self._chassis)
                return expanded if expanded is not None else default
            return value
        return str(value)


    # ISO 8601 variants tried via datetime.fromisoformat() (Python 3.11+ handles Z suffix natively).
    # US date/time patterns tried in order from most specific to least specific.
    _US_DT_FORMATS = (
        "%m/%d/%Y %I:%M:%S %p",  # 01/15/2024 01:45:30 PM
        "%m/%d/%Y %I:%M %p",     # 01/15/2024 01:45 PM
        "%m/%d/%Y %H:%M:%S",     # 01/15/2024 13:45:30
        "%m/%d/%Y %H:%M",        # 01/15/2024 13:45
        "%m/%d/%Y",              # 01/15/2024
    )

    def as_datetime(self, path: str, default: datetime | None = None, verbatim: bool = False) -> datetime | None:
        """
        Navigates to the given path and returns the value as a datetime if possible, otherwise returns the default value.

        Accepts:
         - A datetime object directly.
         - An int or float treated as a Unix timestamp (UTC seconds).
         - A string in ISO 8601 format (e.g. "2024-01-15", "2024-01-15T13:45:00", "2024-01-15T13:45:00Z",
           "2024-01-15T13:45:00+05:00").
         - A string in common US formats: "mm/dd/yyyy", "mm/dd/yyyy HH:MM", "mm/dd/yyyy HH:MM:SS",
           "mm/dd/yyyy hh:MM AM/PM", "mm/dd/yyyy hh:MM:SS AM/PM".

        If verbatim is False and the value is a string, variable expressions are expanded before conversion.
        """
        ok, value = self.try_navigate(path)
        if not ok:
            return default
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.utcfromtimestamp(value)
            except (OSError, OverflowError, ValueError):
                return default
        if isinstance(value, str):
            if not verbatim:
                value = expand_var_expressions(value, resolver=self._var_resolver, chassis=self._chassis)
                if value is None:
                    return default
            s = value.strip()
            # Try ISO 8601 first (handles dates, datetimes, timezone offsets, and Z)
            try:
                return datetime.fromisoformat(s)
            except ValueError:
                pass
            # Try US formats
            for fmt in Descriptor._US_DT_FORMATS:
                try:
                    return datetime.strptime(s, fmt)
                except ValueError:
                    continue
        return default
