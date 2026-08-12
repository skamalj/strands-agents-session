# strands-mongodb-storage

A **MongoDB** implementation of the [Strands Agents](https://strandsagents.com) unified `Storage` interface — durable bytes-under-string-keys that backs session snapshots, context offloading, memory stores, and anything else that consumes `strands.storage.Storage`.

```bash
pip install strands-mongodb-storage
```

```python
from strands.storage import Storage
from strands_mongodb_storage import MongoDBStorage

storage = MongoDBStorage("mongodb://localhost:27017")
assert isinstance(storage, Storage)

await storage.write("sessions/abc/state.json", b"...bytes...")
data = await storage.read("sessions/abc/state.json")   # -> bytes | None
keys = await storage.list("sessions/")                 # sorted, prefix-matched
await storage.delete("sessions/abc/state.json")        # no-op if absent
```

## Interface

| Method | Behaviour |
|---|---|
| `write(key, data)` | Upsert bytes under a `/`-separated key |
| `read(key)` | Return the bytes, or `None` if absent |
| `delete(key)` | Delete the key (no-op if missing) |
| `list(prefix)` | Full keys matching the prefix, sorted ascending |

## Data model

One document per key: `{_id: <key>, data: <BinData>}` in a single collection (`strands_storage.storage` by default). An optional `prefix=` namespaces all keys. Blocking PyMongo calls run in a thread so the async interface never blocks the event loop.

## License

MIT
