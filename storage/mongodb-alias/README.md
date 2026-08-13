# strands-storage-mongodb

A **MongoDB** implementation of the [Strands Agents](https://strandsagents.com) unified `Storage` interface — durable bytes-under-string-keys for session snapshots, context offloading, memory stores, and anything that consumes `strands.storage.Storage`.

```bash
pip install strands-storage-mongodb
```

```python
from strands_storage_mongodb import MongoDBStorage

storage = MongoDBStorage("mongodb://localhost:27017")
await storage.write("sessions/abc/state.json", b"...bytes...")
```

> This is an alternate distribution name for [`strands-mongodb-storage`](https://pypi.org/project/strands-mongodb-storage/); both install the same MongoDB `Storage` backend. Part of the [strands-agents-session](https://github.com/skamalj/strands-agents-session) family.

## License

MIT
