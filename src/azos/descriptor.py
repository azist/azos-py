"""
Dynamic data descriptors
"""

from datetime import datetime, timezone
from types import EllipsisType
from typing import Any

from azos.chassis import AppChassis, ConfigError, expand_var_expressions


def override_dict(base: dict,
                  override: dict,
                  override_pragma: str = "_override",
                  clear_list_pragma: str = "_clear",
                  list_item_key: str = "name",
                  path: str = "") -> None:
    """
    Mutates the base dictionary by recursively overriding its items key-by-key with the values from the overriding dictionary.
    The system "merges" the overriding keys over the base, key-by-key recursively.
    If the value is a list, then the system merges items from the overriding list into the base list subject to list merging
    pragmas described below. If the overriding value does not match the collection type, such as dict overriding list or vice versa,
    the ConfigError is raised.

    The base dictionary can contain special pragmas to control the overriding behavior:

    - If a dictionary in the base contains the specified key by `override_pragma`, it will read the pragma value and
      apply it as follows:
      - If the pragma value is "replace", the value from override dictionary will completely replace the base dictionary
      - If the pragma value is "fail" an attempt to override this value will raise a ConfigError
      - If the pragma value is "stop" an attempt to override this value will be ignored and the base dictionary will be kept as is
      - If the pragma value is "merge" (the default) the overriding values will be merged key-by-key over existing values in the base dictionary (i.e. the default behavior)

    - If the overriding list value contains the value specified by `clear_list_pragma` it deletes all items form the list
    - If the list item is an object/dictionary and contains the specified key by `list_item_key`, the overriding item with the same
      value of this key will replace the base item with the same value of this key, otherwise the overriding item will be
      appended to the list

        Arguments:
            - base: The base dictionary to be mutated by overriding values from the override dictionary
            - override: The overriding dictionary whose values will be merged into the base dictionary
            - override_pragma: The key name for the overriding pragma in dictionaries (default "_override")
            - clear_list_pragma: The value in a list that indicates that the list should be cleared before merging (default "_clear")
            - list_item_key: The key name in list items that is used to match items for replacement (default "name")
            - path: The current path in the recursive override process, used for error messages (default "")
    """

    if base is None or override is None:
        raise ConfigError(f"override_dict(): base and override dictionaries must not be None at path '{path or '/'}'")

    pragma = base.get(override_pragma, "merge")

    if pragma == "stop":
        return

    if pragma == "fail":
        raise ConfigError(f"override_dict(): base dictionary at '{path or '/'}' is protected from overriding (pragma='fail')")

    if pragma == "replace":
        base.clear()
        base.update(override)
        return

    # "merge" (default)
    for key, ov_val in override.items():
        key_path = f"{path}/{key}" if path else key

        if key not in base:
            base[key] = ov_val
            continue

        base_val = base[key]
        if isinstance(base_val, dict):
            if not isinstance(ov_val, dict):
                raise ConfigError(f"override_dict(): type mismatch at '{key_path}': base is dict but override is {type(ov_val).__name__}")
            override_dict(base_val, ov_val, override_pragma, clear_list_pragma, list_item_key, key_path)

        elif isinstance(base_val, list):
            if not isinstance(ov_val, list):
                raise ConfigError(f"override_dict(): type mismatch at '{key_path}': base is list but override is {type(ov_val).__name__}")

            # Check for clear pragma in the override list
            ov_items = [item for item in ov_val if item != clear_list_pragma]
            if len(ov_items) < len(ov_val):  # _clear was present
                base_val.clear()

            # Merge overriding items into base list
            for ov_item in ov_items:
                if isinstance(ov_item, dict) and list_item_key in ov_item:
                    match_val = ov_item[list_item_key]
                    for i, base_item in enumerate(base_val):
                        if isinstance(base_item, dict) and base_item.get(list_item_key) == match_val:
                            base_val[i] = ov_item
                            break
                    else:
                        base_val.append(ov_item)
                else:
                    base_val.append(ov_item)
        else:
            base[key] = ov_val




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
        """Returns the underlying raw data dictionary"""
        return self._data


    @property
    def chassis(self) -> AppChassis | None:
        """
        Returns the chassis associated with this descriptor, if any or None. The chassis is used for evaluating
        variable expressions in the descriptor values.
        """
        return self._chassis


    def try_navigate(self, path: str) -> tuple[bool, Any | None]:
        """
        Tries to navigate the data using the given path as far as possible. Returns a tuple of (success, value) where
        success is a boolean indicating whether the navigation was successful navigating the whole path and value is the
        navigated value (including None) up to the point that was navigated

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

            if node is None:
                return False, None

            if seg[0] == "#":
                # List index navigation
                if not isinstance(node, list):
                    return False, node
                try:
                    idx = int(seg[1:])
                except ValueError:
                    return False, node
                if idx < 0 or idx >= len(node):
                    return False, node
                node = node[idx]

            elif seg[0] == "$":
                # Attribute search navigation: $key=value
                if not isinstance(node, list):
                    return False, node
                eq = seg.find("=", 1)
                if eq < 0:
                    return False, node
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
                    return False, node
                node = found

            else:
                # Plain dictionary key navigation
                if not isinstance(node, dict):
                    return False, node
                if seg not in node:
                    return False, node
                node = node[seg]

        return True, node


    def navigate(self, path: str) -> Any | None | EllipsisType:
        """
        Navigates the data using the given path. Returns the value associated with the path if it exists (including None),
        or ... to indicate that such path did not land at an existing descriptor node.
        """
        ok, value = self.try_navigate(path)
        return value if ok else ...


    def navigate_required_path(self, path: str) -> Any | None:
        """
        Navigates the data using the given path. Returns the value associated with the path if it exists (including None).
        Raises ConfigError if the path does not exist in the descriptor.
        """
        ok, value = self.try_navigate(path)
        if not ok:
            raise ConfigError(f"Required path `{path}` is missing in descriptor data")
        return value


    def navigate_required_value(self, path: str) -> Any:
        """
        Navigates the data using the given path. Returns the value associated with the path if it exists and is not None.
        Raises ConfigError if the path does not exist in the descriptor or if the value is None.
        """
        ok, value = self.try_navigate(path)
        if not ok:
            raise ConfigError(f"Required path `{path}` is missing in descriptor data")
        if value is None:
            raise ConfigError(f"Required value at path `{path}` is null in descriptor data")
        return value


    def var_resolver(self, var_name: str) -> tuple[bool, str]:
        """
        Resolves a variable name to its value for the purpose of evaluating variable expressions in descriptor values.
        """
        got = self.navigate(var_name)
        if got is ...:
            raise ConfigError(f"Var expr `{var_name}` could not be resolved in descriptor data")
        return True, got if got is not None else ""  # always return True to stop expression eval


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
                value = expand_var_expressions(value, resolver=self.var_resolver, chassis=self._chassis)
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
                value = expand_var_expressions(value, resolver=self.var_resolver, chassis=self._chassis)
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
                value = expand_var_expressions(value, resolver=self.var_resolver, chassis=self._chassis)
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
                expanded = expand_var_expressions(value, resolver=self.var_resolver, chassis=self._chassis)
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
                return datetime.fromtimestamp(value, timezone.utc)
            except (OSError, OverflowError, ValueError):
                return default
        if isinstance(value, str):
            if not verbatim:
                value = expand_var_expressions(value, resolver=self.var_resolver, chassis=self._chassis)
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
