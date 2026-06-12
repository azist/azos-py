"""
Uniform application chassis pattern

Copyright (C) 2023, 2026 Azist, MIT License

"""
import logging
import os
import re
import uuid
import platform
import atexit
from pathlib import Path
from configparser import ConfigParser
from typing import Any, Sequence, Type, Dict, List, Optional, Callable, Tuple, TypeVar, override
from azos.oop import DisposableObject
from azos.stock_content import loader


ENV_ENVIRONMENT_NAME_VAR = "SKY_ENVIRONMENT"
"""Name of the environment variable which holds Azos/SKY environment name, such as DEV/TEST/PROD"""

DEFAULT_ENV_NAME = "local"
"""Default environment name if not specified in env var or chassis allocation"""

DEFAULT_APP_ID = "azos"
"""Default application id which is used when no chassis is allocated"""

VAR_EXPANSION_PATTERN = re.compile(r'\$\(([^)]+)\)')
"""Matches $(var) pattern used in config values etc."""

INCLUDE_REX_PATTERN = re.compile(r'^#include<([^\s>]+)>$', re.MULTILINE)
"""Matches #include<X> file include pragma used with `process_includes()`"""

PFX_CHASSIS = "chassis::"
"""
Prefix for application chassis variables, such as `chassis::app`, `chassis::env` etc. This is used in various
configurations for example in log formatters to include chassis variables into logs
"""

PFX_CHASSIS_LEN = len(PFX_CHASSIS)
"""Length of the chassis variable prefix, used for optimization when parsing variable names"""

INCLUDE_MAX_DEPTH = 10
"""Maximum depth of nested includes to prevent infinite recursion. This is a safeguard"""

PFX_STOCK = "stock::"
"""Prefix for stock artifact path - paths that start with this prefix are read by stock content loader"""

PFX_STOCK_LEN = len(PFX_STOCK)
"""Length of the stock variable prefix, used for optimization when parsing var names"""


class ConfigError(Exception):
    """Custom exception type for configuration errors"""
    pass


def expand_var_expressions(val: str | None,
                           resolver: Callable[[str], Tuple[bool, str]] | None = None,
                           chassis: Optional["AppChassis"] = None) -> str | None:
    """
    Expands variables which have a form of `$(expr)` by invoking expression resolver for each.
    If no resolver passed then uses default env var resolver.
    Variable expansion definitions can NOT nest, for example this is invalid: `$(abc$(a))`.
    Works in multiple passes until no more variables are found or maximum depth is reached.
    This allows for chained variable expansions such as `$(var1)` where var1's value is `$(var2)` and so on.

    args:
        val: input string to expand
        resolver: optional custom resolver function which takes variable name and returns a tuple of
          (handled: bool, value: str). If handled is True then value is used as the resolved value, otherwise
          default env var resolver is used.
        chassis: optional AppChassis instance to resolve chassis variables such as `$(chassis::app)`, `$(chassis::env)` etc.

    returns:
        Expanded string with all variables resolved. If a variable cannot be resolved, it remains unchanged
        in the output.
    """

    if val is None:
        return None

    original = val
    i = 0
    while True:
        if i == INCLUDE_MAX_DEPTH:
            raise ConfigError(f"Expression '{original}'->'{val}' exceeded maximum var expansion depth of {INCLUDE_MAX_DEPTH}. "
                              f"Look for circular references or missing env vars.")

        matched, val = expand_var_expressions_once(val, resolver, chassis)

        if not matched:
            break

        i += 1

    return val



