# strands-postgres-store

A **PostgreSQL + pgvector** `MemoryStore` for [Strands Agents](https://strandsagents.com) — semantic long-term agent memory backed by native `pgvector` similarity search (the `<=>` cosine-distance operator over an HNSW index). No external vector database.

```bash
pip install strands-postgres-store
```

```python
from strands import Agent
from strands.memory import MemoryManager
from strands_postgres_store import PostgresMemoryStore

store = PostgresMemoryStore(name="user-memories", url="postgresql://user:pass@localhost:5432/db")
agent = Agent(memory_manager=MemoryManager(stores=[store]))

await store.add("The user prefers dark mode", metadata={"kind": "pref"})
hits = await store.search("what theme does the user like?")
```

## How it works

- **Semantic recall** via pgvector: `ORDER BY embedding <=> query` (cosine distance) over an HNSW index — native ANN in Postgres.
- **You bring the embeddings.** Default embedder is **Amazon Bedrock Titan Text v2** (1024-dim, cosine); pass any `embedder` callable for OpenAI / Cohere / local models.
- Each `add` stores a row `{id, content, embedding vector, metadata jsonb, created_at}`; `search` embeds the query and runs the ANN search, surfacing the distance as `_score`.
- The table, the `vector` extension, and the HNSW index are created automatically.

## Requirements

The **pgvector** extension must be installed on the server. On Debian/Ubuntu: `apt install postgresql-16-pgvector`; on macOS (Homebrew): `brew install pgvector`; managed services (RDS, Cloud SQL, Azure) expose it as an extension. The store runs `CREATE EXTENSION IF NOT EXISTS vector` on init.

## Configuration

`PostgresMemoryStore(name, url=None, *, table_name="strands_memory", engine=None, description=None, max_search_results=None, writable=True, extraction=None, embedder=None, dimensions=1024, region_name=None)`

> The memory **store** (`strands-postgres-store`) is distinct from the byte **storage** backend ([`strands-postgres-storage`](https://pypi.org/project/strands-postgres-storage/)). Also published as `strands-store-postgres`.

## License

MIT
