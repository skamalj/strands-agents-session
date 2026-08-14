"""Contract tests for PostgresStorage against a real local PostgreSQL."""
import os
import uuid

import pytest
from sqlalchemy import MetaData, Table, create_engine
from strands.storage import Storage

from strands_postgres_storage import PostgresStorage, SQLStorage

URL = os.environ.get(
    "SQL_TEST_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
)


def _db_available() -> bool:
    try:
        from sqlalchemy import text

        with create_engine(URL).connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason=f"PostgreSQL not reachable: {URL}")


@pytest.fixture()
def table_name():
    name = f"strands_pg_storage_test_{uuid.uuid4().hex[:8]}"
    yield name
    Table(name, MetaData(), autoload_with=create_engine(URL)).drop(
        create_engine(URL), checkfirst=True
    )


@pytest.fixture()
def storage(table_name):
    return PostgresStorage(url=URL, table_name=table_name)


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
