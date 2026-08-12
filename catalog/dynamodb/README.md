# strands-dynamodb-session-manager

Amazon **DynamoDB** session manager for [Strands Agents](https://strandsagents.com) — durably persists sessions, agent state, and messages so conversations resume across runs.

```bash
pip install strands-dynamodb-session-manager
```

```python
from strands import Agent
from strands_dynamodb_session_manager import DynamoDBSessionManager

session = DynamoDBSessionManager(session_id="user-123", table_name="strands_sessions")
agent = Agent(session_manager=session)
```

> This is the catalog-named distribution of [`strands-session-dynamodb`](https://pypi.org/project/strands-session-dynamodb/); both install the same DynamoDB session manager. Part of the [strands-agents-session](https://github.com/skamalj/strands-agents-session) family.

📖 **Docs:** https://skamalj.github.io/agentstate-reducer/strands/providers/dynamodb/

## License

MIT
