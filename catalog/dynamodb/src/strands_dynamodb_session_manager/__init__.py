"""strands-dynamodb-session-manager.

Catalog-friendly distribution name for the Amazon DynamoDB session manager. The
implementation lives in ``strands_session_dynamodb`` (distribution
``strands-session-dynamodb``); this package re-exports its public API so both
names resolve to the same classes.
"""

from strands_session_dynamodb import DynamoDBSessionManager, DynamoDBSessionStorage

__all__ = ["DynamoDBSessionManager", "DynamoDBSessionStorage"]
