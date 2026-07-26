# strands-session-sql

SQL **session manager** (storage backend) for [Strands Agents](https://strandsagents.com), via **SQLAlchemy**. One provider for any SQLAlchemy-supported database — **SQLite, PostgreSQL, MySQL**, and more — selected purely by connection URL. The Python equivalent of "JDBC backends": one API, many databases.

Part of the [`strands-agents-session`](https://pypi.org/project/strands-agents-session/) family — it implements the base `SessionStorage` interface, so all the Strands session-repository logic comes from the core.

> **Storage only, by design.** Message *pruning* in Strands is a `ConversationManager` concern, decoupled from storage. This package does not prune.

## Installation

```bash
pip install strands-session-sql              # SQLite works out of the box (built-in)
pip install "strands-session-sql[postgres]"  # + psycopg (PostgreSQL)
pip install "strands-session-sql[mysql]"     # + pymysql (MySQL)
# or via the family extra:
pip install "strands-agents-session[sql]"
```

**Requires Python 3.10+.** SQLite needs no driver; other databases need their SQLAlchemy driver (the extras above).

## Quick start

```python
from strands import Agent
from strands_session_sql import SQLSessionManager

# SQLite (zero infra)
agent = Agent(session_manager=SQLSessionManager(
    session_id="user-123", url="sqlite:///sessions.db",
))

# PostgreSQL
mgr = SQLSessionManager(session_id="user-123",
                        url="postgresql+psycopg://user:pass@localhost:5432/mydb")

# MySQL
mgr = SQLSessionManager(session_id="user-123",
                        url="mysql+pymysql://user:pass@localhost:3306/mydb")
```

The table is created automatically if it does not exist.

## API

### `SQLSessionManager(session_id, *, url=None, table_name="strands_sessions", engine=None)`

| Parameter | Description |
|---|---|
| `session_id` | Session identifier |
| `url` | SQLAlchemy connection URL |
| `table_name` | Table name (default `strands_sessions`; created if absent) |
| `engine` | Optional pre-built SQLAlchemy `Engine` to reuse — supply this **or** `url` |

## Authentication

Auth is carried in the connection URL (user/password, host, TLS query args), or via a pre-built SQLAlchemy `Engine` for advanced setups (custom pools, SSL, IAM plugins):

```text
postgresql+psycopg://user:pass@host:5432/db?sslmode=require
mysql+pymysql://user:pass@host/db?ssl_ca=/path/ca.pem
sqlite:///sessions.db
```

## Data model

A single table with a composite primary key `(pk, sk)` and a `data` column:

```sql
CREATE TABLE strands_sessions (
    pk VARCHAR(255) NOT NULL,
    sk VARCHAR(255) NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (pk, sk)
);
```

`list_messages(offset, limit)` maps to `WHERE pk = ? AND sk >= ? ORDER BY sk LIMIT ?`. Message sort keys are zero-padded so lexical order matches numeric order.

## License

MIT
