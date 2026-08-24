# strands-agents-session

A family of **state, storage, and memory backends** for [Strands Agents](https://strandsagents.com) — persist sessions across runs, store durable bytes for any SDK construct, and give agents long-term semantic memory. A **uv workspace monorepo**: one repository, multiple independently-published PyPI packages.

📖 **Full documentation:** **<https://skamalj.github.io/agentstate-reducer/strands/>**

The packages map onto three distinct Strands layers:

| Strands layer | What it is | Our packages |
|---|---|---|
| **Session** (`SessionRepository`) | persist an agent's sessions / agent state / messages across runs | `strands-agents-session` + `strands-session-*` |
| **Storage** (`strands.storage.Storage`) | durable bytes-under-keys (session snapshots, context offload, memory backing) | `strands-*-storage` / `strands-storage-*` |
| **Memory** (`MemoryStore`) | long-term semantic memory (`search`/`add`) | `strands-dynamodb-store` |

## Packages

### Session backends (`SessionRepository`)
| Package (PyPI) | Folder | Backend |
|---|---|---|
| [`strands-agents-session`](https://pypi.org/project/strands-agents-session/) | [`core/`](core) | backend-agnostic core (`SessionStorage` + `KeyValueSessionManager`) |
| [`strands-session-dynamodb`](https://pypi.org/project/strands-session-dynamodb/) ·  [`…-session-manager`](https://pypi.org/project/strands-dynamodb-session-manager/) | [`providers/dynamodb`](providers/dynamodb) | Amazon DynamoDB |
| [`strands-session-mongodb`](https://pypi.org/project/strands-session-mongodb/) ·  [`…-session-manager`](https://pypi.org/project/strands-mongodb-session-manager/) | [`providers/mongodb`](providers/mongodb) | MongoDB |
| [`strands-session-sql`](https://pypi.org/project/strands-session-sql/) ·  [`…-session-manager`](https://pypi.org/project/strands-sql-session-manager/) | [`providers/sql`](providers/sql) | SQL (SQLAlchemy) |

### Storage backends (`strands.storage.Storage`)
| Package (PyPI) | Folder | Backend |
|---|---|---|
| [`strands-sql-storage`](https://pypi.org/project/strands-sql-storage/) | [`storage/sql`](storage/sql) | any SQLAlchemy DB |
| [`strands-postgres-storage`](https://pypi.org/project/strands-postgres-storage/) · [`strands-storage-postgres`](https://pypi.org/project/strands-storage-postgres/) | [`storage/postgres`](storage/postgres) | PostgreSQL |
| [`strands-mongodb-storage`](https://pypi.org/project/strands-mongodb-storage/) · [`strands-storage-mongodb`](https://pypi.org/project/strands-storage-mongodb/) | [`storage/mongodb`](storage/mongodb) | MongoDB |
| [`strands-storage-dynamodb`](https://pypi.org/project/strands-storage-dynamodb/) | [`storage/dynamodb`](storage/dynamodb) | Amazon DynamoDB |

### Memory stores (`MemoryStore`) — semantic long-term memory
| Package (PyPI) | Folder | Vector engine |
|---|---|---|
| [`strands-dynamodb-store`](https://pypi.org/project/strands-dynamodb-store/) | [`memory/dynamodb`](memory/dynamodb) | DynamoDB **native `SearchVectors`** |
| [`strands-postgres-store`](https://pypi.org/project/strands-postgres-store/) · [`strands-store-postgres`](https://pypi.org/project/strands-store-postgres/) | [`memory/postgres`](memory/postgres) | PostgreSQL **pgvector** (`<=>` / HNSW) |
| [`strands-mongodb-store`](https://pypi.org/project/strands-mongodb-store/) · [`strands-store-mongodb`](https://pypi.org/project/strands-store-mongodb/) | [`memory/mongodb`](memory/mongodb) | MongoDB **Vector Search — Automated Embedding** (Voyage); Atlas or self-managed 8.2+ |

Each is a real Strands `MemoryStore` (`search`/`add`) that talks to its backend's native vector search directly — `Storage` has no search primitive, so a semantic store can't ride on it. DynamoDB & Postgres embed via a pluggable embedder (default Bedrock Titan v2); MongoDB uses Automated Embedding (Voyage) — no external embedder.

> **Naming note:** `strands-storage-dynamodb` is the byte **Storage** backend; `strands-dynamodb-store` is the semantic **MemoryStore**. `strands-dynamodb-store` 0.1.x was a storage alias — **from 0.2.0 it is a `MemoryStore`** (breaking); use `strands-storage-dynamodb` for byte storage.

📖 **Full documentation:** https://skamalj.github.io/agentstate-reducer/strands/

## Install

```bash
# Sessions
pip install "strands-agents-session[dynamodb]"   # core + DynamoDB session provider
pip install strands-session-mongodb              # or a provider directly

# Storage (bytes)
pip install strands-storage-dynamodb
pip install strands-postgres-storage

# Memory (semantic vector search)
pip install strands-dynamodb-store     # DynamoDB native SearchVectors
pip install strands-postgres-store     # PostgreSQL pgvector
pip install strands-mongodb-store      # MongoDB Vector Search (Automated Embedding)
```

## Design

- **Session** core implements Strands' full `SessionRepository` (8 CRUD methods) over a tiny `SessionStorage` interface + `RepositorySessionManager`; a provider implements ~5 storage methods. Storage-only by design — pruning is a `ConversationManager` concern.
- **Storage** backends implement the four-method `strands.storage.Storage` (`write`/`read`/`delete`/`list`) — durable bytes for session snapshots, context offloading, and memory backing.
- **Memory** stores are real `MemoryStore`s — each talks to its backend's native vector search directly (DynamoDB `SearchVectors`, Postgres `pgvector`, MongoDB Vector Search), like `BedrockKnowledgeBaseStore` talks to Bedrock, because `Storage` has no search primitive. DynamoDB/Postgres bring their own embeddings (default: Bedrock Titan v2, pluggable); MongoDB uses **Automated Embedding** (Voyage) — store and query plain text, no external embedder.

## Development (uv workspace)

```bash
uv sync
uv run pytest core/tests                  # offline
uv run pytest storage/postgres/tests      # needs local Postgres
uv run pytest memory/dynamodb/tests       # needs AWS + Bedrock (DynamoDB vector search)
```

Each package's tests run separately (per-package `asyncio_mode`). The workspace resolves siblings from local source during development; published packages depend on their PyPI releases.

## License

MIT
