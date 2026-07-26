# strands-session-mongodb

MongoDB **session manager** (storage backend) for [Strands Agents](https://strandsagents.com). Persists an agent's sessions, agent state, conversation-manager state, and messages to MongoDB so conversations resume across runs.

Part of the [`strands-agents-session`](https://pypi.org/project/strands-agents-session/) family — it implements the base `SessionStorage` interface, so all the Strands session-repository logic (message indexing, restore, `removed_message_count` offsetting, tool-use repair) comes from the core.

> **Storage only, by design.** Message *pruning* in Strands is a `ConversationManager` concern, decoupled from storage. This package does not prune.

## Installation

```bash
pip install strands-session-mongodb
# or, via the family's extra:
pip install "strands-agents-session[mongodb]"
```

**Requires Python 3.10+** and a reachable MongoDB (local, Atlas, or self-hosted).

## Quick start

```python
from strands import Agent
from strands_session_mongodb import MongoDBSessionManager

session_manager = MongoDBSessionManager(
    session_id="user-123",
    connection_string="mongodb://127.0.0.1:27017/",
)

agent = Agent(session_manager=session_manager)
agent("Hi, I'm Kamal")
agent("What's my name?")   # remembers within the session
```

Next run, same `session_id` → the agent restores its full history and state from MongoDB.

## API

### `MongoDBSessionManager(session_id, *, connection_string="mongodb://127.0.0.1:27017/", database_name="strands_sessions", collection_name="sessions", client=None, ttl_seconds=None)`

| Parameter | Description |
|---|---|
| `session_id` | Session identifier |
| `connection_string` | MongoDB URI (local, Atlas `mongodb+srv://…`, etc.) |
| `database_name` | Database (default `strands_sessions`) |
| `collection_name` | Collection (default `sessions`) |
| `client` | Optional pre-built `pymongo.MongoClient` to reuse |
| `ttl_seconds` | If set, adds a TTL index so documents expire automatically |

## Data model

A single collection; each document has a `pk` + `sk` (compound-indexed, unique) and a `data` field with the serialized payload:

| Item | pk | sk |
|---|---|---|
| Session | `SESSION#<session_id>` | `META` |
| Agent | `SESSION#<session_id>` | `AGENT#<agent_id>` |
| Message | `SESSION#<session_id>#AGENT#<agent_id>` | `MSG#<zero-padded id>` |

The `(pk, sk)` index gives ordered range scans, so `list_messages(offset, limit)` is a simple indexed `find(...).sort(sk).limit(...)` — matching the `removed_message_count` offset semantics Strands relies on.

## License

MIT
