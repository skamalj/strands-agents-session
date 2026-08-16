"""Contract tests for PostgresStorage against a real local PostgreSQL.

The shared ``engine`` / ``table_name`` fixtures live in conftest.py.
"""
import pytest
from strands.storage import Storage

from strands_postgres_storage import PostgresStorage, SQLStorage


@pytest.fixture()
def storage(engine, table_name):
    return PostgresStorage(engine=engine, table_name=table_name)


def test_is_sqlstorage_and_protocol(storage):
    assert isinstance(storage, Storage)
    assert isinstance(storage, SQLStorage)  # PostgresStorage is a thin SQLStorage subclass


async def test_write_read_round_trip(storage):
    await storage.write("sessions/abc/state.json", b"hello bytes")
    assert await storage.read("sessions/abc/state.json") == b"hello bytes"


async def test_missing_overwrite_delete(storage):
    assert await storage.read("nope") is None
    await storage.write("k", b"one")
    await storage.write("k", b"two")
    assert await storage.read("k") == b"two"
    await storage.delete("k")
    await storage.delete("k")  # no-op
    assert await storage.read("k") is None


async def test_binary_and_empty(storage):
    await storage.write("bin", bytes(range(256)))
    assert await storage.read("bin") == bytes(range(256))
    await storage.write("empty", b"")
    assert await storage.read("empty") == b""


async def test_list_prefix_sorted(storage):
    for k in ["sessions/b", "sessions/a", "sessions/c", "other/x"]:
        await storage.write(k, b"1")
    assert await storage.list("sessions/") == ["sessions/a", "sessions/b", "sessions/c"]
    assert await storage.list("") == ["other/x", "sessions/a", "sessions/b", "sessions/c"]
