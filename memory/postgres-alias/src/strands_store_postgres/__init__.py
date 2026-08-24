"""strands-store-postgres.

Alternate (search-friendly) distribution name for the PostgreSQL + pgvector
``MemoryStore``. The implementation lives in ``strands_postgres_store``
(distribution ``strands-postgres-store``); this package re-exports its public API.
"""

from strands_postgres_store import PostgresMemoryStore, bedrock_titan_embedder

__all__ = ["PostgresMemoryStore", "bedrock_titan_embedder"]
