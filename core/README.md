# strands-agents-session

Backend-agnostic **session management** for [Strands Agents](https://strandsagents.com). Provides the shared machinery so you can build a session storage backend (DynamoDB, Redis, MongoDB, Postgres, …) by implementing just a handful of methods.

This is the base package of a family. Concrete backends are shipped separately, e.g. [`strands-session-dynamodb`](https://pypi.org/project/strands-session-dynamodb/).

## What it gives you

- **`KeyValueSessionManager`** — implements the full Strands `SessionRepository` (all 8 CRUD methods) and mixes in `RepositorySessionManager`, so the Strands session lifecycle (message indexing, restore, `removed_message_count` offsetting, tool-use repair, change detection) is reused unchanged.
- **`SessionStorage`** — a tiny ordered keyed-record interface (`put` / `get` / `query` / `delete` / `delete_partition`). Implement it and you have a working Strands session backend.
- **`InMemorySessionStorage`** — a ready in-memory backend for tests and local development.
- **`keys`** — shared key/serialization conventions (zero-padded message sort keys so `list_messages(offset, limit)` is a native ordered range scan).

> **Storage only, by design.** Message *pruning* in Strands is a `ConversationManager` concern, deliberately decoupled from storage. This package (and its backends) never prune — doing so at the storage layer would corrupt Strands' message-index/offset restore logic.

## Installation

```bash
pip install strands-agents-session
```

**Requires Python 3.10+.**

## Using the in-memory backend

```python
from strands import Agent
from strands_agents_session import KeyValueSessionManager, InMemorySessionStorage

session_manager = KeyValueSessionManager(
    session_id="user-123",
    storage=InMemorySessionStorage(),
)
agent = Agent(session_manager=session_manager)
```

## Batched writes (optional optimization)

Strands writes **one item per message** (user, assistant, tool-use, tool-result), so a tool-heavy turn is several writes. For high-throughput workloads you can opt into **batched writes** — buffer messages and flush them in one batched storage call:

```python
DynamoDBSessionManager(
    session_id="user-123",
    table_name="sessions",
    write_mode="batched",       # default is "immediate"
    max_batch_size=25,          # flush once this many messages are buffered
    max_batch_interval=5.0,     # ...or after this many seconds (lazy: checked on write)
    flush_on_turn_end=True,     # ...or at each turn boundary (recommended backstop)
    on_flush=my_callback,       # optional: called with the flushed batch
)
```

**Durability trade-off (stated plainly):** on a crash you lose at most `max_batch_size` messages, or `max_batch_interval` seconds of un-flushed writes — whichever is smaller — plus anything since the last turn boundary when `flush_on_turn_end` is set. `write_mode="immediate"` (the default) has no such window.

The time trigger is **lazy** — evaluated on each new message, so it never spawns a background thread and won't flush while the session is idle; `flush_on_turn_end` (and an explicit `flush()`) are the durability backstops.

Each backend implements a native bulk write (DynamoDB `BatchWriteItem`, Mongo `bulk_write`, SQL one-transaction `executemany`); the buffering/flush logic lives in the core, so every backend gets it. The `on_flush` callback is a clean seam for driving downstream consumers (e.g. memory extraction) off a coherent, just-persisted batch.

## Building a backend

Implement `SessionStorage` and hand it to `KeyValueSessionManager`:

```python
from strands_agents_session import KeyValueSessionManager, SessionStorage

class MyStorage(SessionStorage):
    def put(self, item): ...                 # item = {"pk", "sk", "data"}
    def get(self, pk, sk): ...               # -> item | None
    def query(self, pk, sk_gte=None, limit=None): ...  # ordered by sk asc
    def delete(self, pk, sk): ...
    def delete_partition(self, pk): ...
    # optional: override for a native bulk write (defaults to looping put)
    def put_batch(self, items): ...

class MySessionManager(KeyValueSessionManager):
    def __init__(self, session_id, **cfg):
        super().__init__(session_id=session_id, storage=MyStorage(**cfg))
```

That's it — all the `SessionRepository` methods, restore logic, and pagination come from the base.

## License

MIT
