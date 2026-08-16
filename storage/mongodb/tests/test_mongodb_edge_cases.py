"""Thorough edge-case tests for MongoDBStorage against real local MongoDB.

Covers key normalization, prefix-listing semantics, namespacing, concurrency,
large/unicode payloads, and error handling — beyond the basic contract tests.
"""
import asyncio
import uuid

import pytest
from strands.storage import Storage
from strands.types.exceptions import StorageError

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
    coll = f"edge_{uuid.uuid4().hex[:8]}"
    s = MongoDBStorage(URI, database_name="strands_storage_test", collection_name=coll)
    yield s
    s._collection.drop()


# --- key normalization --------------------------------------------------------

async def test_slashes_are_collapsed_and_stripped(storage):
    await storage.write("a//b///c", b"x")
    assert await storage.read("a/b/c") == b"x"
    assert await storage.read("/a/b/c/") == b"x"
    assert await storage.list("") == ["a/b/c"]


async def test_empty_key_rejected(storage):
    with pytest.raises(StorageError):
        await storage.write("", b"x")
    with pytest.raises(StorageError):
        await storage.write("///", b"x")
    with pytest.raises(StorageError):
        await storage.read("")


async def test_dotdot_segment_rejected(storage):
    for bad in ["..", "a/../b", "../etc/passwd"]:
        with pytest.raises(StorageError):
            await storage.write(bad, b"x")


# --- prefix listing -----------------------------------------------------------

async def test_list_returns_full_keys_sorted(storage):
    for k in ["a/b/d", "a/b/c", "a/e", "z"]:
        await storage.write(k, b"1")
    assert await storage.list("a/b/") == ["a/b/c", "a/b/d"]
    assert await storage.list("a/") == ["a/b/c", "a/b/d", "a/e"]
    assert await storage.list("") == ["a/b/c", "a/b/d", "a/e", "z"]


async def test_list_prefix_matching_nothing(storage):
    await storage.write("foo/bar", b"1")
    assert await storage.list("nope/") == []


async def test_list_prefix_equal_to_full_key(storage):
    await storage.write("exact/key", b"1")
    await storage.write("exact/key2", b"1")
    assert await storage.list("exact/key") == ["exact/key", "exact/key2"]


async def test_list_regex_metachars_are_literal(storage):
    # A '.' in the prefix must match literally, not as a regex wildcard.
    await storage.write("a.b/one", b"1")
    await storage.write("axb/two", b"1")
    assert await storage.list("a.b/") == ["a.b/one"]


# --- namespacing --------------------------------------------------------------

async def test_namespaced_list_and_isolation(storage):
    coll = storage._collection.name
    a = MongoDBStorage(URI, database_name="strands_storage_test", collection_name=coll, prefix="tenant-a")
    b = MongoDBStorage(URI, database_name="strands_storage_test", collection_name=coll, prefix="tenant-b")
    await a.write("x/1", b"a")
    await a.write("x/2", b"a")
    await b.write("x/1", b"b")
    assert await a.list("") == ["x/1", "x/2"]
    assert await b.list("x/") == ["x/1"]
    assert await a.read("x/1") == b"a"
    assert await b.read("x/1") == b"b"


# --- payloads -----------------------------------------------------------------

async def test_large_payload_round_trips(storage):
    blob = bytes((i * 7) % 256 for i in range(1_000_000))  # ~1 MB
    await storage.write("big", blob)
    assert await storage.read("big") == blob


async def test_unicode_key(storage):
    await storage.write("sessions/日本語/ключ", b"u")
    assert await storage.read("sessions/日本語/ключ") == b"u"


async def test_overwrite_grow_and_shrink(storage):
    await storage.write("k", b"x" * 1000)
    await storage.write("k", b"y")
    assert await storage.read("k") == b"y"


# --- concurrency (validates the asyncio.to_thread wrapping) --------------------

async def test_concurrent_writes_and_reads(storage):
    keys = [f"c/{i:03d}" for i in range(50)]
    await asyncio.gather(*(storage.write(k, k.encode()) for k in keys))
    assert await storage.list("c/") == keys
    vals = await asyncio.gather(*(storage.read(k) for k in keys))
    assert vals == [k.encode() for k in keys]
