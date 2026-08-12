"""SQL (SQLAlchemy) implementation of the Strands Agents unified ``Storage`` interface.

``SQLStorage`` persists raw bytes under string keys in a single table, backing
session snapshots, context offloading, memory stores, and anything else that
consumes ``strands.storage.Storage``. One provider for any SQLAlchemy-supported
database (SQLite, PostgreSQL, MySQL, …) — selected purely by connection URL.
"""

from __future__ import annotations

import asyncio
import builtins
import re
from typing import Optional

from sqlalchemy import (
    Column,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    delete as sa_delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from strands.types.exceptions import StorageError

__all__ = ["SQLStorage"]


def _normalize_key(key: str) -> str:
    normalized = re.sub(r"/+", "/", key).strip("/")
    if not normalized:
        raise StorageError("Storage key must not be empty")
    if ".." in normalized.split("/"):
        raise StorageError(f"Invalid storage key '{key}': '..' path segments are not allowed")
    return normalized


def _normalize_prefix(prefix: str) -> str:
    normalized = re.sub(r"/+", "/", prefix).lstrip("/")
    if ".." in normalized.split("/"):
        raise StorageError(f"Invalid storage prefix '{prefix}': '..' path segments are not allowed")
    return normalized


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so a prefix matches literally (escape char is '\\')."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SQLStorage:
    """Persists bytes under string keys in a SQLAlchemy-backed table.

    Example:
        ```python
        from strands_sql_storage import SQLStorage

        storage = SQLStorage("postgresql://user:pass@localhost/db")
        await storage.write("sessions/abc/state.json", data)
        ```
    """

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        table_name: str = "strands_storage",
        engine: Optional[Engine] = None,
        prefix: str = "",
    ) -> None:
        """Initialize SQL storage.

        Args:
            url: SQLAlchemy connection URL (e.g. ``sqlite:///state.db``). Required
                unless ``engine`` is given.
            table_name: Table used to hold key/value rows (created if absent).
            engine: Pre-built SQLAlchemy ``Engine``; use instead of ``url``.
            prefix: Key prefix prepended to every key (namespace within the table).

        Raises:
            StorageError: If neither ``url`` nor ``engine`` is provided.
        """
        if engine is None and url is None:
            raise StorageError("Provide either 'url' or 'engine'")
        self._engine = engine or create_engine(url)  # type: ignore[arg-type]
        self._metadata = MetaData()
        self._table = Table(
            table_name,
            self._metadata,
            Column("key", String(1024), primary_key=True),
            Column("data", LargeBinary, nullable=False),
        )
        self._metadata.create_all(self._engine)
        normalized = _normalize_prefix(prefix).rstrip("/")
        self._prefix = f"{normalized}/" if normalized else ""

    def _full(self, key: str) -> str:
        return f"{self._prefix}{_normalize_key(key)}"

    async def write(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``, overwriting any existing value."""
        full = self._full(key)

        def _write() -> None:
            with self._engine.begin() as conn:
                updated = conn.execute(
                    update(self._table).where(self._table.c.key == full).values(data=data)
                )
                if updated.rowcount == 0:
                    conn.execute(insert(self._table).values(key=full, data=data))

        try:
            await asyncio.to_thread(_write)
        except Exception as error:
            raise StorageError(f"Failed to write '{key}'") from error

    async def read(self, key: str) -> bytes | None:
        """Return the bytes stored under ``key``, or ``None`` if absent."""
        full = self._full(key)

        def _read() -> bytes | None:
            with self._engine.connect() as conn:
                row = conn.execute(
                    select(self._table.c.data).where(self._table.c.key == full)
                ).first()
            return bytes(row[0]) if row is not None else None

        try:
            return await asyncio.to_thread(_read)
        except Exception as error:
            raise StorageError(f"Failed to read '{key}'") from error

    async def delete(self, key: str) -> None:
        """Delete the value stored under ``key``. A no-op if it does not exist."""
        full = self._full(key)

        def _delete() -> None:
            with self._engine.begin() as conn:
                conn.execute(sa_delete(self._table).where(self._table.c.key == full))

        try:
            await asyncio.to_thread(_delete)
        except Exception as error:
            raise StorageError(f"Failed to delete '{key}'") from error

    async def list(self, query: str = "") -> builtins.list[str]:
        """List keys matching the given prefix, sorted ascending (prefix stripped)."""
        prefix = f"{self._prefix}{_normalize_prefix(query)}"
        pattern = f"{_escape_like(prefix)}%"

        def _list() -> builtins.list[str]:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    select(self._table.c.key).where(self._table.c.key.like(pattern, escape="\\"))
                ).all()
            keys = [r[0] for r in rows]
            if self._prefix:
                keys = [k[len(self._prefix) :] for k in keys if k.startswith(self._prefix)]
            return sorted(keys)

        try:
            return await asyncio.to_thread(_list)
        except Exception as error:
            raise StorageError(f"Failed to list keys with prefix '{query}'") from error
