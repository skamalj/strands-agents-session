# strands-dynamodb-storage

An **Amazon DynamoDB** implementation of the [Strands Agents](https://strandsagents.com) unified `Storage` interface — durable bytes-under-string-keys that backs session snapshots, context offloading, memory stores, and anything else that consumes `strands.storage.Storage`.

```bash
pip install strands-dynamodb-storage
```

```python
from strands.storage import Storage
from strands_dynamodb_storage import DynamoDBStorage

storage = DynamoDBStorage("strands_storage")   # table auto-created if absent
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

A single table with string keys `PK` (HASH) / `SK` (RANGE), billed PAY_PER_REQUEST and auto-created. Every value shares one partition (`partition_value`, default `"storage"`) with the storage key as the sort key, so `list(prefix)` is an ordered `begins_with` query. For very large or high-throughput datasets this concentrates load on one partition — use separate tables or `partition_value`s per namespace to spread it. Blocking boto3 calls run in a thread so the async interface never blocks the event loop.

## License

MIT
