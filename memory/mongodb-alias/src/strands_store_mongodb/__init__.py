"""strands-store-mongodb.

Alternate (search-friendly) distribution name for the MongoDB Vector Search
``MemoryStore`` (Automated Embedding). The implementation lives in
``strands_mongodb_store`` (distribution ``strands-mongodb-store``); this package
re-exports its public API.
"""

from strands_mongodb_store import MongoDBMemoryStore

__all__ = ["MongoDBMemoryStore"]
