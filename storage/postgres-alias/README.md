# strands-storage-postgres

A **PostgreSQL** implementation of the [Strands Agents](https://strandsagents.com) unified `Storage` interface — durable bytes-under-string-keys for session snapshots, context offloading, memory stores, and anything that consumes `strands.storage.Storage`.

```bash
pip install strands-storage-postgres
```

```python
from strands_storage_postgres import PostgresStorage

storage = PostgresStorage("postgresql://user:pass@localhost:5432/db")
await storage.write("sessions/abc/state.json", b"...bytes...")
```

> This is an alternate distribution name for [`strands-postgres-storage`](https://pypi.org/project/strands-postgres-storage/); both install the same PostgreSQL `Storage` backend. Part of the [strands-agents-session](https://github.com/skamalj/strands-agents-session) family.

## License

MIT
