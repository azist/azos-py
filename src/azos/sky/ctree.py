"""
Hierarchical Configuration Tree functionality.

Override `ConfigTreeDataSource` to provide custom data fetching logic for the configuration tree.
Nodes are fetched on-demand from the data source and can be cached for efficient access.

The effective config is calculated by merging the configuration from the root node down to the specified node,
with child nodes overriding parent nodes where applicable. See `Descriptor.override_by` for details on how the
merging is performed.


Copyright (C) 2020 - 2026 Azist, MIT License
"""

import asyncio
import copy
import time
from typing import cast, override
from abc import abstractmethod

from azos.cache import LimitedCache
from azos.chassis import AppChassis, AppComponent
from azos.daemons import AsyncDaemon
from azos.descriptor import Descriptor
from azos.factoryutils import make_component_from_descriptor

# redo this - Make COnfig and Props Config inherits props do not
class ConfigTreeNode(Descriptor):
    """
    Represents a node in the configuration tree.
    """
    def __init__(self, data: dict, chassis: AppChassis | None, tree_path: str):
        super().__init__(data=data, chassis=chassis)
        self._tree_path = tree_path
        self._level_descriptor: Descriptor | None = None


    def clone(self) -> "ConfigTreeNode":
        """
        Creates a deep copy of the configuration tree node.
        """
        got =  ConfigTreeNode(copy.deepcopy(self._data), self.chassis, self._tree_path)
        return cast(ConfigTreeNode, got)

    @property
    def tree_path(self) -> str:
        return self._tree_path

    @property
    def level_descriptor(self) -> Descriptor:
        """
        Returns the descriptor representing the configuration at this level of the tree, without inheritance
        """
        return cast(Descriptor, self._level_descriptor)




class ConfigTreeDataSource(AppComponent):
    """
    Provides abstraction for a tree to get its data
    """
    def __init__(self, chassis: AppChassis, director: AppComponent, config: Descriptor):
        super().__init__(chassis, director=director)

    @abstractmethod
    async def fetch_level(self, path: str, asof: float) -> ConfigTreeNode | None:
        """
        Fetches the configuration tree node at the specified path and time.
        This method does not cache anything, it accesses data source directly every time it is called
        and this can take significant time depending on the data source (e.g. network requests, database queries).
        The thundering herd problem must be taken into account by the caller, this method does not implement any protection

        :param path: The path to fetch e.g. "/sys/app/myservice1/dev"
        :param asof: The Unix timestamp to use for temporal addressing.
        :return: The configuration tree node at the specified path, or None if not found.
        """
        return None



class ConfigTreeClient(AsyncDaemon):
    """
    Provides a client interface to interact with the configuration tree.
    The functionality is read-only by design and does not include setting/administering config tree data.
    """

    SECONDS_PER_DAY: int = 24 * 60 * 60

    def __init__(self, chassis: AppChassis, director: AppComponent, config: Descriptor):
        super().__init__(chassis, director=director)

        self._cache = LimitedCache(
                        config.as_int("cache_max_size") or 1024,
                        config.as_float("cache_ttl_sec") or 120
                    )

        self._data = make_component_from_descriptor(ConfigTreeDataSource, config, self.chassis, self)

        self._pending = {}

    @override
    async def do_work(self, stop_event: asyncio.Event):
        removed = self._cache.evict_old()
        if removed:
            self._log.info(f"Evicted {removed} old cache entries")


    @property
    def interval_s(self) -> float:
        return 3600


    def round_asof(self, asof: float) -> float:
        """
        Takes Unix timestamp and rounds it down to the nearest day.
        This defines the granularity of temporal addressing, by default set to 1 day effectively
        this design does not allow to change policies more than 1 time per day.
        You can override this method, but keep in mind that high granularity negates the benefits
        of caching as the cache will be frequently invalidated.
        """
        seconds = int(asof)
        return seconds - (seconds % self.SECONDS_PER_DAY)


    async def navigate(self, path: str, asof: float = 0, cache: bool = True) -> ConfigTreeNode | None:
        """
        Navigates the configuration tree to the specified path.

        :param path: The path to navigate to.
        :param asof: The Unix timestamp to use for temporal addressing.
        :param cache: Whether to use the cache for this navigation.
        :return: The configuration tree node at the specified path.
        """
        if path is None:
            raise ValueError("Path cannot be None")

        path = path.strip()
        if not path:
            raise ValueError("Path cannot be empty")

        if asof <= 0:
            asof = time.time()

        asof = self.round_asof(asof)

        return await self._navigate(path, asof, cache)


    async def _navigate(self, path: str, asof: float, cache: bool) -> ConfigTreeNode | None:
        key = f"{asof}::{path}"

        if cache:
            cached = cast(ConfigTreeNode | None, self._cache.get(key))
            if cached is ...: return None # sentinel value
            if cached is not None:
                return cached.clone()

        #prevent flooding the source
        if key in self._pending:
            fetched = await self._pending[key]
        else:
            fetch_task = asyncio.create_task(self._fetch_node(path, asof, cache))
            self._pending[key] = fetch_task
            try:
                fetched = await fetch_task
            finally:
                self._pending.pop(key, None)

        if cache:
            if fetched is None:
                self._cache.set(key, ...)
                return None

            self._cache.set(key, fetched)

        return fetched



    async def _fetch_node(self, path: str, asof: float, cache: bool) -> ConfigTreeNode | None:
        this = await self._data.fetch_level(path, asof)

        if this is None:
            return None

        if path == "/":
            return this

        parent_path = "/".join(path.strip("/").split("/")[:-1])
        if parent_path == "": parent_path = "/" #root

        parent = await self._navigate(parent_path, asof, cache) if parent_path else None

        if parent is None:
            return None

        result = parent
        result._level_descriptor = this
        result._tree_path = path # set the path to this node
        result.override_by(this) # inheritance happens here

        return result
