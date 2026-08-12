# strands-sql-storage

A **SQL (SQLAlchemy)** implementation of the [Strands Agents](https://strandsagents.com) unified `Storage` interface — durable bytes-under-string-keys that backs session snapshots, context offloading, memory stores, and anything else that consumes `strands.storage.Storage`. One provider for any SQLAlchemy-supported database (SQLite, PostgreSQL, MySQL, …), selected purely by connection URL.

```bash
pip install strands-sql-storage
```

```python
from strands.storage import Storage
from strands_sql_storage import SQLStorage

storage = SQLStorage("postgresql://user:pass@localhost/db")   # or engine=<Engine>
assert isinstance(storage, Storage)

await storage.write("sessions/abc/state.json", b"...bytes...")
data = await storage.read("sessions/abc/state.json")          # -> bytes | None
keys = await storage.list("sessions/")                        # sorted, prefix-matched
await storage.delete("sessions/abc/state.json")               # no-op if absent
```

## Interface

Implements the four `Storage` operations over opaque bytes:

| Method | Behaviour |
|---|---|
| `write(key, data)` | Upsert bytes under a `/`-separated key |
| `read(key)` | Return the bytes, or `None` if the key is absent |
| `delete(key)` | Delete the key (no-op if missing) |
| `list(prefix)` | Full keys matching the prefix, sorted ascending |

## Data model

A single table (`strands_storage` by default) of `(key VARCHAR PRIMARY KEY, data BLOB)`, created automatically. An optional `prefix=` namespaces all keys within the table. Blocking SQLAlchemy calls run in a thread so the async interface never blocks the event loop.

## License

MIT
