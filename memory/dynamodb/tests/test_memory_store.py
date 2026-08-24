"""E2E tests for DynamoDBMemoryStore against real DynamoDB vector search + Bedrock.

Requires AWS credentials, DynamoDB vector search availability, and Bedrock model
access for the default Titan embedder. One table is created for the module
(vector-index creation is slow) and deleted at the end.
"""
import time
import uuid

import boto3
import pytest

from strands_dynamodb_store import DynamoDBMemoryStore

REGION = "us-east-1"


def _aws_available() -> bool:
    try:
        boto3.client("sts", region_name=REGION).get_caller_identity()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _aws_available(), reason="AWS credentials not available")


@pytest.fixture(scope="module")
def store():
    table = f"strands_mem_test_{uuid.uuid4().hex[:8]}"
    ddb = boto3.client("dynamodb", region_name=REGION)
    s = DynamoDBMemoryStore(name="test", table_name=table, region_name=REGION)

    # Wait for the vector index to become ACTIVE before searching.
    deadline = time.time() + 300
    while time.time() < deadline:
        d = ddb.describe_table(TableName=table)["Table"]
        vis = d.get("VectorIndexes") or []
        if d["TableStatus"] == "ACTIVE" and all(v.get("IndexStatus") == "ACTIVE" for v in vis):
            break
        time.sleep(10)

    yield s
    ddb.delete_table(TableName=table)


@pytest.fixture(scope="module")
def seeded(store):
    import asyncio

    async def _seed():
        await store.add("The user loves sushi and Japanese food", metadata={"kind": "food"})
        await store.add("The user's favorite programming language is Python", metadata={"kind": "tech"})
        await store.add("The user lives in Ho Chi Minh City", metadata={"kind": "location"})

    asyncio.run(_seed())
    return store


def test_implements_memory_store_surface(store):
    assert hasattr(store, "search") and hasattr(store, "add")
    assert store.name == "test" and store.writable is True


async def test_add_returns_id(store):
    result = await store.add("A standalone fact to store")
    assert isinstance(result.get("id"), str) and result["id"]


async def test_semantic_search_ranks_relevant_first(seeded):
    hits = await seeded.search("what food does the user enjoy?", options={"max_search_results": 3})
    assert hits, "expected at least one hit"
    assert "sushi" in hits[0].content.lower()           # semantically closest wins
    assert hits[0].metadata.get("_score") is not None    # score surfaced
    assert hits[0].metadata.get("kind") == "food"        # stored metadata round-trips


async def test_max_search_results_caps(seeded):
    hits = await seeded.search("user", options={"max_search_results": 1})
    assert len(hits) <= 1


async def test_empty_query_returns_empty(store):
    assert await store.search("   ") == []


async def test_not_writable_rejects_add(store):
    ro = DynamoDBMemoryStore(
        name="ro", table_name=store._table, region_name=REGION, writable=False
    )
    with pytest.raises(ValueError):
        await ro.add("should not write")
