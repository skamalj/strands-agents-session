"""strands-mongodb-session-manager.

Catalog-friendly distribution name for the MongoDB session manager. The
implementation lives in ``strands_session_mongodb`` (distribution
``strands-session-mongodb``); this package re-exports its public API so both
names resolve to the same classes.
"""

from strands_session_mongodb import MongoDBSessionManager, MongoDBSessionStorage

__all__ = ["MongoDBSessionManager", "MongoDBSessionStorage"]
