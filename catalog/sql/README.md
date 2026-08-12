# strands-sql-session-manager

**SQL** (SQLAlchemy) session manager for [Strands Agents](https://strandsagents.com) — durably persists sessions, agent state, and messages so conversations resume across runs. Works with any SQLAlchemy-supported database (PostgreSQL, MySQL, SQLite, …).

```bash
pip install strands-sql-session-manager
```

```python
from strands import Agent
from strands_sql_session_manager import SQLSessionManager

session = SQLSessionManager(session_id="user-123", url="postgresql://user:pass@localhost/db")
agent = Agent(session_manager=session)
```

> This is the catalog-named distribution of [`strands-session-sql`](https://pypi.org/project/strands-session-sql/); both install the same SQL session manager. Part of the [strands-agents-session](https://github.com/skamalj/strands-agents-session) family.

📖 **Docs:** https://skamalj.github.io/agentstate-reducer/strands/providers/sql/

## License

MIT
