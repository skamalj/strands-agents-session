"""Contract tests for DynamoDBStorage against real DynamoDB.

Shared ``storage`` / ``ns`` fixtures (with cleanup) live in conftest.py.
"""
from strands.storage import Storage


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


async def test_binary_payload(storage):
    await storage.write("bin", bytes(range(256)))
    assert await storage.read("bin") == bytes(range(256))


async def test_list_prefix_sorted(storage):
    for k in ["sessions/b", "sessions/a", "sessions/c", "other/x"]:
        await storage.write(k, b"1")
    assert await storage.list("sessions/") == ["sessions/a", "sessions/b", "sessions/c"]
    assert await storage.list("") == ["other/x", "sessions/a", "sessions/b", "sessions/c"]
