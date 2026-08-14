from azos.descriptor import Descriptor
from azos.chassis import AppChassis
from azos.db.sharding import TrieShardRouter

app = AppChassis("test", __file__, "dev")
cfg = Descriptor({
    "node_id": "root",
    "left": {
        "node_id": "l",
        "left": { "node_id": "ll" },
        "right": { "node_id": "lr" }
    },
    "right": {
        "node_id": "r"
    }
})

router = TrieShardRouter(app, cfg)

shards = router.all_shards()
for s in shards:
    r = router.route(s.path)
    print(f"Node: {s.cfg.as_str('node_id')}, Depth: {s.depth}, Path: {s.path}, Routed back to: {r.cfg.as_str('node_id')}")

