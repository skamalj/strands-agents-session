# strands-dynamodb-store

A **DynamoDB-native-vector `MemoryStore`** for [Strands Agents](https://strandsagents.com) — semantic long-term agent memory backed by [DynamoDB's native vector search](https://aws.amazon.com/blogs/aws/amazon-dynamodb-now-supports-real-time-vector-search-at-any-scale/) (`SearchVectors`). No external vector database, no separate `Storage` layer — the store talks to DynamoDB directly, the way `BedrockKnowledgeBaseStore` talks to Bedrock.

```bash
pip install strands-dynamodb-store
```

```python
from strands import Agent
from strands.memory import MemoryManager
from strands_dynamodb_store import DynamoDBMemoryStore

store = DynamoDBMemoryStore(name="user-memories", table_name="agent_memory")
agent = Agent(memory_manager=MemoryManager(stores=[store]))

# or use it directly
await store.add("The user prefers dark mode", metadata={"kind": "pref"})
hits = await store.search("what theme does the user like?")
```

## How it works

- **Semantic recall** via DynamoDB `search_vectors` (approximate nearest-neighbor over a vector index) — ranked by similarity, at DynamoDB scale.
- **You bring the embeddings.** DynamoDB does not generate them; by default the store embeds with **Amazon Bedrock Titan Text v2** (`amazon.titan-embed-text-v2:0`, 1024-dim, cosine). Pass any `embedder` callable to use Cohere, OpenAI, a local model, etc.
- Each `add` stores an item `{id, content, embedding (List<Number>), metadata, createdAt}`; `search` embeds the query and runs the ANN search.
- The table is created automatically if absent — `PAY_PER_REQUEST` with a vector index on the `embedding` attribute.

## Configuration

`DynamoDBMemoryStore(name, table_name, *, description=None, max_search_results=None, writable=True, extraction=None, embedder=None, dimensions=1024, distance_function="COSINE", index_name="vector_index", vector_attribute="embedding", region_name=None, boto_session=None, endpoint_url=None)`

Implements the Strands `MemoryStore` protocol: `search(query, options)` and `add(content, metadata)`.

Each result's metadata carries `_score`, a **similarity** (higher is better; for `COSINE` it is `1 - distance`), and `_distance`, DynamoDB's raw value (lower is better). *0.2.0 reported the raw distance as `_score`; fixed in 0.2.1.*

## Requirements

- `boto3>=1.43.78` (DynamoDB vector search, GA 2026-08-05)
- A region where DynamoDB vector search is available, plus Bedrock model access for the default embedder.

> This package (the memory **store**) is distinct from [`strands-storage-dynamodb`](https://pypi.org/project/strands-storage-dynamodb/) (the byte **storage** backend). Earlier `strands-dynamodb-store` releases (0.1.x) were an alias of that storage package; from 0.2.0 it is a `MemoryStore`.

## License

MIT
