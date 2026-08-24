"""MongoDB Atlas Vector Search ``MemoryStore`` for Strands Agents.

``MongoDBMemoryStore`` is a Strands :class:`~strands.memory.types.MemoryStore`
that stores memory entries — content plus an embedding vector — as MongoDB
documents and answers :meth:`search` with **Atlas Vector Search** (the
``$vectorSearch`` aggregation stage over an Atlas vector index).

Requires **MongoDB Atlas** (Vector Search is an Atlas feature; community/self-hosted
MongoDB does not support ``$vectorSearch``). You bring the embeddings — by default
Amazon Bedrock Titan Text v2; pass any ``embedder`` callable to change models.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from strands.memory.types import MemoryEntry, MemoryStore, Metadata, SearchOptions

__all__ = ["MongoDBMemoryStore", "bedrock_titan_embedder", "Embedder"]

Embedder = Callable[[str], List[float]]
DEFAULT_EMBED_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_DIMENSIONS = 1024
DEFAULT_MAX_SEARCH_RESULTS = 10
RELEVANCE_SCORE_KEY = "_score"


def _now() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z"


def bedrock_titan_embedder(
    *,
    model_id: str = DEFAULT_EMBED_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
    normalize: bool = True,
    region_name: Optional[str] = None,
    client: Any = None,
) -> Embedder:
    """An :data:`Embedder` backed by Amazon Bedrock Titan Text embeddings."""
    import boto3

    runtime = client or boto3.client("bedrock-runtime", region_name=region_name)

    def embed(t: str) -> List[float]:
        body = json.dumps({"inputText": t, "dimensions": dimensions, "normalize": normalize})
        resp = runtime.invoke_model(modelId=model_id, body=body)
        return json.loads(resp["body"].read())["embedding"]

    return embed


class MongoDBMemoryStore(MemoryStore):
    """A Strands ``MemoryStore`` backed by MongoDB Atlas Vector Search.

    Example:
        ```python
        from strands_mongodb_store import MongoDBMemoryStore

        store = MongoDBMemoryStore(
            name="user-memories",
            connection_string="mongodb+srv://user:pass@cluster.mongodb.net",
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
        embedder: Optional[Embedder] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        similarity: str = "cosine",
        index_name: str = "vector_index",
        create_index: bool = True,
        region_name: Optional[str] = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("MongoDBMemoryStore: name must not be empty.")
        self.name = name
        self.description = description
        self.max_search_results = max_search_results
        self.writable = writable
        self.extraction = extraction

        self._embedder = embedder or bedrock_titan_embedder(
            dimensions=dimensions, region_name=region_name
        )
        self._dimensions = dimensions
        self._similarity = similarity
        self._index = index_name
        self._client = client or MongoClient(connection_string)
        self._collection = self._client[database_name][collection_name]
        if create_index:
            self._ensure_index()

    def _ensure_index(self) -> None:
        """Create the Atlas vector search index if absent (best effort).

        Atlas-only: on community MongoDB this raises, which is expected — the store
        requires Atlas Vector Search.
        """
        existing = {ix["name"] for ix in self._collection.list_search_indexes()}
        if self._index in existing:
            return
        model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": self._dimensions,
                        "similarity": self._similarity,
                    }
                ]
            },
            name=self._index,
            type="vectorSearch",
        )
        self._collection.create_search_index(model)

    async def search(self, query: str, options: SearchOptions | None = None) -> list[MemoryEntry]:
        """Semantic search via Atlas ``$vectorSearch``, ranked by similarity score."""
        caller_max = options.get("max_search_results") if options else None
        if caller_max is not None and caller_max < 1:
            raise ValueError("MongoDBMemoryStore: max_search_results must be at least 1.")
        limit = caller_max or self.max_search_results or DEFAULT_MAX_SEARCH_RESULTS
        if not query or not query.strip():
            return []

        def _run() -> list[MemoryEntry]:
            vector = self._embedder(query)
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self._index,
                        "path": "embedding",
                        "queryVector": vector,
                        "numCandidates": max(limit * 10, 100),
                        "limit": limit,
                    }
                },
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
        """Embed ``content`` and store it as a document; returns ``{"id": ...}``."""
        if not self.writable:
            raise ValueError("MongoDBMemoryStore: store is not writable (set writable=True).")
        if not content or not content.strip():
            raise ValueError("MongoDBMemoryStore: content must not be empty.")

        def _run() -> dict:
            vector = self._embedder(content)
            record_id = str(uuid.uuid4())
            self._collection.insert_one(
                {
                    "_id": record_id,
                    "content": content,
                    "embedding": vector,
                    "metadata": metadata,
                    "createdAt": _now(),
                }
            )
            return {"id": record_id}

        return await asyncio.to_thread(_run)
