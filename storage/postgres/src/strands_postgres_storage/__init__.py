"""PostgreSQL implementation of the Strands Agents unified ``Storage`` interface.

``PostgresStorage`` persists raw bytes under string keys in a PostgreSQL table,
backing session snapshots, context offloading, memory stores, and anything else
that consumes ``strands.storage.Storage``. It is the SQLAlchemy-backed
``SQLStorage`` (distribution ``strands-sql-storage``) surfaced under a
PostgreSQL-specific name — pass any SQLAlchemy PostgreSQL URL.
"""

from strands_sql_storage import SQLStorage

__all__ = ["PostgresStorage", "SQLStorage"]


class PostgresStorage(SQLStorage):
    """``Storage`` backed by PostgreSQL (via SQLAlchemy).

    Example:
        ```python
        from strands_postgres_storage import PostgresStorage

        storage = PostgresStorage("postgresql://user:pass@localhost:5432/db")
        await storage.write("sessions/abc/state.json", data)
        ```

    Behaviourally identical to :class:`strands_sql_storage.SQLStorage`; provide a
    PostgreSQL connection URL (e.g. ``postgresql+psycopg2://…``).
    """
