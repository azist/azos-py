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

    def __init__(self, chassis: AppChassis, cfg: Descriptor,  director: Optional["AppComponent"] = None) -> None:
        super().__init__(chassis, director)
        self._root = TrieNode(cfg, 0)


    def route_gdid8(self, gdid8: int) -> "TrieNode":
        """
        Routes the given GDID8 value to the appropriate shard node within the trie.
        The GDID8 value is first converted to a shard hash using the GDID8.get_shard_hash method,
        and then routed using the route method.
        This provides a convenient way to route GDID8 values directly without manually extracting the shard hash.
        """
        from azos.gdid8 import GDID8
        shard_hash = GDID8.get_shard_hash(gdid8)
        return self.route(shard_hash)


    def route(self, shard_hash: int) -> "TrieNode":
        """
        Routes the given shard hash to the appropriate shard node within the trie.
        This is a form of consistent hashing, where the shard hash determines the path within the trie,
        ensuring that the same shard hash will always route to the same shard node, providing a stable and predictable
        distribution of keys across shards.
        The shard hash is interpreted in binary, and the trie is traversed accordingly.
        The lowest bit represents the fastest changing direction in the trie, determining the initial steps in the
         navigation path within the consistent shard tree.
        If the shard hash leads to a non-existent child, the current leaf/terminal node is returned.
        This provides efficient routing without recursion overhead.
        """
        node = self._root

        for _ in range(self.MAX_DEPTH):  # Limit the traversal to the maximum depth of the trie
            if shard_hash & 1:
                if node._right is None:
                    return node
                node = node._right
            else:
                if node._left is None:
                    return node
                node = node._left
            shard_hash >>= 1

        return node  # Return the last node reached if the maximum depth is reached


class TrieNode:
    """
    A node in the trie data structure used by the TrieShardRouter.
    Each node can have a left and right child, representing the binary branching of the trie.
    """
    def __init__(self, cfg: Descriptor, depth: int) -> None:
        self._cfg = cfg
        self._depth = depth
        if depth > TrieShardRouter.MAX_DEPTH:
            raise ConfigError(f"Trie depth cannot exceed {TrieShardRouter.MAX_DEPTH} levels")

        left = cfg.as_descriptor('left')
        right = cfg.as_descriptor('right')
        self._left = TrieNode(left, depth + 1) if left is not None else None
        self._right = TrieNode(right, depth + 1) if right is not None else None

    @property
    def cfg(self) -> Descriptor:
        """Returns the configuration descriptor associated with this trie node"""
        return self._cfg

    @property
    def depth(self) -> int:
        """Returns the depth of this trie node within the trie"""
        return self._depth

    @property
    def left(self) -> Optional["TrieNode"]:
        """Returns the left child node of this trie node, or None if it does not exist and this is a leaf/terminal node"""
        return self._left

    @property
    def right(self) -> Optional["TrieNode"]:
        """Returns the right child node of this trie node, or None if it does not exist and this is a leaf/terminal node"""
        return self._right



