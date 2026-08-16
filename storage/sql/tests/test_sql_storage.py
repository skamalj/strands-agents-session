"""Contract tests for SQLStorage against a real database (defaults to PostgreSQL).

Shared ``engine`` / ``table_name`` fixtures live in conftest.py.
"""
import pytest
from strands.storage import Storage

from strands_sql_storage import SQLStorage


@pytest.fixture()
def storage(engine, table_name):
    return SQLStorage(engine=engine, table_name=table_name)


def test_satisfies_protocol(storage):
    assert isinstance(storage, Storage)


async def test_write_read_round_trip(storage):
    await storage.write("sessions/abc/state.json", b"hello bytes")
    assert await storage.read("sessions/abc/state.json") == b"hello bytes"


async def test_read_missing_returns_none(storage):
    assert await storage.read("nope/missing") is None


async def test_overwrite(storage):
    await storage.write("k", b"one")
    await storage.write("k", b"two")
    assert await storage.read("k") == b"two"


async def test_delete_is_noop_when_absent(storage):
    await storage.delete("never/created")  # must not raise
    await storage.write("k", b"v")
    await storage.delete("k")
    assert await storage.read("k") is None


async def test_binary_and_empty_payloads(storage):
    await storage.write("bin", bytes(range(256)))
    assert await storage.read("bin") == bytes(range(256))
    await storage.write("empty", b"")
    assert await storage.read("empty") == b""


async def test_list_prefix_sorted(storage):
    for k in ["sessions/b", "sessions/a", "sessions/c", "other/x"]:
        await storage.write(k, b"1")
    assert await storage.list("sessions/") == ["sessions/a", "sessions/b", "sessions/c"]
    assert await storage.list("") == ["other/x", "sessions/a", "sessions/b", "sessions/c"]


async def test_list_prefix_is_literal(storage):
    # LIKE wildcards in a key must be matched literally, not as patterns.
    await storage.write("a%b/one", b"1")
    await storage.write("axb/two", b"1")
    assert await storage.list("a%b/") == ["a%b/one"]


async def test_namespace_prefix(engine, table_name):
    a = SQLStorage(engine=engine, table_name=table_name, prefix="tenant-a")
    b = SQLStorage(engine=engine, table_name=table_name, prefix="tenant-b")
    await a.write("k", b"a-val")
    await b.write("k", b"b-val")
    assert await a.read("k") == b"a-val"
    assert await b.read("k") == b"b-val"
    assert await a.list("") == ["k"]  # only its own namespace, prefix stripped
