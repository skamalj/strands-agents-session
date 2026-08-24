"""Tests for MongoDBMemoryStore against a real MongoDB Atlas cluster.

Requires MONGODB_ATLAS_URI (an Atlas connection string with Vector Search). Uses a
small deterministic embedder (no AWS). Skips when no Atlas URI is provided —
community/local MongoDB does not support $vectorSearch.
"""
import os
import time
import uuid

import pytest

from strands_mongodb_store import MongoDBMemoryStore

ATLAS_URI = os.environ.get("MONGODB_ATLAS_URI")

_BASIS = {"food": [1, 0, 0, 0], "tech": [0, 1, 0, 0], "place": [0, 0, 1, 0]}


def _fake_embed(textval: str) -> list[float]:
    t = textval.lower()
    if "sushi" in t or "food" in t or "eat" in t:
        return _BASIS["food"]
    if "python" in t or "program" in t or "code" in t:
        return _BASIS["tech"]
    if "city" in t or "live" in t or "place" in t:
        return _BASIS["place"]
    return [0, 0, 0, 1]


pytestmark = pytest.mark.skipif(
    not ATLAS_URI, reason="MONGODB_ATLAS_URI not set (Atlas Vector Search required)"
)


@pytest.fixture()
def store():
    coll = f"mem_test_{uuid.uuid4().hex[:8]}"
    s = MongoDBMemoryStore(
        name="test", connection_string=ATLAS_URI,
        database_name="strands_memory_test", collection_name=coll,
        embedder=_fake_embed, dimensions=4,
    )
    # Atlas builds the vector index asynchronously — wait until it's queryable.
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


async def test_semantic_search_ranks_relevant_first(store):
    await store.add("The user loves sushi and Japanese food", metadata={"kind": "food"})
    await store.add("The user's favorite is the Python programming language", metadata={"kind": "tech"})
    await store.add("The user lives in a big city", metadata={"kind": "place"})
    time.sleep(5)  # allow the index to ingest the new docs

    hits = await store.search("what does the user like to eat?", options={"max_search_results": 3})
    assert hits
    assert "sushi" in hits[0].content.lower()
    assert hits[0].metadata.get("_score") is not None
    assert hits[0].metadata.get("kind") == "food"


async def test_empty_query_returns_empty(store):
    assert await store.search("  ") == []
