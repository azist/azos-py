"""
Hierarchical Configuration Tree functionality.

Configuration trees are hierarchical data structures navigable by string path similar to a file system.
Each node at every level is version controlled via "as-of" UTC timestamp making temporal navigation and historical
queries possible: when you resolve a path, you do this as-of a specific point in time.
Keep in mind: your parent node's configuration is considered as-of the same timestamp when resolving the effective
configuration for a child node and the parent node. This flexible design allows for maximum temporal consistency and
accurate historical queries.

Every level of the tree contains two data vectors: the effective configuration (`config`) and the node-specific properties (`props`).
The properties is not inherited from parent, whereas the effective config is inherited from the tree root all the way down to child nodes.

The tree feeds from source using a `ConfigTreeDataSource` implementation.
Override `ConfigTreeDataSource` to provide custom data fetching logic for the configuration tree.
Nodes are fetched on-demand from the data source and can be cached for efficient access.
The client interface to interact with the tree is provided by `ConfigTree`.

See `Descriptor.override_by` for details on how the effective configuration merging is performed.


Copyright (C) 2020 - 2026 Azist, MIT License
"""

import asyncio
import time
from typing import cast, override
from dataclasses import dataclass
from abc import abstractmethod

from azos.cache import LimitedCache
from azos.chassis import AppChassis, AppComponent
from azos.daemons import AsyncDaemon
from azos.descriptor import Descriptor
from azos.factoryutils import make_component_from_descriptor

_NOT_FOUND_SENTINEL = object()

@dataclass(frozen=True, slots=True)
class ConfigTreeNode:
    """Provides data for a node of config tree: (path, level, effective, props)"""

    path: str
    """The path of the node in the configuration tree."""

    level_config: Descriptor
    """The descriptor representing the configuration at this level of the tree, without inheritance."""

    config: Descriptor
    """The effective configuration descriptor, resulting from merging this node with its ancestors."""

    props: Descriptor
    """The properties descriptor specific to this node."""




class ConfigTreeDataSource(AppComponent):
    """
    Provides abstraction for a tree to get its data. This class is for tree consumption pattern, where the tree
    data is read-only. It is used in system configuration.

    Paired with `ConfigTree`, which provides a read-only client interface to interact with the configuration tree.
    """

    def __init__(self, chassis: AppChassis, director: AppComponent, config: Descriptor):
        super().__init__(chassis, director=director)

    @abstractmethod
    async def get_children(self, path: str, asof: float) -> list[str] | None:
        """
        Retrieves the list of child node paths for the specified node path as of the given time.
        You can use this method to build tree visualizers.
        Start with navigation from the root node at "/" path and recursively fetch children.

        :param path: The path of the node whose children are to be retrieved.
        :param asof: The Unix timestamp to use for temporal addressing.
        :return: List of child node paths or empty list, or None if the node does not exist.
        """
        pass


    @abstractmethod
    async def fetch_level(self, path: str, asof: float) -> tuple[Descriptor, Descriptor] | None:
        """
        Fetches the configuration tree node at the specified path and time.
        This method does not cache anything, it accesses data source directly every time it is called
        and this can take significant time depending on the data source (e.g. network requests, database queries).
        The thundering herd problem must be taken into account by the caller, this method does not implement any protection.
        The Descriptor objects returned must be created anew and not shared (as they might be mutated later by callers).

        :param path: The path to fetch e.g. "/sys/app/myservice1/dev"
        :param asof: The Unix timestamp to use for temporal addressing.
        :return: Tuple of (level_config, props) descriptors, or None if not found.
        """
        pass



class ConfigTree(AsyncDaemon):
    """
    Provides a client interface to interact with the configuration tree.
    The functionality is read-only by design and does not include setting/administering config tree data.

    In future we can create a writable counterpart to this class for managing config tree data
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

        if path != "/":
            path = "/" + path.strip("/")

        if asof <= 0:
            asof = time.time()

        asof = self.round_asof(asof)

        return await self._navigate(path, asof, cache)


    async def _navigate(self, path: str, asof: float, cache: bool) -> ConfigTreeNode | None:
        key = f"{asof}::{path}"

        if cache:
            cached = cast(ConfigTreeNode | None, self._cache.get(key))
            if cached is _NOT_FOUND_SENTINEL: return None # sentinel value
            if cached is not None:
                return cached

        #prevent flooding the source
        if key in self._pending:
            return await asyncio.shield(self._pending[key])

        async def _do_fetch_and_cache():
            try:
                fetched = await self._fetch_node(path, asof, cache)
                if cache:
                    if fetched is None:
                        self._cache.set(key, _NOT_FOUND_SENTINEL)
                    else:
                        self._cache.set(key, fetched)
                return fetched
            finally:
                self._pending.pop(key, None)

        fetch_task = asyncio.create_task(_do_fetch_and_cache())
        self._pending[key] = fetch_task
        return await asyncio.shield(fetch_task)



    async def _fetch_node(self, path: str, asof: float, cache: bool) -> ConfigTreeNode | None:
        fetched = await self._data.fetch_level(path, asof)

        if fetched is None:
            return None

        if path == "/":
            return ConfigTreeNode(path,
                                  level_config=fetched[0].seal(),
                                  config=Descriptor({}, self.chassis).seal(),
                                  props=fetched[1].seal())

        parts = path.strip("/").split("/")[:-1]
        parent_path = "/" + "/".join(parts) if parts else "/"

        parent = await self._navigate(parent_path, asof, cache) if parent_path else None

        if parent is None:
            return None

        # Clone parent's config to avoid mutating shared cached nodes
        merged_config = parent.config.clone()
        merged_config.override_by(fetched[0])

        result = ConfigTreeNode(path,
                                level_config=fetched[0].seal(),
                                config=merged_config.seal(),
                                props=fetched[1].seal())
        return result
