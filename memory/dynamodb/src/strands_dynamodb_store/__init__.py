"""DynamoDB-native-vector ``MemoryStore`` for Strands Agents.

``DynamoDBMemoryStore`` is a Strands :class:`~strands.memory.types.MemoryStore`
that stores memory entries — content plus an embedding vector — as DynamoDB items
and answers :meth:`search` with DynamoDB's **native vector search**
(``search_vectors`` ANN over a vector index). No external vector database and no
byte ``Storage`` layer: it talks to DynamoDB directly, the way
``BedrockKnowledgeBaseStore`` talks to Bedrock.

DynamoDB does not generate embeddings — you bring them. By default this store
embeds with Amazon Bedrock Titan Text v2; pass any ``embedder`` callable to use a
different model (Cohere, OpenAI, local, …).

Requires ``boto3>=1.43.78`` (DynamoDB vector search, GA 2026-08-05) and a table in
``PAY_PER_REQUEST`` mode with a vector index (created automatically if absent).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

import boto3

from strands.memory.types import MemoryEntry, MemoryStore, Metadata, SearchOptions

__all__ = ["DynamoDBMemoryStore", "bedrock_titan_embedder", "Embedder"]

# A function that turns text into an embedding vector.
Embedder = Callable[[str], List[float]]

DEFAULT_EMBED_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_DIMENSIONS = 1024
DEFAULT_DISTANCE_FUNCTION = "COSINE"
DEFAULT_MAX_SEARCH_RESULTS = 10

# Synthetic metadata keys on a search result: ``_score`` is a similarity (higher is
# better; for COSINE it is ``1 - distance``), ``_distance`` is DynamoDB's raw value.
RELEVANCE_SCORE_KEY = "_score"
DISTANCE_KEY = "_distance"


def _now() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z"


def _new_id() -> str:
    return str(uuid.uuid4())


def bedrock_titan_embedder(
    *,
    model_id: str = DEFAULT_EMBED_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
    normalize: bool = True,
    region_name: Optional[str] = None,
    client: Any = None,
) -> Embedder:
    """Build an :data:`Embedder` backed by Amazon Bedrock Titan Text embeddings.

    Titan v2 supports 256/512/1024 dimensions; ``dimensions`` must match the
    ``Dimensions`` the store's vector index is created with.
    """
    runtime = client or boto3.client("bedrock-runtime", region_name=region_name)

    def embed(text: str) -> List[float]:
        body = json.dumps({"inputText": text, "dimensions": dimensions, "normalize": normalize})
        resp = runtime.invoke_model(modelId=model_id, body=body)
        return json.loads(resp["body"].read())["embedding"]

    return embed


class DynamoDBMemoryStore(MemoryStore):
    """A Strands ``MemoryStore`` backed by DynamoDB native vector search.

    Example:
        ```python
        from strands import Agent
        from strands.memory import MemoryManager
        from strands_dynamodb_store import DynamoDBMemoryStore

        store = DynamoDBMemoryStore(name="user-memories", table_name="agent_memory")
        agent = Agent(memory_manager=MemoryManager(stores=[store]))
        ```

    Attributes mirror :class:`~strands.memory.types.MemoryStoreConfig`
    (``name``/``description``/``max_search_results``/``writable``/``extraction``).
    """

    def __init__(
        self,
        *,
        name: str,
        table_name: str,
        description: Optional[str] = None,
        max_search_results: Optional[int] = None,
        writable: bool = True,
        extraction: Any = None,
        embedder: Optional[Embedder] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        distance_function: str = DEFAULT_DISTANCE_FUNCTION,
        index_name: str = "vector_index",
        vector_attribute: str = "embedding",
        region_name: Optional[str] = None,
        boto_session: Optional["boto3.Session"] = None,
        endpoint_url: Optional[str] = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("DynamoDBMemoryStore: name must not be empty.")
        self.name = name
        self.description = description
        self.max_search_results = max_search_results
        self.writable = writable
        self.extraction = extraction

        self._embedder = embedder or bedrock_titan_embedder(
            dimensions=dimensions, region_name=region_name
        )
        self._dimensions = dimensions
        self._distance = distance_function
        self._index = index_name
        self._vattr = vector_attribute
        self._table = table_name

        session = boto_session or boto3.Session(region_name=region_name)
        self._ddb = session.client("dynamodb", endpoint_url=endpoint_url)
        self._ensure_table()

    # ------------------------------------------------------------------ setup
    def _ensure_table(self) -> None:
        try:
            self._ddb.describe_table(TableName=self._table)
            return
        except self._ddb.exceptions.ResourceNotFoundException:
            self._ddb.create_table(
                TableName=self._table,
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                BillingMode="PAY_PER_REQUEST",
                VectorIndexes=[
                    {
                        "IndexName": self._index,
                        "VectorAttribute": {"AttributeName": self._vattr},
                        "Dimensions": self._dimensions,
                        "DistanceFunction": self._distance,
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
            )
            self._ddb.get_waiter("table_exists").wait(TableName=self._table)

    def _vector_av(self, vec: List[float]) -> dict:
        """A DynamoDB List-of-Number attribute value for a stored item."""
        return {"L": [{"N": repr(float(v))} for v in vec]}

    def _query_vector(self, vec: List[float]) -> list:
        """The bare AttributeValue list ``SearchVectors`` expects for the query."""
        return [{"N": repr(float(v))} for v in vec]

    # ------------------------------------------------------------------ MemoryStore
    async def search(self, query: str, options: SearchOptions | None = None) -> list[MemoryEntry]:
        """Semantic search via DynamoDB native vector ANN, ranked by similarity."""
        caller_max = options.get("max_search_results") if options else None
        if caller_max is not None and caller_max < 1:
            raise ValueError("DynamoDBMemoryStore: max_search_results must be at least 1.")
        limit = caller_max or self.max_search_results or DEFAULT_MAX_SEARCH_RESULTS

        if not query or not query.strip():
            return []

        def _run() -> list[MemoryEntry]:
            vector = self._embedder(query)
            resp = self._ddb.search_vectors(
                TableName=self._table,
                IndexName=self._index,
                SearchVector=self._query_vector(vector),
                TopK=limit,
            )
            entries: list[MemoryEntry] = []
            for result in resp.get("SearchResults", []):
                item = result["Item"]
                content = item["content"]["S"]
                metadata: Metadata = {}
                if "metadata" in item:
                    metadata = json.loads(item["metadata"]["S"])
                # DynamoDB returns a *distance* (0 = identical). Surface a similarity
                # (higher is better) as ``_score`` and keep the raw value as ``_distance``.
                raw = result.get("Score")
                if raw is not None:
                    metadata[DISTANCE_KEY] = float(raw)
                    metadata[RELEVANCE_SCORE_KEY] = (
                        1.0 - float(raw) if self._distance == "COSINE" else -float(raw)
                    )
                entries.append(MemoryEntry(content=content, metadata=metadata))
            return entries

        return await asyncio.to_thread(_run)

    async def add(self, content: str, metadata: Metadata | None = None) -> dict:
        """Embed ``content`` and store it as a DynamoDB item; returns ``{"id": ...}``."""
        if not self.writable:
            raise ValueError("DynamoDBMemoryStore: store is not writable (set writable=True).")
        if not content or not content.strip():
            raise ValueError("DynamoDBMemoryStore: content must not be empty.")

        def _run() -> dict:
            vector = self._embedder(content)
            record_id = _new_id()
            item = {
                "id": {"S": record_id},
                "content": {"S": content},
                self._vattr: self._vector_av(vector),
                "createdAt": {"S": _now()},
            }
            if metadata is not None:
                item["metadata"] = {"S": json.dumps(metadata)}
            self._ddb.put_item(TableName=self._table, Item=item)
            return {"id": record_id}

        return await asyncio.to_thread(_run)
