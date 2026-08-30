import pytest
import asyncio
from azos.chassis import AppChassis
from azos.descriptor import Descriptor
from azos.sky.ctree import ConfigTree, ConfigTreeDataSource
from azos.factoryutils import knownas

MOCK_TREE = {
    "/": {
        "config": {"env": "prod", "timeout": 10},
        "props": {"desc": "root node"},
        "children": ["/a", "/b"]
    },
    "/a": {
        "config": {"timeout": 20, "retries": 3},
        "props": {"desc": "node a"},
        "children": ["/a/c"]
    },
    "/b": {
        "config": {"env": "dev"},
        "props": {"desc": "node b"},
        "children": []
    },
    "/a/c": {
        "config": {"mode": "fast"},
        "props": {"desc": "leaf c"},
        "children": []
    }
}

@knownas("MockTreeSource")
class MockTreeSource(ConfigTreeDataSource):

    async def get_children(self, path: str, asof: float) -> list[str] | None:
        node = MOCK_TREE.get(path)
        if node is None:
            return None
        return node["children"]

    async def fetch_level(self, path: str, asof: float) -> tuple[Descriptor, Descriptor] | None:
        node = MOCK_TREE.get(path)
        if node is None:
            return None
        return Descriptor(node["config"]), Descriptor(node["props"])

def test_config_tree_navigation():
    async def _do_test():
        app = AppChassis(app_id="testapp", ep_path=__file__)

        try:
            config = Descriptor({
                "data-source": {"type": "MockTreeSource"}
            })

            tree = ConfigTree(app, None, config)

            async with app:
                # Root
                root_node = await tree.navigate("/")
                assert root_node is not None
                assert root_node.path == "/"
                assert root_node.props.as_str("desc") == "root node"
                assert root_node.level_config.as_int("timeout") == 10
                assert root_node.config.as_int("timeout") == 10
                assert root_node.config.as_str("env") == "prod"

                # Children of root
                children = await tree._data.get_children("/", 0)
                assert children == ["/a", "/b"]

                # Sub path /a
                a_node = await tree.navigate("/a")
                assert a_node is not None
                assert a_node.path == "/a"
                assert a_node.props.as_str("desc") == "node a"
                assert a_node.level_config.as_int("timeout") == 20
                assert a_node.level_config.as_int("retries") == 3

                # Effective config merges parent's config + node's level config
                assert a_node.config.as_str("env") == "prod" # from root
                assert a_node.config.as_int("timeout") == 20 # overridden by /a
                assert a_node.config.as_int("retries") == 3 # from /a

                # Sub path /b
                b_node = await tree.navigate("/b")
                assert b_node is not None
                assert b_node.path == "/b"
                assert b_node.props.as_str("desc") == "node b"
                assert b_node.level_config.as_str("env") == "dev"
                assert b_node.config.as_str("env") == "dev" # overridden by /b
                assert b_node.config.as_int("timeout") == 10 # from root

                # Deep sub path /a/c
                c_node = await tree.navigate("/a/c")
                assert c_node is not None
                assert c_node.path == "/a/c"
                assert c_node.props.as_str("desc") == "leaf c"
                assert c_node.level_config.as_str("mode") == "fast"
                assert c_node.config.as_str("env") == "prod" # from root
                assert c_node.config.as_int("timeout") == 20 # from /a
                assert c_node.config.as_int("retries") == 3 # from /a
                assert c_node.config.as_str("mode") == "fast" # from /a/c

                # Non-existent path
                missing_node = await tree.navigate("/x/y/z")
                assert missing_node is None
        finally:
            app.dispose()

    asyncio.run(_do_test())


def test_config_tree_navigation_path_normalization():
    async def _do_test():
        app = AppChassis(app_id="testapp", ep_path=__file__)

        try:
            config = Descriptor({
                "data-source": {"type": "MockTreeSource"},
            })

            tree = ConfigTree(app, None, config)

            async with app:
                paths_to_test = [
                    "a",
                    "a/",
                    "a//",
                    "a/ /",
                    "a  /    /",
                    "/ / / / / a",
                    "        /       /a"
                ]

                # All paths should normalize to "/a" and resolve the a_node successfully
                for p in paths_to_test:
                    node = await tree.navigate(p)
                    assert node is not None, f"Path '{p}' failed to resolve"
                    assert node.path == "/a", f"Path '{p}' resolved to wrong path '{node.path}'"
                    assert node.props.as_str("desc") == "node a"
                    assert node.level_config.as_int("timeout") == 20
        finally:
            app.dispose()

    asyncio.run(_do_test())
