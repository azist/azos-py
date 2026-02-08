"""
Uniform application chassis pattern

Copyright (C) 2023, 2026 Azist, MIT License

"""
import os
import re
import uuid
import platform
from pathlib import Path
from configparser import ConfigParser
from typing import List, Optional, Callable, Tuple

ENV_ENVIRONMENT_NAME_VAR = "SKY_ENVIRONMENT"
"""Name of the environment variable which holds Azos/SKY environment name, such as DEV/TEST/PROD"""

DEFAULT_APP_ID = "azapp"
"""Default application id which is used when no chassis is allocated"""

VAR_EXPANSION_PATTERN = re.compile(r'\$\(([^)]+)\)')
"""Matches $(var) pattern used in config values etc."""

INCLUDE_REX_PATTERN = re.compile(r'^#include<([^\s>]+)>$', re.MULTILINE)
"""Matches #include<X> file include pragma used with `process_includes()`"""


def expand_var_expressions(val: str, resolver: Callable[[str], Tuple[bool, str]] | None = None) -> str:
    """
    Expands variables which have a form of `$(expr)` by invoking expression resolver for each.
    If no resolver passed then assumes expr to represent an OS var.
    Variable expansions can NOT nest, for example this is invalid: `$(abc$(a))`
    """

    # If the string doesn't even have '$', we can skip regex entirely
    if "$" not in val:
        return val

    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)

        # Priority 1: Custom Resolver
        if resolver:
            handled, resolved_value = resolver(var_name)
            if handled:
                return str(resolved_value)

        # Priority 2: OS Environment
        # Using match.group(0) as default keeps the $(VAR) intact if not found
        return os.environ.get(var_name, match.group(0))

    return VAR_EXPANSION_PATTERN.sub(replace_match, val)


def process_includes(root_path: Path, content: str, expand_vars: bool = False, resolver: Callable[[str], Tuple[bool, str]] | None = None) -> str:
    """
    Replaces lines starting with '#include<X>' with the content of file X.
    If X starts with "!" then the file is required and the system throws exception if such file
    is not found, otherwise the include is replaced with an empty string

    Args:
        root_path: A Path as of which to search for files
        content: Input string to process.
        expand_vars: pass True to expand environment vars in the include
        resolver: optional env var resolver functor

    Returns:
        Modified string with includes expanded.

    Raises:
        FileNotFoundError: If an include file is missing and was referenced with "!" in the
        beginning, otherwise an empty string will be returned
    """
    def replace_match(match: re.Match) -> str:
        filename = match.group(1)

        if expand_vars:
            filename = expand_var_expressions(filename, resolver)

        filename = filename.strip() # safeguard
        required = len(filename) > 1 and filename.startswith("!")
        if required:
            filename = filename[1:]

        file_path = root_path.joinpath(filename)
        if not file_path.is_file():
            if required:
                raise FileNotFoundError(f"Required include file is not found: `{file_path}`")
            else:
                return "" # empty string if referenced file is not found
        return file_path.read_text()  # Preserves newlines and encoding

    return INCLUDE_REX_PATTERN.sub(replace_match, content)



class AppChassis:
    """
    Application chassis pattern provides global boilerplate for app instance identification,
    logical host name mapping and configuration root. It is a singleton object which get initialized
    only at the application entry point (such as `main.py`)

    Notes:
        This is a purposely opinionated design pattern applied to Azos applications to set the unified
        approach to application architecture
    """

    __s_default: Optional["AppChassis"] = None
    __s_current: Optional["AppChassis"] = None
    __s_global_dependency_callbacks: List[Callable] = []

    @staticmethod
    def register_global_dependency_callback(callback: Callable):
        """Registers global dependency callback function if it is not yet registered"""
        if callback not in AppChassis.__s_global_dependency_callbacks:
          AppChassis.__s_global_dependency_callbacks.append(callback)

    @staticmethod
    def get_default_instance() -> "AppChassis":
      """Returns the ever-present default Application class instance"""
      return AppChassis.__s_default

    @staticmethod
    def get_current_instance() -> "AppChassis":
      """
      Returns the current Application singleton which was allocated the last.
      If not explicit allocation was ever made then the default instance is returned
      """
      current = AppChassis.__s_current
      return current if current else AppChassis.__s_default

    def __init__(self,
                 app_id: str,
                 ep_path: str,
                 environment_name: str | None = None,
                 config: ConfigParser | None = None):
       self._instance_id = uuid.uuid4().hex
       self._entry_point_path = os.path.abspath(ep_path)
       self._app = app_id if app_id else DEFAULT_APP_ID
       self._instance_tag = self._instance_id[:8] # Tag is a shortened app id
       self._environment = self._get_environment(environment_name)
       self._config = self._load_config(config) # use the supplied one or load co-located file
       self._host = platform.node()

       if not AppChassis.__s_default:
          AppChassis.__s_default = self
          self._isdefault = True
       else:
          AppChassis.__s_current = self
          self._isdefault = False

       # Notify all dependencies
       for callback in AppChassis.__s_global_dependency_callbacks:
          if callable(callback):
             callback()

    def _get_environment(self, environment_name: str | None) -> str:
       """
       Returns environment name supplied or default to environment variable `SKY_ENVIRONMENT`

       Note:
            The returned value is always lowercase
       """
       if environment_name is not None and environment_name != "" and not environment_name.isspace():
          return environment_name.lower()

       environment_name = os.getenv(ENV_ENVIRONMENT_NAME_VAR, 'local')
       return environment_name.lower()

    def _load_config(self, config: ConfigParser | None) -> ConfigParser:
        """
        Loads config INI file co-located with the entry point.
        The file takes format: `main-ENV.ini` where `ENV` is the name of your environment,
        for example:  `./main-dev.ini`, `./main-prod.ini` etc.
        If environment specific file is not found, then system tries to load from
        non-environment file such as `./main.ini`
        """
        if config:
            return config # pass-through

        config = ConfigParser() # config always exists, even an empty one

        path = Path(self._entry_point_path)
        # Try Environment-specific file first
        full = path.parent.joinpath(f"{path.stem}-{self._environment}.ini")
        fn = None
        if os.path.isfile(full):
            fn = full
        else:
            # No environment name at all
            full = path.parent.joinpath(f"{path.stem}.ini")
            if os.path.isfile(full):
                fn = full

        if fn:
            # config.read(fn)
            source = fn.read_text()
            # Pre process source
            source = process_includes(path.parent, source, expand_vars=True) #  #include<!../cfg/log-$(ENV_NAME).ini>
            # ------------------
            config.read_string(source, f"Interpolated config `{str(fn)}`")

        return config

    @property
    def isdefault(self) -> bool:
        """Return True if this is a default Application instance"""
        return self._isdefault

    @property
    def config(self) -> ConfigParser:
        """Returns ConfigParser object for this app. It is always present even if app does not have a config file"""
        return self._config

    @property
    def entry_point_path(self) -> str:
        """Returns full absolute path to the entrypoint"""
        return self._entry_point_path

    @property
    def environment(self) -> str:
        """Return environment name - always lowercase"""
        return self._environment

    @property
    def instance_id(self) -> str:
        """Return a string identifier of the running instance"""
        return self._instance_id

    @property
    def instance_tag(self) -> str:
        """Return a short tag id of the running instance - used for logging"""
        return self._instance_tag

    @property
    def host(self) -> str:
        """Returns logical host name of this machine. Defaults to physical host name"""
        return self._host

    @property
    def app(self) -> str:
        """Short application id. Atom recommended"""
        return self._app


# Allocate default instance
AppChassis(DEFAULT_APP_ID, __file__)
