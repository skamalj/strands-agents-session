"""Contract tests for MongoDBStorage against a real (local) MongoDB."""
import uuid

import pytest
from strands.storage import Storage

from strands_mongodb_storage import MongoDBStorage

URI = "mongodb://127.0.0.1:27017/"


def _mongo_available() -> bool:
    try:
        from pymongo import MongoClient

        MongoClient(URI, serverSelectionTimeoutMS=800).admin.command("ping")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _mongo_available(), reason="local MongoDB not reachable")


@pytest.fixture()
def storage():
    coll = f"storage_test_{uuid.uuid4().hex[:8]}"
    s = MongoDBStorage(URI, database_name="strands_storage_test", collection_name=coll)
    yield s
    s._collection.drop()


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
    await storage.delete("never/created")
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
    await storage.write("a.b/one", b"1")
    await storage.write("axb/two", b"1")
    assert await storage.list("a.b/") == ["a.b/one"]  # regex metachar treated literally


async def test_namespace_prefix(storage):
    a = MongoDBStorage(
        URI, database_name="strands_storage_test",
        collection_name=storage._collection.name, prefix="tenant-a",
    )
    b = MongoDBStorage(
        URI, database_name="strands_storage_test",
        collection_name=storage._collection.name, prefix="tenant-b",
    )
    await a.write("k", b"a-val")
    await b.write("k", b"b-val")
    assert await a.read("k") == b"a-val"
    assert await b.read("k") == b"b-val"
    assert await a.list("") == ["k"]
