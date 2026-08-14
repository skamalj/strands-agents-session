# strands-postgres-storage

A **PostgreSQL** implementation of the [Strands Agents](https://strandsagents.com) unified `Storage` interface — durable bytes-under-string-keys that backs session snapshots, context offloading, memory stores, and anything that consumes `strands.storage.Storage`.

```bash
pip install strands-postgres-storage
```

```python
from strands.storage import Storage
from strands_postgres_storage import PostgresStorage

storage = PostgresStorage("postgresql://user:pass@localhost:5432/db")
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

A single table (`strands_storage` by default) of `(key VARCHAR PRIMARY KEY, data BYTEA)`, created automatically. An optional `prefix=` namespaces all keys. Built on the SQLAlchemy-backed [`strands-sql-storage`](https://pypi.org/project/strands-sql-storage/) — `PostgresStorage` is `SQLStorage` under a PostgreSQL-specific name; blocking calls run in a thread so the async interface never blocks the event loop.

## License

MIT
