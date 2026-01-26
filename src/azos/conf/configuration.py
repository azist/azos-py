"""Provides the Configuration root object for Azos configuration tree"""

from __future__ import annotations

import os

from .nodes import ConfigAttributeNode, ConfigSectionNode


class Configuration:
    """Represents root configuration object holding a config tree"""

    def __init__(self, read_only: bool = False) -> None:
        self._read_only = read_only
        self._root: ConfigSectionNode | None = None
        self._empty_section = ConfigSectionNode(self, None, exists=False)
        self._empty_attribute = ConfigAttributeNode(self, None, exists=False)
        self.variable_start = "$("
        self.variable_end = ")"
        self.variable_escape = "$$"
        self.variable_env_mod = "~"
        self.variable_path_mod = "@"

    @property
    def is_read_only(self) -> bool:
        """Returns true when configuration is read-only"""
        return self._read_only

    @property
    def root(self) -> ConfigSectionNode:
        """Returns root section node"""
        return self._root if self._root is not None else self._empty_section

    @property
    def empty_section(self) -> ConfigSectionNode:
        """Returns empty section sentinel"""
        return self._empty_section

    @property
    def empty_attribute(self) -> ConfigAttributeNode:
        """Returns empty attribute sentinel"""
        return self._empty_attribute

    def create(self, root_name: str = "config", root_value: str | None = None) -> "Configuration":
        """Creates a new root section and returns self"""
        self._root = ConfigSectionNode(self, None, root_name, root_value)
        return self

    def destroy(self) -> None:
        """Destroys configuration root"""
        self._root = None

    def get(self, path: str) -> ConfigSectionNode | ConfigAttributeNode:
        """Navigates the path from root"""
        if self._root is None:
            return self._empty_section
        return self._root.navigate(path)

    def exists(self, path: str) -> bool:
        """Returns true if a node exists at path"""
        return self.get(path).exists

    def resolve_env_var(self, name: str) -> str | None:
        """Resolves an environment variable by name"""
        if name is None or name == "":
            return None
        return os.environ.get(name)
