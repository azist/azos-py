"""
LimitedCache provides an in-memory cache for objects with expiration and max_size constraints.

Copyright (C) 2018 - 2026 Azist, MIT License
"""

import time
from typing import Hashable


class LimitedCache:
    """
    Simple cache that imposes a maximum size and expiration time limits for its items.
    Allows getting, setting, deleting items.
    When size is exceeded the oldest item is evicted.
    When an item is expired it is removed from cache on next get.
    You can call `evict_old()` to remove all expired items from cache from the external callers.

    This class is NOT thread-safe.
    """

    MIN_SIZE = 8
    MAX_SIZE_DEFAULT = 8 * 1024
    MAX_SIZE_MAX = 8_000_000
    EXPIRATION_SECONDS_DEFAULT = 60 * 60 * 24  # 1 day

    def __init__(self, max_size: int = MAX_SIZE_DEFAULT, expiration_seconds: float = 0):
        """
        Initializes a new instance of the LimitedCache class.

        :param max_size: The maximum number of items the cache can hold. At least 8
        :param expiration_seconds: The time in seconds after which an item expires. If 0 or less, 1 day is used
        """
        self._max_size = max_size if max_size > LimitedCache.MIN_SIZE else LimitedCache.MIN_SIZE
        if self._max_size > LimitedCache.MAX_SIZE_MAX:
            self._max_size = LimitedCache.MAX_SIZE_MAX
        self._expiration_seconds = expiration_seconds if expiration_seconds > 0 else LimitedCache.EXPIRATION_SECONDS_DEFAULT
        self._cache = {}


    @property
    def max_size(self) -> int:
        """
        Gets the maximum number of items the cache can hold.

        :return: The maximum size of the cache.
        """
        return self._max_size


    @property
    def expiration_seconds(self) -> float:
        """
        Gets the time in seconds after which an item expires.

        :return: The expiration time in seconds.
        """
        return self._expiration_seconds


    @property
    def capacity(self):
        """
        Returns the number of items currently in the cache regardless of their expiration.
        """
        return len(self._cache)


    def get(self, key: Hashable, exp_sec: float = 0) -> object | None:
        """
        Retrieves an item from the cache by its key.

        :param key: The key of the item to retrieve.
        :param exp_sec: Optional expiration time in seconds for this specific get operation. If 0 or less, the default expiration is used.
        :return: The cached item if it exists and has not expired; otherwise, None.
        """
        item = self._cache.get(key, None)
        if item is None:
            return None
        value, timestamp = item
        expiration = exp_sec if exp_sec > 0 else self._expiration_seconds
        if time.time() - timestamp > expiration:
            del self._cache[key]
            return None
        return value


    def set(self, key: Hashable, value: object) -> bool:
        """
        Adds an item to the cache with the specified key.

        :param key: The key of the item to add.
        :param value: The item to add to the cache.
        :return: True if the item was added; False if it replaced an existing item.
        """
        if key is None or value is None:
            raise ValueError("Cannot add None key or value to the cache.")

        is_new = key not in self._cache
        if not is_new:
            del self._cache[key]  # remove to ensure the updated item is moved to the end

        self._cache[key] = (value, time.time())

        if len(self._cache) > self._max_size:
            # since dicts are insertion ordered and we re-insert on update,
            # the first item is always the oldest (smallest timestamp)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        return is_new


    def delete(self, key: Hashable) -> bool:
        """
        Removes an item from the cache by its key.

        :param key: The key of the item to remove.
        :return: True if the item was removed; False if the item was not found.
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False


    def clear(self) -> None:
        """
        Clears all items from the cache.
        """
        self._cache.clear()


    def evict_old(self, exp_sec: float = 0) -> int:
        """
        Evicts all expired items from the cache.
        Call this method periodically to remove expired items, for example in a daemon spin task.

        :param exp_sec: Optional expiration time in seconds for this specific evict operation. If 0 or less, the default expiration is used.
        :return: The number of items removed from the cache.
        """
        was = len(self._cache)

        now = time.time()
        expiration = exp_sec if exp_sec > 0 else self._expiration_seconds
        expired_keys = [k for k, v in self._cache.items() if now - v[1] > expiration]

        for k in expired_keys:
            self._cache.pop(k, None)

        removed = was - len(self._cache)
        return removed