def expand_var_expressions_once(val: str | None,
                                resolver: Callable[[str], Tuple[bool, str]] | None = None,
                                chassis: Optional["AppChassis"] = None) -> Tuple[bool, str | None]:
    """
    Expands variables which have a form of `$(expr)` by invoking expression resolver for each.
    If no resolver passed then uses default env var resolver.
    Variable expansion definitions can NOT nest, for example this is invalid: `$(abc$(a))`.
    Works in a  single pass, meaning that if the resolved value contains more variables,
    they will NOT be expanded in this call.

    args:
        val: input string to expand
        resolver: optional custom resolver function which takes variable name and returns a tuple of
          (handled: bool, value: str). If handled is True then value is used as the resolved value, otherwise
          default env var resolver is used.
        chassis: optional AppChassis instance to resolve chassis variables such as `$(chassis::app)`, `$(chassis::env)` etc.

    returns:
        Expanded string with all variables resolved in this pass. If a variable cannot be resolved, it remains unchanged
        in the output. Single pass meaning that if the resolved value contains more variables, they will not be
         expanded in this call. See `expand_var_expressions()` for multi-pass expansion.
    """
    if val is None:
        return False, None

    # If the string doesn't even have '$', we can skip regex entirely
    if "$" not in val:
        return False, val

    had_match = False

    def replace_match(match: re.Match) -> str:
        nonlocal had_match
        had_match = True

        var_name = match.group(1)

        # Priority 1: Custom Resolver
        if resolver:
            handled, resolved_value = resolver(var_name)
            if handled:
                return str(resolved_value)

        #Priority 2: Chassis Variables
        if var_name.startswith(PFX_CHASSIS) and len(var_name) > PFX_CHASSIS_LEN:
            ac = chassis if chassis else AppChassis.get_current_instance()
            nm = var_name[PFX_CHASSIS_LEN:]
            return getattr(ac, nm, nm)

        #Priority 3: App config $(@sect->key) syntax
        if var_name.startswith("@") and len(var_name) > 4: # @x->y is the minimum length = 5 chars
            ac = chassis if  chassis else AppChassis.get_current_instance()
            sect,_, atr = var_name[1:].partition("->")
            if len(sect) > 0 and len(atr) > 0:
                return ac.config.get(sect, atr, fallback="")

        # Priority 4: OS Environment
        # Using match.group(0) as default keeps the $(VAR) intact if not found
        return os.environ.get(var_name, match.group(0)) or ""

    result =  VAR_EXPANSION_PATTERN.sub(replace_match, val)
    return had_match, result


def process_includes(root_path: Path,
                     content: str,
                     expand_vars: bool = False,
                     resolver: Callable[[str], Tuple[bool, str]] | None = None,
                     chassis: Optional["AppChassis"] = None) -> str:
    """
    Replaces lines starting with '#include<X>' with the content of file X.
    If X starts with "!" then the file is required and the system throws exception if such file
    is not found, otherwise the include clause is replaced with an empty string

    Args:
        root_path: A Path as of which to search for files
        content: Input string to process.
        expand_vars: pass True to expand environment vars in the include
        resolver: optional env var resolver functor
        chassis: application chassis instance, or current will be used if None

    Returns:
        Modified string with includes expanded.

    Raises:
        FileNotFoundError: If an include file is missing and was referenced with "!" in the
        beginning, otherwise an empty string will be returned
    """
    def replace_match(match: re.Match) -> str:
        filename = str(match.group(1))

        if expand_vars:
            filename = expand_var_expressions(filename, resolver, chassis)

        if filename is None:
            return "" # empty string if filename is None after expansion

        filename = filename.strip() # safeguard
        required = len(filename) > 1 and filename.startswith("!")
        if required:
            filename = filename[1:]

        if filename == "":
            if required:
                raise FileNotFoundError(f"Required include file is unknown after var evaluation")
            else:
                return "" # empty string if filename is empty after expansion

        if filename.startswith(PFX_STOCK) and len(filename) > PFX_STOCK_LEN:
            stock_path = filename[PFX_STOCK_LEN:]
            stock_content = loader.load_text_content(stock_path)
            if stock_content is None:
                if required:
                    raise FileNotFoundError(f"Required stock content file is not found: `{stock_path}`")
                else:
                    return "" # empty string if referenced stock content is not found
            return stock_content

        file_path = root_path.joinpath(filename)
        if not file_path.is_file():
            if required:
                raise FileNotFoundError(f"Required include file is not found: `{file_path}`")
            else:
                return "" # empty string if referenced file is not found
        return file_path.read_text()  # Preserves newlines and encoding

    return INCLUDE_REX_PATTERN.sub(replace_match, content)


T = TypeVar("T")

