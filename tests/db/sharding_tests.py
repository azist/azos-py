import random

import pytest

from azos.descriptor import Descriptor
from azos.chassis import AppChassis, ConfigError
from azos.db.sharding import TrieShardRouter


@pytest.fixture
def app():
    # Use default app chassis instance
    return AppChassis.get_default_instance()


def test_trie_shard_router_one_node(app):
    cfg = Descriptor({"node_id": "root"})
    router = TrieShardRouter(app, cfg)

    shards = router.all_shards()
    assert len(shards) == 1

    node = shards[0]
    assert node.cfg.as_str("node_id") == "root"
    assert node.path == 0
    assert node.depth == 0

    routed = router.route(node.path)
    assert routed is node


def test_trie_shard_router_four_nodes(app):
    cfg = Descriptor(
        {
            "node_id": "root",
            "left": {
                "node_id": "l",
                "left": {"node_id": "ll"},
                "right": {"node_id": "lr"},
            },
            "right": {"node_id": "r"},
        }
    )

    router = TrieShardRouter(app, cfg)

    shards = router.all_shards()
    assert len(shards) == 3

    for s in shards:
        routed = router.route(s.path)
        assert routed is s, (
            f"Node {s.cfg.as_str('node_id')} with path {s.path} routed incorrectly"
        )


def test_trie_shard_router_skewed_left(app):
    # Depth 4, all left
    cfg = Descriptor(
        {
            "node_id": "root",
            "left": {
                "node_id": "l",
                "left": {
                    "node_id": "ll",
                    "left": {"node_id": "lll", "left": {"node_id": "llll"}},
                },
            },
        }
    )

    router = TrieShardRouter(app, cfg)
    shards = router.all_shards()
    assert len(shards) == 1
    assert shards[0].path == 0

    assert router.route(shards[0].path) is shards[0]


def test_trie_shard_router_skewed_right(app):
    # Depth 3, all right
    cfg = Descriptor(
        {
            "node_id": "root",
            "right": {
                "node_id": "r",
                "right": {
                    "node_id": "rr",
                    "right": {
                        "node_id": "rrr",
                    },
                },
            },
        }
    )

    router = TrieShardRouter(app, cfg)
    shards = router.all_shards()
    assert len(shards) == 1
    assert shards[0].path == 7  # 1 + 2 + 4

    assert router.route(shards[0].path) is shards[0]


def test_trie_shard_router_full_tree(app):
    # 3 levels deep = 8 leaf nodes
    def build_full_tree(depth, max_depth, prefix=""):
        if depth == max_depth:
            return {"node_id": prefix}
        return {
            "node_id": prefix,
            "left": build_full_tree(depth + 1, max_depth, prefix + "l"),
            "right": build_full_tree(depth + 1, max_depth, prefix + "r"),
        }

    cfg_dict = build_full_tree(0, 3, "root")
    cfg = Descriptor(cfg_dict)

    router = TrieShardRouter(app, cfg)
    shards = router.all_shards()
    assert len(shards) == 8

    for s in shards:
        routed = router.route(s.path)
        assert routed is s, (
            f"Node {s.cfg.as_str('node_id')} with path {s.path} routed incorrectly"
        )


def test_trie_shard_router_deep(app):
    cfg = Descriptor(
        {
            "node_id": "root",
            "left": {"node_id": "l"},
            "right": {
                "node_id": "r",
                "left": {"node_id": "rl", "right": {"node_id": "rlr"}},
            },
        }
    )

    router = TrieShardRouter(app, cfg)

    shards = router.all_shards()
    assert len(shards) == 2

    for s in shards:
        routed = router.route(s.path)
        assert routed is s, f"Node {s.cfg.as_str('node_id')} routed differently"


def test_trie_shard_router_route_gdid8(app):
    cfg = Descriptor(
        {
            "node_id": "root",
            "left": {
                "node_id": "l",
            },
            "right": {"node_id": "r"},
        }
    )
    router = TrieShardRouter(app, cfg)
    # The route_gdid8 converts gdid8 integer to shard_hash and routes it.
    # To properly route gdid8, we just need to ensure the method executes and returns a node
    node = router.route_gdid8(123456789)
    assert node is not None
    assert node.depth in (1,)


def test_trie_shard_router_max_depth(app):
    # build 11 depth tree
    def build_tree(depth):
        if depth == 11:
            return {"node_id": "leaf"}
        return {"node_id": f"node{depth}", "left": build_tree(depth + 1)}

    cfg = Descriptor(build_tree(0))
    with pytest.raises(ConfigError, match="Trie depth cannot exceed"):
        TrieShardRouter(app, cfg)


