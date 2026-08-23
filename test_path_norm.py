import asyncio
from azos.chassis import AppChassis
from azos.descriptor import Descriptor
from azos.sky.ctree import ConfigTree, ConfigTreeDataSource

class MockTreeSource(ConfigTreeDataSource):
    async def get_children(self, path: str, asof: float) -> list[str] | None: return None
    async def fetch_level(self, path: str, asof: float) -> tuple[Descriptor, Descriptor] | None:
        return Descriptor({"path": path}), Descriptor({"path": path})

async def _do_test():
    app = AppChassis(app_id="testapp", ep_path=__file__)
    config = Descriptor({"type": "MockTreeSource"})
    tree = ConfigTree(app, None, config)
    async with app:
        paths = ["a", "a/", "a//", "a/ /", "a  /    /", "/ / / / / a", "        /       /a"]
        for p in paths:
            node = await tree.navigate(p)
            print(f"'{p}' -> '{node.path}'" if node else f"'{p}' -> None")
    app.dispose()

asyncio.run(_do_test())
