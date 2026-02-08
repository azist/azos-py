"""Provides configuration node classes used by the Azos configuration system"""

from __future__ import annotations

import datetime as _datetime
import os
from typing import Iterable

from ..atom import Atom
from ..entityid import EntityId
from ..exceptions import AzosError


def _normalize_name(name: str | None) -> str:
    return name.strip() if isinstance(name, str) else ""


def _equals_ignore_case(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return left.lower() == right.lower()


def _to_str(value: str | None, dflt: str | None) -> str | None:
    if value is None or value == "":
        return dflt
    return str(value)


def _to_int(value: str | None, dflt: int) -> int:
    if value is None or value == "":
        return dflt
    try:
        return int(str(value).strip(), 0)
    except ValueError as err:
        raise AzosError("Invalid int value", "conf", "as_int") from err


def _to_float(value: str | None, dflt: float) -> float:
    if value is None or value == "":
        return dflt
    try:
        return float(str(value).strip())
    except ValueError as err:
        raise AzosError("Invalid float value", "conf", "as_float") from err


def _to_bool(value: str | None, dflt: bool) -> bool:
    if value is None or value == "":
        return dflt
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1", "on"}:
        return True
    if text in {"false", "f", "no", "n", "0", "off"}:
        return False
    raise AzosError("Invalid bool value", "conf", "as_bool")


def _to_datetime(value: str | None, dflt: _datetime.datetime | None) -> _datetime.datetime | None:
    if value is None or value == "":
        return dflt
    if isinstance(value, _datetime.datetime):
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _datetime.datetime.fromisoformat(text)
    except ValueError as err:
        raise AzosError("Invalid datetime value", "conf", "as_datetime") from err


def _to_atom(value: str | None, dflt: Atom | None) -> Atom | None:
    if value is None or value == "":
        return dflt
    return Atom(value)


def _to_entityid(value: str | None, dflt: EntityId | None) -> EntityId | None:
    if value is None or value == "":
        return dflt
    return EntityId.from_value(value)


def _choose_separator(left: str, right: str) -> str:
    if "\\" in left or "\\" in right:
        return "\\"
    return "/"


def _add_path(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    if left == "":
        return right
    if right == "":
        return left
    sep = _choose_separator(left, right)
    if left.endswith("/") or left.endswith("\\"):
        left = left[:-1]
    if right.startswith("/") or right.startswith("\\"):
        right = right[1:]
    return left + sep + right


class ConfigNode:
    """Base configuration node with common name/value behavior"""

    def __init__(self, configuration, parent: ConfigSectionNode | None = None, name: str | None = None,
                 value: str | None = None, exists: bool = True) -> None:
        self._configuration = configuration
        self._parent = parent
        self._name = _normalize_name(name)
        self._value = value
        self._modified = False
        self._exists = exists

    @property
    def configuration(self):
        """Returns configuration instance this node belongs to"""
        return self._configuration

    @property
    def exists(self) -> bool:
        """Returns true if this node exists in configuration"""
        return self._exists

    @property
    def name(self) -> str:
        """Gets or sets node name"""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self.__check_can_modify()
        new_name = _normalize_name(value)
        if self._name != new_name:
            self._name = new_name
            self._modified = True

    @property
    def verbatim_value(self) -> str | None:
        """Returns raw node value without variable evaluation"""
        return self._value

    @property
    def value(self) -> str | None:
        """Returns evaluated node value with variables expanded"""
        if self._value is None or self._value == "":
            return None
        if isinstance(self, ConfigSectionNode):
            return self.evaluate_value_variables(self._value)
        if self._parent is not None and self._parent.exists:
            return self._parent.evaluate_value_variables(self._value)
        return self.evaluate_value_variables(self._value)

    @value.setter
    def value(self, value: str | None) -> None:
        self.__check_can_modify()
        if self._value != value:
            self._value = value
            self._modified = True

    @property
    def parent(self) -> ConfigSectionNode:
        """Returns parent section or an empty section"""
        if self._parent is None:
            return self._configuration.empty_section
        return self._parent

    @property
    def root(self) -> ConfigSectionNode:
        """Returns root section for this node"""
        node: ConfigNode = self
        while True:
            parent = node._parent
            if parent is None or not parent.exists:
                break
            node = parent
        if isinstance(node, ConfigSectionNode):
            return node
        return self._configuration.root

    @property
    def is_root(self) -> bool:
        """Returns true if this node is root"""
        return self._parent is None or not self._parent.exists

    @property
    def is_section(self) -> bool:
        """Returns true if node is a section"""
        return isinstance(self, ConfigSectionNode)

    @property
    def is_attribute(self) -> bool:
        """Returns true if node is an attribute"""
        return isinstance(self, ConfigAttributeNode)

    @property
    def modified(self) -> bool:
        """Returns true if node has been modified"""
        return self._modified

    @property
    def path(self) -> str:
        """Returns path from root to this node"""
        if not self.parent.exists:
            return "/"
        prefix = "$" if self.is_attribute else ""
        name = self.name
        index = self.__get_sibling_index()
        segment = f"{prefix}[{index}]" if index >= 0 else f"{prefix}{name}"
        if self.parent is None or self.parent == self._configuration.root:
            return "/" + segment
        return self.parent.path.rstrip("/") + "/" + segment

    def reset_modified(self) -> None:
        """Resets modified flag on this node"""
        self._modified = False

    def delete(self) -> None:
        """Deletes this node from its parent"""
        raise NotImplementedError()

    def is_same_name(self, other_name: str | None) -> bool:
        """Returns true when node name matches supplied name"""
        return _equals_ignore_case(self.name, other_name)

    def find_by_path(self, path: str) -> ConfigNode:
        """Navigates the path from this node"""
        if isinstance(self, ConfigSectionNode):
            return self.navigate(path)
        return self.parent.navigate(path)

    def as_str(self, dflt: str | None = None, verbatim: bool = False) -> str | None:
        """Returns node value as string"""
        value = self.verbatim_value if verbatim else self.value
        return _to_str(value, dflt)

    def as_int(self, dflt: int = 0, verbatim: bool = False) -> int:
        """Returns node value as int"""
        value = self.verbatim_value if verbatim else self.value
        return _to_int(value, dflt)

    def as_float(self, dflt: float = 0.0, verbatim: bool = False) -> float:
        """Returns node value as float"""
        value = self.verbatim_value if verbatim else self.value
        return _to_float(value, dflt)

    def as_bool(self, dflt: bool = False, verbatim: bool = False) -> bool:
        """Returns node value as bool"""
        value = self.verbatim_value if verbatim else self.value
        return _to_bool(value, dflt)

    def as_datetime(self, dflt: _datetime.datetime | None = None, verbatim: bool = False) -> _datetime.datetime | None:
        """Returns node value as datetime"""
        value = self.verbatim_value if verbatim else self.value
        return _to_datetime(value, dflt)

    def as_atom(self, dflt: Atom | None = None, verbatim: bool = False) -> Atom | None:
        """Returns node value as Atom"""
        value = self.verbatim_value if verbatim else self.value
        return _to_atom(value, dflt)

    def as_entityid(self, dflt: EntityId | None = None, verbatim: bool = False) -> EntityId | None:
        """Returns node value as EntityId"""
        value = self.verbatim_value if verbatim else self.value
        return _to_entityid(value, dflt)

    def evaluate_value_variables(self, value: str, recurse: bool = True) -> str:
        """Evaluates $(var) variables in a value string"""
        if value is None:
            return None
        escape = self._configuration.variable_escape
        if value.startswith(escape):
            return value[len(escape):] if len(value) > len(escape) else ""

        var_start = self._configuration.variable_start
        var_end = self._configuration.variable_end

        visited: set[str] = set()
        iterations = 0
        max_iterations = 1000
        result = value
        while True:
            if iterations > max_iterations:
                raise AzosError("Variable expansion exceeded max iterations", "conf", "evaluate_value_variables")
            iterations += 1
            idxs = result.find(var_start)
            if idxs < 0:
                break
            idxe = result.find(var_end, idxs + len(var_start))
            if idxe < 0:
                break
            original = result[idxs:idxe + len(var_end)]
            vname = result[idxs + len(var_start):idxe].strip()
            if vname in visited:
                raise AzosError("Recursive variable expansion", "conf", "evaluate_value_variables")
            visited.add(vname)
            try:
                replacement = self.__resolve_variable(vname)
                result = result.replace(original, replacement, 1)
                if not recurse:
                    break
            finally:
                visited.remove(vname)
        return result

    def __resolve_variable(self, name: str) -> str:
        if name is None or name == "":
            return ""
        env_mod = self._configuration.variable_env_mod
        path_mod = self._configuration.variable_path_mod
        if name.startswith(env_mod):
            env_name = name[len(env_mod):]
            required = False
            if env_name.startswith("!"):
                env_name = env_name[1:]
                required = True
            value = self._configuration.resolve_env_var(env_name)
            if value is None:
                if required:
                    raise AzosError("Required environment variable missing", "conf", "evaluate_value_variables")
                return ""
            return value
        if name.startswith(path_mod):
            value = self._resolve_path_value(name[len(path_mod):])
            return value
        return self._resolve_path_value(name)

    def _resolve_path_value(self, path: str) -> str:
        node = self.find_by_path(path)
        return node.value or ""

    def __get_sibling_index(self) -> int:
        if self.parent is None or not self.parent.exists:
            return -1
        siblings: list[ConfigNode]
        if self.is_attribute:
            siblings = [a for a in self.parent.attributes if a.is_same_name(self.name)]
        else:
            siblings = [c for c in self.parent.children if c.is_same_name(self.name)]
        if len(siblings) <= 1:
            return -1
        for i, node in enumerate(siblings):
            if node is self:
                return i
        return -1

    def __check_can_modify(self) -> None:
        if not self.exists:
            raise AzosError("Cannot modify empty node", "conf", "ConfigNode")
        if self._configuration.is_read_only:
            raise AzosError("Configuration is read-only", "conf", "ConfigNode")


class ConfigSectionNode(ConfigNode):
    """Represents a configuration section node which can have children and attributes"""

    def __init__(self, configuration, parent: ConfigSectionNode | None = None, name: str | None = None,
                 value: str | None = None, exists: bool = True) -> None:
        super().__init__(configuration, parent, name, value, exists)
        self._children: list[ConfigSectionNode] = []
        self._attributes: list[ConfigAttributeNode] = []

    @property
    def children(self) -> Iterable[ConfigSectionNode]:
        """Returns an iterable of child sections"""
        return list(self._children)

    @property
    def attributes(self) -> Iterable[ConfigAttributeNode]:
        """Returns an iterable of attribute nodes"""
        return list(self._attributes)

    def add_child_node(self, name: str, value: str | None = None) -> ConfigSectionNode:
        """Adds a new child section node"""
        self._check_can_modify_section()
        node = ConfigSectionNode(self._configuration, self, name, value)
        self._children.append(node)
        self._modified = True
        return node

    def add_attribute_node(self, name: str, value: str | None = None) -> ConfigAttributeNode:
        """Adds a new attribute node"""
        self._check_can_modify_section()
        node = ConfigAttributeNode(self._configuration, self, name, value)
        self._attributes.append(node)
        self._modified = True
        return node

    def remove_child(self, node: ConfigSectionNode) -> None:
        """Removes a child section node"""
        self._check_can_modify_section()
        if node in self._children:
            self._children.remove(node)
            self._modified = True

    def clear_children(self) -> None:
        """Removes all children"""
        self._check_can_modify_section()
        self._children.clear()
        self._modified = True

    def clear_attributes(self) -> None:
        """Removes all attributes"""
        self._check_can_modify_section()
        self._attributes.clear()
        self._modified = True

    def get_child(self, name: str) -> ConfigSectionNode:
        """Returns child section by name or empty section"""
        for child in self._children:
            if child.is_same_name(name):
                return child
        return self._configuration.empty_section

    def attr_by_name(self, name: str) -> ConfigAttributeNode:
        """Returns attribute by name or empty attribute"""
        for attr in self._attributes:
            if attr.is_same_name(name):
                return attr
        return self._configuration.empty_attribute

    def child_by_index(self, idx: int) -> ConfigSectionNode:
        """Returns child by index or empty section"""
        if 0 <= idx < len(self._children):
            return self._children[idx]
        return self._configuration.empty_section

    def attr_by_index(self, idx: int) -> ConfigAttributeNode:
        """Returns attribute by index or empty attribute"""
        if 0 <= idx < len(self._attributes):
            return self._attributes[idx]
        return self._configuration.empty_attribute

    def navigate(self, path: str) -> ConfigNode:
        """Navigates a path and returns a node"""
        if path is None or path.strip() == "":
            raise AzosError("Path is empty", "conf", "navigate")
        required = False
        working = path.strip()
        if working.startswith("!"):
            required = True
            working = working[1:]
        if working.startswith("/") or working.startswith("\\"):
            working = working[1:]
            current: ConfigNode = self._configuration.root
        else:
            current = self
        if working == "":
            return current
        segments = [seg for seg in working.replace("\\", "/").split("/") if seg != ""]
        for seg in segments:
            if not current.exists:
                break
            if seg == "..":
                current = current.parent
                continue
            if not isinstance(current, ConfigSectionNode):
                raise AzosError("Path segment is not a section", "conf", f"navigate({path})")
            section = current
            is_attr = False
            if seg.startswith("$"):
                is_attr = True
                seg = seg[1:].strip()
            if seg.startswith("[") and seg.endswith("]"):
                idx_text = seg[1:-1]
                try:
                    idx = int(idx_text)
                except ValueError as err:
                    raise AzosError("Invalid index in path", "conf", f"navigate({path})") from err
                current = section.attr_by_index(idx) if is_attr else section.child_by_index(idx)
                continue
            if seg.endswith("]") and "[" in seg and not is_attr:
                open_idx = seg.index("[")
                name = seg[:open_idx]
                query = seg[open_idx + 1:-1]
                if "=" in query:
                    atr_name, atr_value = query.split("=", 1)
                    found = None
                    for child in section.children:
                        if child.is_same_name(name) and _equals_ignore_case(child.attr_by_name(atr_name).value, atr_value):
                            found = child
                            break
                    current = found if found is not None else self._configuration.empty_section
                else:
                    found = None
                    for child in section.children:
                        if child.is_same_name(name) and _equals_ignore_case(child.value, query):
                            found = child
                            break
                    current = found if found is not None else self._configuration.empty_section
                continue
            current = section.attr_by_name(seg) if is_attr else section.get_child(seg)
        if required and not current.exists:
            raise AzosError("Required node not found", "conf", f"navigate({path})")
        return current

    def delete(self) -> None:
        """Deletes this section from its parent"""
        self._ConfigNode__check_can_modify()
        if not self.parent.exists:
            self._configuration.destroy()
            return
        self.parent.remove_child(self)

    def reset_modified(self) -> None:
        """Resets modified flag on this node and children"""
        super().reset_modified()
        for child in self._children:
            child.reset_modified()
        for attr in self._attributes:
            attr.reset_modified()

    def _check_can_modify_section(self) -> None:
        self._ConfigNode__check_can_modify()


class ConfigAttributeNode(ConfigNode):
    """Represents a leaf attribute node"""

    def delete(self) -> None:
        """Deletes this attribute from its parent"""
        self._ConfigNode__check_can_modify()
        if not self.parent.exists:
            return
        if self in self.parent._attributes:
            self.parent._attributes.remove(self)
            self.parent._modified = True
