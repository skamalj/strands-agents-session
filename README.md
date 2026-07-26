# strands-agents-session

A family of **session backends** for [Strands Agents](https://strandsagents.com) — persist an agent's sessions, agent state, and messages across runs. A backend-agnostic core plus pluggable storage providers.

This is a **uv workspace monorepo**: one repository, multiple independently-published PyPI packages.

## Packages

| Package (PyPI) | Folder | What it is |
|---|---|---|
| [`strands-agents-session`](https://pypi.org/project/strands-agents-session/) | [`core/`](core) | Backend-agnostic core — `SessionStorage` interface + `KeyValueSessionManager` (+ in-memory backend) |
| [`strands-session-dynamodb`](https://pypi.org/project/strands-session-dynamodb/) | [`providers/dynamodb/`](providers/dynamodb) | Amazon DynamoDB storage backend |
| [`strands-session-mongodb`](https://pypi.org/project/strands-session-mongodb/) | [`providers/mongodb/`](providers/mongodb) | MongoDB storage backend |
| [`strands-session-sql`](https://pypi.org/project/strands-session-sql/) | [`providers/sql/`](providers/sql) | SQL via SQLAlchemy (SQLite, PostgreSQL, MySQL) |

More providers (Redis, …) land as new folders under `providers/`.

📖 **Full documentation:** https://skamalj.github.io/strands-agents-session/

## Install

Pick a provider directly, or use the core package's extras:

```bash
pip install "strands-agents-session[dynamodb]"   # core + DynamoDB provider
pip install "strands-agents-session[mongodb]"     # core + MongoDB provider
pip install "strands-agents-session[sql]"         # core + SQL provider (SQLAlchemy)
# equivalently, install a provider directly:
pip install strands-session-dynamodb
pip install strands-session-mongodb
pip install strands-session-sql
```

Each provider is an independent distribution that pulls the core transitively — a DynamoDB user never pulls another provider's code.

## Design

- The **core** implements Strands' full `SessionRepository` (all 8 CRUD methods) over a tiny `SessionStorage` interface, and mixes in `RepositorySessionManager`, so the Strands session lifecycle (message indexing, restore, `removed_message_count` offsetting, tool-use repair) is reused unchanged.
- A **provider** implements ~5 storage methods (`put`/`get`/`query`/`delete`/`delete_partition`). That's the entire surface to add a new backend.
- **Storage only, by design.** Message *pruning* in Strands is a `ConversationManager` concern, deliberately decoupled from storage. These packages never prune — doing so at the storage layer would corrupt Strands' message-index/offset restore logic.

## Development (uv workspace)

```bash
uv sync                    # installs all workspace members + dev deps
uv run pytest core/tests   # offline core tests (in-memory backend)
uv run pytest providers/dynamodb/tests   # provider tests (needs AWS creds; LLM tests need OPENAI_API_KEY)
```

The workspace resolves the core from local source during development (`[tool.uv.sources]`), while published providers depend on `strands-agents-session` from PyPI.

## License

MIT
