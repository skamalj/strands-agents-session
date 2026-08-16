"""Shared PostgreSQL engine for the storage tests.

One session-scoped engine (disposed at the end) avoids leaking a connection pool
per test — creating many short-lived ``SQLStorage(url=...)`` instances otherwise
exhausts PostgreSQL's connection slots mid-run.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

URL = os.environ.get(
    "SQL_TEST_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
)


@pytest.fixture(scope="session")
def engine():
    try:
        e = create_engine(URL, pool_size=25, max_overflow=25, pool_pre_ping=True)
        with e.connect() as c:
            c.execute(text("select 1"))
    except Exception:
        pytest.skip(f"PostgreSQL not reachable: {URL}")
    yield e
    e.dispose()


@pytest.fixture()
def table_name(engine):
    name = f"strands_pg_test_{uuid.uuid4().hex[:8]}"
    yield name
    with engine.begin() as c:
        c.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