def test_trie_shard_router_max_depth_full_tree(app):
    # build 10 depth full tree = 1024 leaves
    def build_full_tree(depth, max_depth):
        if depth == max_depth:
            return {"node_id": "leaf"}
        return {
            "node_id": f"node{depth}",
            "left": build_full_tree(depth + 1, max_depth),
            "right": build_full_tree(depth + 1, max_depth),
        }

    cfg_dict = build_full_tree(0, 10)
    cfg = Descriptor(cfg_dict)

    router = TrieShardRouter(app, cfg)

    shards = router.all_shards()
    assert len(shards) == 1024  # 2^10 = 1024

    for s in shards:
        routed = router.route(s.path)
        assert routed is s, f"Node with path {s.path} routed incorrectly"


def test_trie_shard_router_semantic_db_connection(app):

    # Example database configuration with 4 shards, each having a unique connection string
    cfg = Descriptor(
        {
            "node_id": "root",
            "left": {
                "node_id": "l",
                "left": {"connect_string": "pgSQL1"},
                "right": {"connect_string": "pgSQL2"},
            },
            "right": {
                "node_id": "r",
                "left": {"connect_string": "pgSQL3"},
                "right": {"connect_string": "pgSQL4"},
            },
        }
    )

    router = TrieShardRouter(app, cfg)

    shards = router.all_shards()
    assert len(shards) == 4

    # Test random paths with bit length > 4
    paths_and_expected = [
        (0b10100, "pgSQL1"),  # Ends in 00 -> left, left
        (0b11010, "pgSQL2"),  # Ends in 10 -> left, right
        (0b10001, "pgSQL3"),  # Ends in 01 -> right, left
        (0b11111, "pgSQL4"),  # Ends in 11 -> right, right
        (100, "pgSQL1"),  # 100 = 0b1100100 -> 00
        (102, "pgSQL2"),  # 102 = 0b1100110 -> 10
        (101, "pgSQL3"),  # 101 = 0b1100101 -> 01
        (103, "pgSQL4"),  # 103 = 0b1100111 -> 11
        (0b1111111100, "pgSQL1"),
        (0b1111111110, "pgSQL2"),
        (0b1111111101, "pgSQL3"),
        (0b1111111111, "pgSQL4"),
    ]

    for path, expected_conn in paths_and_expected:
        routed = router.route(path)
        assert routed.cfg.as_str("connect_string") == expected_conn


import time
from azos.gdid8 import GDID8


def test_trie_shard_router_gdid8_distribution(app):
    cfg = Descriptor(
        {
            "node_id": "root",
            "left": {
                "node_id": "0",
                "left": {
                    "node_id": "00",
                    "left": {"connect_string": "pgSQL1"},
                    "right": {"connect_string": "pgSQL2"},
                },
                "right": {
                    "node_id": "01",
                    "left": {"connect_string": "pgSQL3"},
                    "right": {"connect_string": "pgSQL4"},
                },
            },
            "right": {
                "node_id": "1",
                "left": {
                    "node_id": "10",
                    "left": {"connect_string": "pgSQL5"},
                    "right": {"connect_string": "pgSQL6"},
                },
                "right": {
                    "node_id": "11",
                    "left": {"connect_string": "pgSQL7"},
                    "right": {"connect_string": "pgSQL8"},
                },
            },
        }
    )

    router = TrieShardRouter(app, cfg)
    shards = router.all_shards()
    assert len(shards) == 8

    counts = {f"pgSQL{i}": 0 for i in range(1, 9)}

    start_time = time.perf_counter()

    generator = GDID8(0x55)

    for i in range(10000):
    #    if random.random() > 0.85: time.sleep(0.001)
        gdid = generator.generate()
        routed = router.route_gdid8(gdid)
        counts[routed.cfg.as_str("connect_string")] += 1 # type: ignore

    end_time = time.perf_counter()
    elapsed = end_time - start_time

     # DKh LINAI: 10,000 GDID8 routed in 0.0324 seconds = 308K ops/sec
    print(f"\n10,000 GDID8 routed in {elapsed:.4f} seconds")

    assert elapsed < 1.0, f"Routing took too long: {elapsed:.4f}s"

    # Test distribution curve
    # It loops exactly 10,000 times, storing the generated connections into a dictionary.
    # The assertions check the distribution curve (making sure no node is starved under 500 routes or
    # overused over 2000 routes, which tests for statistically uniform hash properties) and records the
    # elapsed perf_counter!

    for k, count in counts.items():
        print(f"Shard {k} got {count} routes")
        assert count > 500, (
            f"Shard {k} only got {count} routes, expected uniform distribution"
        )
        assert count < 2000, (
            f"Shard {k} got too many routes: {count}, expected uniform distribution"
        )
