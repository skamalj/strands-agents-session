"""Tests for MongoDBMemoryStore (Automated Embedding) against a real vector-search MongoDB.

Requires MongoDB Vector Search with Automated Embedding — either Atlas or
self-managed Community 8.2+ with the ``mongot`` binary and a Voyage AI key
configured. Set MONGODB_VECTOR_URI to enable; otherwise the tests skip.
"""
import os
import time
import uuid

import pytest

from strands_mongodb_store import MongoDBMemoryStore

URI = os.environ.get("MONGODB_VECTOR_URI")

pytestmark = pytest.mark.skipif(
    not URI, reason="MONGODB_VECTOR_URI not set (MongoDB Vector Search + Automated Embedding required)"
)


@pytest.fixture()
def store():
    coll = f"mem_test_{uuid.uuid4().hex[:8]}"
    s = MongoDBMemoryStore(
        name="test", connection_string=URI,
        database_name="strands_memory_test", collection_name=coll,
    )
    # Wait for the vector index to be queryable (index build is asynchronous).
    deadline = time.time() + 180
    while time.time() < deadline:
        idx = list(s._collection.list_search_indexes())
        if idx and all(i.get("queryable") for i in idx):
            break
        time.sleep(5)
    yield s
    s._collection.drop()


async def test_add_returns_id(store):
    r = await store.add("A fact about food and sushi")
    assert isinstance(r.get("id"), str) and r["id"]


async def test_empty_query_returns_empty(store):
    assert await store.search("  ") == []


async def test_not_writable_rejects_add(store):
    ro = MongoDBMemoryStore(
        name="ro", connection_string=URI,
        database_name="strands_memory_test", collection_name=store._collection.name,
        create_index=False, writable=False,
    )
    with pytest.raises(ValueError):
        await ro.add("nope")


async def test_semantic_search_ranks_relevant_first(store):
    await store.add("The user loves sushi and Japanese food", metadata={"kind": "food"})
    await store.add("The user's favorite is the Python programming language", metadata={"kind": "tech"})
    await store.add("The user lives in a big city by the sea", metadata={"kind": "place"})

    # Automated embeddings ingest asynchronously — retry until results appear.
    hits = []
    for _ in range(12):
        hits = await store.search("what does the user like to eat?", options={"max_search_results": 3})
        if hits:
            break
        time.sleep(5)

    assert hits, "expected results once embeddings are ingested"
    assert "sushi" in hits[0].content.lower()
    assert hits[0].metadata.get("_score") is not None
    assert hits[0].metadata.get("kind") == "food"
