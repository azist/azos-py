from azos.descriptor import Descriptor
from azos.chassis import AppChassis
from azos.db.sharding import TrieShardRouter
from azos.gdid8 import GDID8
import time

app = AppChassis.get_default_instance()
cfg = Descriptor({
    "node_id": "root",
    "left": {
        "node_id": "0",
        "left": {
            "node_id": "00",
            "left": { "connect_string": "pgSQL1" },
            "right": { "connect_string": "pgSQL2" }
        },
        "right": {
            "node_id": "01",
            "left": { "connect_string": "pgSQL3" },
            "right": { "connect_string": "pgSQL4" }
        }
    },
    "right": {
        "node_id": "1",
        "left": {
            "node_id": "10",
            "left": { "connect_string": "pgSQL5" },
            "right": { "connect_string": "pgSQL6" }
        },
        "right": {
            "node_id": "11",
            "left": { "connect_string": "pgSQL7" },
            "right": { "connect_string": "pgSQL8" }
        }
    }
})

router = TrieShardRouter(app, cfg)
counts = { f"pgSQL{i}": 0 for i in range(1, 9) }

start_time = time.perf_counter()

for i in range(10000):
    gdid = GDID8.encode(i % 256, 1234567890 + (i // 100), i % 1000)
    routed = router.route_gdid8(gdid)
    counts[routed.cfg.as_str("connect_string")] += 1

end_time = time.perf_counter()
elapsed = end_time - start_time

print(f"Elapsed: {elapsed}")
print(counts)
