"""Thorough edge-case tests for DynamoDBStorage against real DynamoDB.

Mirrors the Postgres/Mongo edge suites, adapted for DynamoDB (notably the 400 KB
item-size limit instead of a multi-MB payload). Shared fixtures in conftest.py.
"""
import asyncio

import pytest
from strands.storage import Storage
from strands.types.exceptions import StorageError

from strands_dynamodb_storage import DynamoDBStorage


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


# --- namespacing --------------------------------------------------------------

async def test_namespaced_list_and_isolation(ns, table_name, region):
    a = DynamoDBStorage(table_name, region_name=region, prefix=f"{ns}/tenant-a")
    b = DynamoDBStorage(table_name, region_name=region, prefix=f"{ns}/tenant-b")
    await a.write("x/1", b"a")
    await a.write("x/2", b"a")
    await b.write("x/1", b"b")
    assert await a.list("") == ["x/1", "x/2"]     # prefix stripped, only tenant-a
    assert await b.list("x/") == ["x/1"]
    assert await a.read("x/1") == b"a"
    assert await b.read("x/1") == b"b"


# --- payloads (DynamoDB item limit is 400 KB) ---------------------------------

async def test_large_payload_round_trips(storage):
    blob = bytes((i * 7) % 256 for i in range(300_000))  # ~300 KB, under the 400 KB cap
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
    keys = [f"c/{i:03d}" for i in range(15)]
    await asyncio.gather(*(storage.write(k, k.encode()) for k in keys))
    assert await storage.list("c/") == keys
    vals = await asyncio.gather(*(storage.read(k) for k in keys))
    assert vals == [k.encode() for k in keys]
