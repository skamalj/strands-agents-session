"""PostgreSQL + pgvector ``MemoryStore`` for Strands Agents.

``PostgresMemoryStore`` is a Strands :class:`~strands.memory.types.MemoryStore`
that stores memory entries — content plus an embedding vector — in a PostgreSQL
table and answers :meth:`search` with **pgvector** native ANN (the ``<=>`` cosine
distance operator over an HNSW index). No external vector database.

DynamoDB does not generate embeddings and neither does Postgres — you bring them.
By default this store embeds with Amazon Bedrock Titan Text v2; pass any
``embedder`` callable to use a different model.

Requires the ``pgvector`` extension on the server (``CREATE EXTENSION vector``).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Index,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from strands.memory.types import MemoryEntry, MemoryStore, Metadata, SearchOptions

__all__ = ["PostgresMemoryStore", "bedrock_titan_embedder", "Embedder"]

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


class PostgresMemoryStore(MemoryStore):
    """A Strands ``MemoryStore`` backed by PostgreSQL + pgvector.

    Example:
        ```python
        from strands_postgres_store import PostgresMemoryStore

        store = PostgresMemoryStore(
            name="user-memories",
            url="postgresql://user:pass@localhost:5432/db",
        )
        await store.add("The user prefers dark mode", metadata={"kind": "pref"})
        hits = await store.search("what theme does the user like?")
        ```
    """

    def __init__(
        self,
        *,
        name: str,
        url: Optional[str] = None,
        table_name: str = "strands_memory",
        engine: Optional[Engine] = None,
        description: Optional[str] = None,
        max_search_results: Optional[int] = None,
        writable: bool = True,
        extraction: Any = None,
        embedder: Optional[Embedder] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        region_name: Optional[str] = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("PostgresMemoryStore: name must not be empty.")
        if engine is None and url is None:
            raise ValueError("Provide either 'url' or 'engine'")
        self.name = name
        self.description = description
        self.max_search_results = max_search_results
        self.writable = writable
        self.extraction = extraction

        self._embedder = embedder or bedrock_titan_embedder(
            dimensions=dimensions, region_name=region_name
        )
        self._dimensions = dimensions
        self._engine = engine or create_engine(url)  # type: ignore[arg-type]
        self._metadata = MetaData()
        self._table = Table(
            table_name,
            self._metadata,
            Column("id", String, primary_key=True),
            Column("content", Text, nullable=False),
            Column("embedding", Vector(dimensions), nullable=False),
            Column("metadata", JSONB),
            Column("created_at", String, nullable=False),
        )
        self._index = Index(
            f"{table_name}_embedding_hnsw",
            self._table.c.embedding,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        self._metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            self._index.create(conn, checkfirst=True)

    async def search(self, query: str, options: SearchOptions | None = None) -> list[MemoryEntry]:
        """Semantic search via pgvector cosine distance (``<=>``), ranked closest-first."""
        caller_max = options.get("max_search_results") if options else None
        if caller_max is not None and caller_max < 1:
            raise ValueError("PostgresMemoryStore: max_search_results must be at least 1.")
        limit = caller_max or self.max_search_results or DEFAULT_MAX_SEARCH_RESULTS
        if not query or not query.strip():
            return []

        t = self._table

        def _run() -> list[MemoryEntry]:
            vector = self._embedder(query)
            distance = t.c.embedding.cosine_distance(vector)
            with self._engine.connect() as conn:
                rows = conn.execute(
                    select(t.c.content, t.c.metadata, distance.label("_distance"))
                    .order_by(distance)
                    .limit(limit)
                ).all()
            entries: list[MemoryEntry] = []
            for content, meta, dist in rows:
                metadata: Metadata = dict(meta or {})
                metadata[RELEVANCE_SCORE_KEY] = float(dist)
                entries.append(MemoryEntry(content=content, metadata=metadata))
            return entries

        return await asyncio.to_thread(_run)

    async def add(self, content: str, metadata: Metadata | None = None) -> dict:
        """Embed ``content`` and store it as a row; returns ``{"id": ...}``."""
        if not self.writable:
            raise ValueError("PostgresMemoryStore: store is not writable (set writable=True).")
        if not content or not content.strip():
            raise ValueError("PostgresMemoryStore: content must not be empty.")

        t = self._table

        def _run() -> dict:
            vector = self._embedder(content)
            record_id = str(uuid.uuid4())
            with self._engine.begin() as conn:
                conn.execute(
                    insert(t).values(
                        id=record_id, content=content, embedding=vector,
                        metadata=metadata, created_at=_now(),
                    )
                )
            return {"id": record_id}

        return await asyncio.to_thread(_run)
