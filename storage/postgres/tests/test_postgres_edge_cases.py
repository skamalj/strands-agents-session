"""Thorough edge-case tests for PostgresStorage against real local PostgreSQL.

Covers key normalization, prefix-listing semantics, namespacing, concurrency,
large/unicode payloads, and error handling. Shared ``engine`` / ``table_name``
fixtures live in conftest.py.
"""
import asyncio

import pytest
from strands.storage import Storage
from strands.types.exceptions import StorageError

from strands_postgres_storage import PostgresStorage


@pytest.fixture()
def storage(engine, table_name):
    return PostgresStorage(engine=engine, table_name=table_name)


# --- key normalization --------------------------------------------------------

async def test_slashes_are_collapsed_and_stripped(storage):
    await storage.write("a//b///c", b"x")
    assert await storage.read("a/b/c") == b"x"          # collapsed
    assert await storage.read("/a/b/c/") == b"x"        # leading/trailing stripped
    assert await storage.list("") == ["a/b/c"]          # stored canonicalized


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
    assert await storage.list("a/b/") == ["a/b/c", "a/b/d"]   # full keys, sorted
    assert await storage.list("a/") == ["a/b/c", "a/b/d", "a/e"]
    assert await storage.list("") == ["a/b/c", "a/b/d", "a/e", "z"]


async def test_list_prefix_matching_nothing(storage):
    await storage.write("foo/bar", b"1")
    assert await storage.list("nope/") == []


async def test_list_prefix_equal_to_full_key(storage):
    await storage.write("exact/key", b"1")
    await storage.write("exact/key2", b"1")
    assert await storage.list("exact/key") == ["exact/key", "exact/key2"]


async def test_list_underscore_wildcard_is_literal(storage):
    # '_' is a single-char LIKE wildcard; must be matched literally.
    await storage.write("a_b/one", b"1")
    await storage.write("axb/two", b"1")
    assert await storage.list("a_b/") == ["a_b/one"]


# --- namespacing --------------------------------------------------------------

async def test_namespaced_list_and_isolation(engine, table_name):
    a = PostgresStorage(engine=engine, table_name=table_name, prefix="tenant-a")
    b = PostgresStorage(engine=engine, table_name=table_name, prefix="tenant-b")
    await a.write("x/1", b"a")
    await a.write("x/2", b"a")
    await b.write("x/1", b"b")
    assert await a.list("") == ["x/1", "x/2"]     # prefix stripped, only tenant-a
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
    keys = [f"c/{i:03d}" for i in range(20)]
    await asyncio.gather(*(storage.write(k, k.encode()) for k in keys))
    assert await storage.list("c/") == keys                 # all present, ordered
    vals = await asyncio.gather(*(storage.read(k) for k in keys))
    assert vals == [k.encode() for k in keys]
