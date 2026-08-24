"""MongoDB Vector Search ``MemoryStore`` (Automated Embedding) for Strands Agents.

``MongoDBMemoryStore`` is a Strands :class:`~strands.memory.types.MemoryStore`
that stores memory entries as plain-text documents and answers :meth:`search`
with MongoDB Vector Search using **Automated Embedding** — MongoDB generates the
embeddings itself (via Voyage AI) at index- and query-time, so you never compute,
store, or manage vectors, and there is no external embedder.

Works on **MongoDB Atlas** or **self-managed MongoDB Community 8.2+** running the
``mongot`` binary. Automated Embedding requires a Voyage AI API key configured on
the deployment (Atlas, or ``mongot`` for Community).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from strands.memory.types import MemoryEntry, MemoryStore, Metadata, SearchOptions

__all__ = ["MongoDBMemoryStore"]

DEFAULT_MODEL = "voyage-4-lite"
DEFAULT_MAX_SEARCH_RESULTS = 10
RELEVANCE_SCORE_KEY = "_score"


def _now() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z"


class MongoDBMemoryStore(MemoryStore):
    """A Strands ``MemoryStore`` backed by MongoDB Vector Search Automated Embedding.

    Documents store the raw ``content`` text; MongoDB auto-generates and manages
    the embeddings. ``search`` passes the query text — MongoDB embeds it too.

    Example:
        ```python
        from strands_mongodb_store import MongoDBMemoryStore

        store = MongoDBMemoryStore(
            name="user-memories",
            connection_string="mongodb://localhost:27017",   # or Atlas SRV URI
            database_name="agent", collection_name="memory",
        )
        await store.add("The user prefers dark mode", metadata={"kind": "pref"})
        hits = await store.search("what theme does the user like?")
        ```
    """

    def __init__(
        self,
        *,
        name: str,
        connection_string: str,
        database_name: str = "strands_memory",
        collection_name: str = "memory",
        client: Optional[MongoClient] = None,
        description: Optional[str] = None,
        max_search_results: Optional[int] = None,
        writable: bool = True,
        extraction: Any = None,
        model: str = DEFAULT_MODEL,
        index_name: str = "vector_index",
        num_candidates: Optional[int] = None,
        create_index: bool = True,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("MongoDBMemoryStore: name must not be empty.")
        self.name = name
        self.description = description
        self.max_search_results = max_search_results
        self.writable = writable
        self.extraction = extraction

        self._model = model
        self._index = index_name
        self._num_candidates = num_candidates
        self._client = client or MongoClient(connection_string)
        self._collection = self._client[database_name][collection_name]
        if create_index:
            self._ensure_index()

    def _ensure_index(self) -> None:
        """Create the Automated-Embedding vector search index if absent.

        Requires MongoDB Vector Search (Atlas, or self-managed Community 8.2+ with
        ``mongot``) plus a Voyage AI key configured on the deployment.
        """
        existing = {ix["name"] for ix in self._collection.list_search_indexes()}
        if self._index in existing:
            return
        model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "autoEmbed",
                        "modality": "text",
                        "path": "content",
                        "model": self._model,
                    }
                ]
            },
            name=self._index,
            type="vectorSearch",
        )
        self._collection.create_search_index(model)

    async def search(self, query: str, options: SearchOptions | None = None) -> list[MemoryEntry]:
        """Semantic search via MongoDB Vector Search — the query text is auto-embedded."""
        caller_max = options.get("max_search_results") if options else None
        if caller_max is not None and caller_max < 1:
            raise ValueError("MongoDBMemoryStore: max_search_results must be at least 1.")
        limit = caller_max or self.max_search_results or DEFAULT_MAX_SEARCH_RESULTS
        if not query or not query.strip():
            return []

        def _run() -> list[MemoryEntry]:
            vector_search: dict[str, Any] = {
                "index": self._index,
                "path": "content",
                "query": query,
                "limit": limit,
                "numCandidates": self._num_candidates or max(limit * 10, 100),
            }
            pipeline = [
                {"$vectorSearch": vector_search},
                {
                    "$project": {
                        "_id": 0,
                        "content": 1,
                        "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]
            entries: list[MemoryEntry] = []
            for doc in self._collection.aggregate(pipeline):
                metadata: Metadata = dict(doc.get("metadata") or {})
                metadata[RELEVANCE_SCORE_KEY] = doc.get("score")
                entries.append(MemoryEntry(content=doc["content"], metadata=metadata))
            return entries

        return await asyncio.to_thread(_run)

    async def add(self, content: str, metadata: Metadata | None = None) -> dict:
        """Store ``content`` as a plain-text document (MongoDB embeds it); returns ``{"id": ...}``."""
        if not self.writable:
            raise ValueError("MongoDBMemoryStore: store is not writable (set writable=True).")
        if not content or not content.strip():
            raise ValueError("MongoDBMemoryStore: content must not be empty.")

        def _run() -> dict:
            record_id = str(uuid.uuid4())
            self._collection.insert_one(
                {"_id": record_id, "content": content, "metadata": metadata, "createdAt": _now()}
            )
            return {"id": record_id}

        return await asyncio.to_thread(_run)
