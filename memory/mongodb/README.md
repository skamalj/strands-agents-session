# strands-mongodb-store

A **MongoDB Atlas Vector Search** `MemoryStore` for [Strands Agents](https://strandsagents.com) — semantic long-term agent memory via Atlas `$vectorSearch`. No external vector database.

```bash
pip install strands-mongodb-store
```

```python
from strands import Agent
from strands.memory import MemoryManager
from strands_mongodb_store import MongoDBMemoryStore

store = MongoDBMemoryStore(
    name="user-memories",
    connection_string="mongodb+srv://user:pass@cluster.mongodb.net",
    database_name="agent", collection_name="memory",
)
agent = Agent(memory_manager=MemoryManager(stores=[store]))

await store.add("The user prefers dark mode", metadata={"kind": "pref"})
hits = await store.search("what theme does the user like?")
```

## How it works

- **Semantic recall** via Atlas `$vectorSearch` (approximate nearest-neighbor over a vector index), ranked by `vectorSearchScore`.
- **You bring the embeddings.** Default embedder is **Amazon Bedrock Titan Text v2** (1024-dim, cosine); pass any `embedder` callable.
- Each `add` stores a document `{_id, content, embedding, metadata, createdAt}`; the Atlas vector index is created automatically if absent (`create_index=True`).

## Requirements

**MongoDB Atlas** — Vector Search (`$vectorSearch`) is an Atlas feature; community/self-hosted MongoDB does not support it. For local development, use a managed store or the [Postgres](https://pypi.org/project/strands-postgres-store/) / [DynamoDB](https://pypi.org/project/strands-dynamodb-store/) memory stores.

> The memory **store** (`strands-mongodb-store`) is distinct from the byte **storage** backend ([`strands-mongodb-storage`](https://pypi.org/project/strands-mongodb-storage/)). Also published as `strands-store-mongodb`.

## License

MIT
