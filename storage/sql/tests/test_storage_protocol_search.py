"""Storage backends must subclass strands.storage.Storage so the 1.54+ default search() is inherited
(FileMemoryStore calls storage.search)."""
import os
import pytest
from strands.storage import Storage

from strands_sql_storage import SQLStorage

URL = os.environ.get("SQL_TEST_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")


async def test_is_storage_and_default_search_works():
    s = SQLStorage(URL, table_name="proto_search_test")
    assert isinstance(s, Storage)
    await s.write("notes/a.txt", b"the user loves sushi")
    await s.write("notes/b.txt", b"python every day")
    results = await s.search("sushi")
    assert results and results[0].key == "notes/a.txt"
