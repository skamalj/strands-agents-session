# strands-mongodb-session-manager

**MongoDB** session manager for [Strands Agents](https://strandsagents.com) — durably persists sessions, agent state, and messages so conversations resume across runs.

```bash
pip install strands-mongodb-session-manager
```

```python
from strands import Agent
from strands_mongodb_session_manager import MongoDBSessionManager

session = MongoDBSessionManager(session_id="user-123", connection_string="mongodb://localhost:27017")
agent = Agent(session_manager=session)
```

> This is the catalog-named distribution of [`strands-session-mongodb`](https://pypi.org/project/strands-session-mongodb/); both install the same MongoDB session manager. Part of the [strands-agents-session](https://github.com/skamalj/strands-agents-session) family.

📖 **Docs:** https://skamalj.github.io/agentstate-reducer/strands/providers/mongodb/

## License

MIT
