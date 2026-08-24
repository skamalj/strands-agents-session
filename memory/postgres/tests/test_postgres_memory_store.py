"""Tests for PostgresMemoryStore against a real pgvector-enabled PostgreSQL.

Uses a small deterministic embedder (no AWS/Bedrock needed) so the test validates
the pgvector search mechanics. Skips if the ``vector`` extension isn't available.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from strands_postgres_store import PostgresMemoryStore

URL = os.environ.get(
    "SQL_TEST_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
)

# A deterministic 4-dim "embedder": maps keywords to basis vectors so ranking is
# predictable without a real embedding model.
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


def _pgvector_available() -> bool:
    try:
        e = create_engine(URL)
        with e.connect() as c:
            r = c.execute(
                text("select 1 from pg_available_extensions where name='vector'")
            ).first()
        return r is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pgvector_available(), reason="pgvector extension not available on the test PostgreSQL"
)


@pytest.fixture()
def store():
    table = f"strands_mem_test_{uuid.uuid4().hex[:8]}"
    s = PostgresMemoryStore(
        name="test", url=URL, table_name=table, embedder=_fake_embed, dimensions=4
    )
    yield s
    with s._engine.begin() as c:
        c.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
    s._engine.dispose()


async def test_add_returns_id(store):
    r = await store.add("A fact about food and sushi")
    assert isinstance(r.get("id"), str) and r["id"]


async def test_semantic_search_ranks_relevant_first(store):
    await store.add("The user loves sushi and Japanese food", metadata={"kind": "food"})
    await store.add("The user's favorite is the Python programming language", metadata={"kind": "tech"})
    await store.add("The user lives in a big city", metadata={"kind": "place"})

    hits = await store.search("what does the user like to eat?", options={"max_search_results": 3})
    assert hits
    assert "sushi" in hits[0].content.lower()          # nearest by vector
    assert hits[0].metadata.get("_score") is not None
    assert hits[0].metadata.get("kind") == "food"      # metadata round-trips


async def test_max_search_results_caps(store):
    for i in range(4):
        await store.add(f"food fact number {i}")
    hits = await store.search("food", options={"max_search_results": 2})
    assert len(hits) <= 2


async def test_empty_query_returns_empty(store):
    assert await store.search("  ") == []


async def test_not_writable_rejects_add(store):
    ro = PostgresMemoryStore(
        name="ro", engine=store._engine, table_name=store._table.name,
        embedder=_fake_embed, dimensions=4, writable=False,
    )
    with pytest.raises(ValueError):
        await ro.add("nope")
