"""
Uniform application chassis pattern

Copyright (C) 2023 Azist, MIT License

"""
import os
import uuid
import platform
from pathlib import Path
from configparser import ConfigParser
from typing import List, Callable

ENV_ENVIRONMENT_NAME_VAR = "SKY_ENVIRONMENT"
"""Name of the environment variable which holds Azos/SKY environment name, such as DEV/TEST/PROD"""

DEFAULT_APP_ID = "azapp"
"""Default application id which is used when no chassis is allocated"""


class AppChassis:
    """
    Application chassis pattern provides global boilerplate for app instance identification,
    logical host name mapping and configuration root. It is a singleton object which get initialized
    only at the application entry point (such as `main.py`)

    Notes:
        This is a purposely opinionated design pattern applied to Azos applications to set the unified
        approach to application architecture
    """

    __s_default: "AppChassis"
    __s_current: "AppChassis"
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
       """
       if config:
          return config # pass-through

       config = ConfigParser()

       path = Path(self._entry_point_path)
       full = path.parent.joinpath(f"{path.stem}-{self._environment}.ini")
       if os.path.isfile(full):
          config.read(full)

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