class DIContainer:
    """
    Implements service location/dependency injection pattern by providing a double registry of
    dict[Type, Dict[str, instance]] dependency instances.

    Important: `DIContainer` does not assume any component ownership. Treat it as a specialized data structure
    for storing and retrieving dependencies. It is the responsibility of the owners/directors to manage dependency
    life cycles.
    """

    def __init__(self) -> None:
        self._deps: dict[Type, Dict[str, Any]] = {}

    def purge(self, t_dep: Type | None = None):
        """Drops all dependencies and starts anew, if you supply a type then drops only dependencies of that type"""
        if t_dep is None:
          self._deps = { }  # Clear all
        else:
          self._deps.pop(t_dep, None)

    def register(self, t_dep: Type, instance: Any, name: str | None = None) -> bool:
        """
        Registers a dependency instance of type and optional name.
        The instance MUST be of tDep class assignment-compatible.

        :param self: Self reference
        :param t_dep: Dependency type such as abstract base type of service (and interface)
        :type t_dep: Type of service to register
        :param instance: An instance of the said type
        :type instance: type or subtype of tDep
        :param name: Optional name, to resolve instance by name, if not used then `*` is assumed
        :return: True if was added, false if already existed and was replaced
        """
        if t_dep is None:
            raise TypeError("Missing dependency type")

        if instance is None:
            raise ValueError("Missing dependency instance")

        if not isinstance(instance, t_dep):
            raise TypeError(f"Mismatch in dep registration of type `{t_dep}`, but instance is not of that type")

        if not name:
            name = "*"

        named = self._deps.get(t_dep, None) # Get type bucket
        if named is None:
            named = { }
            self._deps[t_dep] = named

        was = name in named
        named[name] = instance
        return not was


    def try_get(self, t_dep: Type[T], name: str | None = None) -> T | None:
        """
        Tries to resolve a dependency of the specifies type and optional name.
        If resolution fails, returns None, unlike the `get` method which throws

        :param self: Self ref
        :param t_dep: Dependency type such as abstract base type of service (and interface)
        :type t_dep: Type[T] of service to get
        :param name: Optional name, in NOne then `*` is used for any
        :return: Dependency instance of the requested type or None
        """
        if t_dep is None:
            return None

        named = self._deps.get(t_dep, None)
        if named is None:
            return None;

        if not name:
            name = "*"

        return named.get(name, None)


    def get(self, t_dep: Type[T], name: str | None = None) -> T:
        """
        Resolve a dependency of the specifies type and optional name.
        If resolution fails, then throws, unlike the `try_get` method which return None

        :param self: Self ref
        :param t_dep: Dependency type such as abstract base type of service (and interface)
        :type t_dep: Type[T] of service to get
        :param name: Optional name, in NOne then `*` is used for any
        :return: Dependency instance of the requested type or None
        """
        result = self.try_get(t_dep, name)
        if result is None:
            raise ValueError(f"Could not resolve dependency requirement {t_dep}('{name}')"
                             f"Revise chassis dependency registration like `chassis.deps.register({t_dep}, instance, '{name}')`")
        return result


class Injector:
    """
    Facilitates Dependency resolution and injection from `DIContainer` instance mounted on the
    current application chassis.

    Examples:
       For example, in a FastAPI application you can succinctly declare injectable dependencies
       using `typing.Annotated` and `fastapi.Depends`:

       ```python

        WeatherDep = Annotated[IWeatherService, Depends(Injector(IWeatherService, "national"))]

        @app.get("/weather/")
        async def get_weather(weather: WeatherDep):
            return weather.get_hourly('Elm Shores, TX')

        @app.get("/weather2/")  # or use `inject(T)` FastAPI helper
        async def get_weather2(weather: inject(IWeather)):
            return weather.get_hourly('Another Town, OH')
       ```
    """
    def __init__(self, target_type: Type[Any], target_name: str| None = None):
       self.target_type = target_type
       self.target_name = target_name

    def __call__(self) -> Any:
        chassis = AppChassis.get_current_instance()
        return chassis.deps.get(self.target_type, self.target_name)


