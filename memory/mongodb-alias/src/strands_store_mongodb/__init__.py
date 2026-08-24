"""strands-store-mongodb.

Alternate (search-friendly) distribution name for the MongoDB Atlas Vector Search
``MemoryStore``. The implementation lives in ``strands_mongodb_store``
(distribution ``strands-mongodb-store``); this package re-exports its public API.
"""

from strands_mongodb_store import MongoDBMemoryStore, bedrock_titan_embedder

__all__ = ["MongoDBMemoryStore", "bedrock_titan_embedder"]
