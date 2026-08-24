# strands-mongodb-store

A **MongoDB Vector Search** `MemoryStore` for [Strands Agents](https://strandsagents.com) — semantic long-term agent memory using **Automated Embedding**: MongoDB generates the embeddings itself (via Voyage AI), so you store **plain text** and query with **plain text** — no external embedder, no vectors to manage.

```bash
pip install strands-mongodb-store
```

```python
from strands import Agent
from strands.memory import MemoryManager
from strands_mongodb_store import MongoDBMemoryStore

store = MongoDBMemoryStore(
    name="user-memories",
    connection_string="mongodb://localhost:27017",   # self-managed, or an Atlas SRV URI
    database_name="agent", collection_name="memory",
    model="voyage-4-lite",
)
agent = Agent(memory_manager=MemoryManager(stores=[store]))

await store.add("The user prefers dark mode", metadata={"kind": "pref"})
hits = await store.search("what theme does the user like?")
```

## How it works

- **Automated Embedding.** The vector index is created with a `type: "autoEmbed"` field and a Voyage model; MongoDB embeds your `content` at index-time and your query text at query-time. `add` stores just `{_id, content, metadata, createdAt}` — no vectors in your documents.
- **Semantic recall** via `$vectorSearch` (`"query": <text>`), ranked by `vectorSearchScore`, surfaced as `_score`.
- The vector index is created automatically if absent.

## Requirements

MongoDB **Vector Search** with **Automated Embedding**, on either:
- **MongoDB Atlas**, or
- **self-managed MongoDB Community 8.2+** running the **`mongot`** binary (Linux; Docker / tarball / package / K8s).

Automated Embedding needs a **Voyage AI API key** configured on the deployment (Atlas, or `mongot` for Community). Models: `voyage-4-lite` (default), `voyage-4`, `voyage-4-large`, `voyage-code-3`.

> The memory **store** (`strands-mongodb-store`) is distinct from the byte **storage** backend ([`strands-mongodb-storage`](https://pypi.org/project/strands-mongodb-storage/)). Also published as `strands-store-mongodb`. **0.2.0** switched from manual embeddings to Automated Embedding (breaking).

## License

MIT