class AppChassis(DisposableObject):
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
      """
      Returns the ever-present default Application class instance.
      This is a framework internal method which should not be utilized in business apps
      """
      return AppChassis.__s_default # pyright: ignore[reportReturnType]

    @staticmethod
    def get_current_instance() -> "AppChassis":
      """
      Returns the current Application singleton which was allocated the last.
      If not explicit allocation was ever made then the default instance is returned.
      This is a framework internal method which should not be utilized much is ever in business apps
      which should use DI instead
      """
      current = AppChassis.__s_current
      return current if current is not None else AppChassis.__s_default # pyright: ignore[reportReturnType]

    def __init__(self,
                 app_id: str,
                 ep_path: str,
                 environment_name: str | None = None,
                 config: ConfigParser | None = None):
        existing = AppChassis.__s_current
        if existing is not None:
            raise RuntimeError(f"AppChassis({existing.app}) instance is already allocated. Dispose it first")

        super().__init__()

        self._instance_id = uuid.uuid4().hex
        self._components: List[AppComponent] = []
        self._entry_point_path = os.path.abspath(ep_path)
        self._app = app_id if app_id else DEFAULT_APP_ID
        self._instance_tag = self._instance_id[:8] # Tag is a shortened app id
        self._environment = self._get_environment(environment_name)
        self._host = platform.node()
        self._deps = DIContainer()
        # Must be after _env
        self._config = self._load_config(config) # use the supplied one or load co-located file

        if AppChassis.__s_default is None:
            AppChassis.__s_default = self
            self._is_default = True
        else:
            AppChassis.__s_current = self
            self._is_default = False

        # Notify all dependencies
        for callback in AppChassis.__s_global_dependency_callbacks:
            if callable(callback):
                callback()

    @override
    def dispose(self) -> None:
        if self._is_default:
            # Never dispose default instance, it is always present and should not be disposed
            return

        super().dispose()

    @override
    def _dispose(self) -> None:
        # Not called for default instance

        logger = logging.getLogger("AppChassis")

        all = self._components.copy() # copy to avoid concurrent modification during dispose
        all.reverse()
        for c in all:
            try:
                c.dispose()
            except Exception as ex:
                error = f"Error disposing component {c.__class__.__name__}: {ex}"
                logger.critical(error)


        AppChassis.__s_current = None

        # Notify all dependencies AFTER context switch
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

       environment_name = os.getenv(ENV_ENVIRONMENT_NAME_VAR,
                                    os.getenv(ENV_ENVIRONMENT_NAME_VAR.lower(), DEFAULT_ENV_NAME))

       return environment_name.lower() if environment_name else DEFAULT_ENV_NAME

    def _load_config(self, config: ConfigParser | None) -> ConfigParser:
        """
        Loads config INI file co-located with the entry point.
        The file takes format: `main-ENV.ini` where `ENV` is the name of your environment,
        for example:  `./main-dev.ini`, `./main-prod.ini` etc.
        If environment specific file is not found, then system tries to load from
        non-environment file such as `./main.ini`
        """
        if config is not None:
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
            for x in range(INCLUDE_MAX_DEPTH):
                was = source
                source = process_includes(path.parent,
                                          source,
                                          expand_vars=True,
                                          chassis=self) #  #include<!../cfg/log-$(ENV_NAME).ini>
                if was == source: break
            # ------------------
            config.read_string(source, f"Interpolated config `{str(fn)}`")

        return config

    @property
    def is_default(self) -> bool:
        """Return True if this is a default Application instance"""
        return self._is_default

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

    @property
    def components(self) -> Sequence["AppComponent"]:
        """
        Returns a sequence of components which are registered with this chassis.
        You can use this for runtime introspection of what components are present in the system, for diagnostics.
        Returns a readonly copy of the internal component registry
        """
        return tuple(self._components)

    @property
    def deps(self) -> DIContainer:
        """
        Returns `DIContainer` which you use to register at entry point and then resolve application dependencies
        at runtime.

        This is the cornerstone of dependency injection solution, acting as a chassis-central service locator,
        you outline application logic as service contracts and then provide various implementations for them.
        At the application entry, we register dependencies by associating an optionally-named instance of the
        said service of interest with the resolver (this property).

        At runtime various other components can now
        polymorphically resolve or inject dependencies into themselves
        """
        return self._deps



class AppComponent(DisposableObject):
    """
    Base class for application components which are aware of the chassis and can access its properties and dependencies.
    Application components get auto registered with app chassis, this way we can get a list of all application
    components at runtime by accessing `chassis.components` property. This can be used for diagnostics, monitoring, etc.

    Note:
     It is app components that own other components (directors). Directors (owners) should know how to deterministically
     dispose their owned components, but the chassis does not dispose them, it is the responsibility of the owners.
    """

    _s_sid_counter = 0

    def __init__(self, chassis: AppChassis, director: Optional["AppComponent"] = None) -> None:
        if chassis is None:
            raise ValueError(f"AppComponent->{self.__class__.__name__} requires a non-null AppChassis reference")

        if director is not None:
            if not isinstance(director, AppComponent):
                raise TypeError(f"AppComponent->{self.__class__.__name__} director must be of type AppComponent or None")

            if director._chassis != chassis:
                raise ValueError(f"AppComponent->{self.__class__.__name__} director component chassis mismatch")

        super().__init__()

        AppComponent._s_sid_counter += 1

        self._sid = AppComponent._s_sid_counter
        self._chassis = chassis
        self._director = director
        self._chassis._components.append(self) # Register component with the chassis, so we can get a list of all components


    @override
    def _dispose(self) -> None:
        try:
            self._chassis._components.remove(self) # Remove self from chassis registry
        except ValueError: pass # if not found, ignore. This is the most efficient way

    @property
    def sid(self) -> int:
        """
        Returns a numeric sys id of this component, which is unique within the application instance. It is assigned
        sequentially in order of component creation. Among other things it is used for component listing in tools
        """
        return self._sid

    @property
    def chassis(self) -> AppChassis:
        """Returns the application chassis instance associated with this component"""
        return self._chassis

    @property
    def director(self) -> Optional["AppComponent"]:
        """
        Returns the director component which owns/directs this component, or None if this component is not owned by
        any other component. Directors typically own the lifetime of their components, meaning that when a director gets disposed,
        it disposes all of its components as well. This is a common pattern in component-based architectures.
        """
        return self._director


def _atexit_cleanup():
    AppChassis.get_current_instance().dispose()

atexit.register(_atexit_cleanup)


# Allocate default instance of chassis
AppChassis(DEFAULT_APP_ID, __file__)
