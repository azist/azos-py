"""
Provides database sharding functionality which spreads data across multiple data nodes

Copyright (C) 2011 - 2026 Azist, MIT License
"""

from typing import Optional

from azos.chassis import AppChassis, AppComponent, ConfigError
from azos.descriptor import Descriptor


class TrieShardRouter(AppComponent):
    """
    Sharding is a technique of distributing data across multiple independent database nodes, allowing for horizontal scaling.
    This class is responsible for routing shard hashes to the appropriate shard nodes using a trie data structure.
    This allows for efficient and scalable consistent routing of database requests across multiple shards.

    By design this structure supports up to 10 levels of depth, providing 2^10 (1024) possible leaf nodes for shard routing.

    ATTENTION!!! You may lose data routing and disrupt your system if you modify this code.
    Do not modify this code unless you are fully aware of the implications on the consistent shard routing logic and the
    potential impact on data distribution across shards.
    """

    MAX_DEPTH = 10  # Maximum depth of the trie 2^10 = 1024 possible shard nodes

    def __init__(
        self,
        chassis: AppChassis,
        cfg: Descriptor,
        director: Optional["AppComponent"] = None,
    ) -> None:
        super().__init__(chassis, director)
        self._root = TrieNode(cfg, 0, 0)

    def route_gdid8(self, gdid8: int) -> "TrieNode":
        """
        Routes the given GDID8 value to the appropriate shard node within the trie.
        The GDID8 value is first converted to a shard hash using the GDID8.get_shard_hash method,
        and then routed using the route method.
        This provides a convenient way to route GDID8 values directly without manually extracting the shard hash.
        """
        from azos.gdid8 import GDID8

        path = GDID8.get_shard_hash(gdid8)
        return self.route(path)

    def route(self, path: int) -> "TrieNode":
        """
        Routes the given shard hash to the appropriate shard node within the trie.
        This is a form of consistent hashing, where the shard path determines the path within the trie,
        ensuring that the same shard path will always route to the same shard node, providing a stable and predictable
        distribution of keys across shards.
        The shard path is interpreted in binary, and the trie is traversed accordingly.
        The lowest bit represents the fastest changing direction in the trie, determining the initial steps in the
         navigation path within the consistent shard tree.
        If the shard hash leads to a non-existent child, the current leaf/terminal node is returned.
        This provides efficient routing without recursion overhead.
        """
        node = self._root

        for _ in range(
            self.MAX_DEPTH
        ):  # Limit the traversal to the maximum depth of the trie
            if path & 1:
                if node._right is None:
                    return node
                node = node._right
            else:
                if node._left is None:
                    return node
                node = node._left
            path >>= 1

        return node  # Return the last node reached if the maximum depth is reached

    def all_shards(self) -> list["TrieNode"]:
        """
        Returns a list of all leaf/terminal nodes in the trie, representing all available shard nodes.
        This is useful for enumerating all shards for operations that need to be performed across all shards,
        such as maintenance tasks or data aggregation.
        """
        shards = []
        stack = [self._root]

        while stack:  # loop is used instead of recursion to avoid function calls
            node = stack.pop()
            if node._left is None and node._right is None:
                shards.append(node)
            else:
                if node._right is not None:
                    stack.append(node._right)
                if node._left is not None:
                    stack.append(node._left)

        return shards


class TrieNode:
    """
    A node in the trie data structure used by the TrieShardRouter.
    Each node can have a left and right child, representing the binary branching of the trie.
    """

    def __init__(self, cfg: Descriptor, depth: int, path: int) -> None:
        self._cfg = cfg

        if depth > TrieShardRouter.MAX_DEPTH:
            raise ConfigError(
                f"Trie depth cannot exceed {TrieShardRouter.MAX_DEPTH} levels"
            )

        if path > (1 << TrieShardRouter.MAX_DEPTH):
            raise ConfigError(
                f"Trie path cannot exceed {(1 << TrieShardRouter.MAX_DEPTH)}"
            )

        self._depth = depth
        self._path = path

        left = cfg.as_descriptor("left")
        right = cfg.as_descriptor("right")
        self._left = TrieNode(left, depth + 1, path) if left is not None else None
        self._right = (
            TrieNode(right, depth + 1, path | (1 << depth))
            if right is not None
            else None
        )

    @property
    def cfg(self) -> Descriptor:
        """Returns the configuration descriptor associated with this trie node"""
        return self._cfg

    @property
    def depth(self) -> int:
        """Returns the depth of this trie node within the trie"""
        return self._depth

    @property
    def path(self) -> int:
        """
        Returns the path value of this trie node, representing its position in the trie.
        If you pass this path back into the route method, you will get back the same node, ensuring consistent routing
        """
        return self._path

    @property
    def left(self) -> Optional["TrieNode"]:
        """Returns the left child node of this trie node, or None if it does not exist and this is a leaf/terminal node"""
        return self._left

    @property
    def right(self) -> Optional["TrieNode"]:
        """Returns the right child node of this trie node, or None if it does not exist and this is a leaf/terminal node"""
        return self._right
