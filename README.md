# strands-agents-session

A family of **state, storage, and memory backends** for [Strands Agents](https://strandsagents.com) — persist sessions across runs, store durable bytes for any SDK construct, and give agents long-term semantic memory. A **uv workspace monorepo**: one repository, multiple independently-published PyPI packages.

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

### Memory store (`MemoryStore`)
| Package (PyPI) | Folder | Backend |
|---|---|---|
| [`strands-dynamodb-store`](https://pypi.org/project/strands-dynamodb-store/) | [`memory/dynamodb`](memory/dynamodb) | DynamoDB **native vector search** (`SearchVectors`), Bedrock Titan embeddings |

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

# Memory (semantic, DynamoDB native vectors)
pip install strands-dynamodb-store
```

## Design

- **Session** core implements Strands' full `SessionRepository` (8 CRUD methods) over a tiny `SessionStorage` interface + `RepositorySessionManager`; a provider implements ~5 storage methods. Storage-only by design — pruning is a `ConversationManager` concern.
- **Storage** backends implement the four-method `strands.storage.Storage` (`write`/`read`/`delete`/`list`) — durable bytes for session snapshots, context offloading, and memory backing.
- **Memory** (`strands-dynamodb-store`) is a real `MemoryStore` — it talks to DynamoDB's native vector search directly (like `BedrockKnowledgeBaseStore` talks to Bedrock), because `Storage` has no search primitive. You bring the embeddings (default: Bedrock Titan v2, pluggable).

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
