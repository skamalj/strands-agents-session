"""MongoDB implementation of the Strands Agents unified ``Storage`` interface.

``MongoDBStorage`` persists raw bytes under string keys in a single collection,
backing session snapshots, context offloading, memory stores, and anything else
that consumes ``strands.storage.Storage``.
"""

from __future__ import annotations

import asyncio
import builtins
import re
from typing import Optional

from bson.binary import Binary
from pymongo import MongoClient

from strands.types.exceptions import StorageError

__all__ = ["MongoDBStorage"]


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


class MongoDBStorage:
    """Persists bytes under string keys in a MongoDB collection.

    Example:
        ```python
        from strands_mongodb_storage import MongoDBStorage

        storage = MongoDBStorage("mongodb://localhost:27017")
        await storage.write("sessions/abc/state.json", data)
        ```
    """

    def __init__(
        self,
        connection_string: str = "mongodb://127.0.0.1:27017/",
        *,
        database_name: str = "strands_storage",
        collection_name: str = "storage",
        client: Optional[MongoClient] = None,
        prefix: str = "",
    ) -> None:
        """Initialize MongoDB storage.

        Args:
            connection_string: MongoDB URI (ignored if ``client`` is given).
            database_name: Database holding the collection.
            collection_name: Collection used for key/value documents.
            client: Pre-built ``MongoClient`` to use instead of ``connection_string``.
            prefix: Key prefix prepended to every key (namespace within the collection).
        """
        self._client = client or MongoClient(connection_string)
        self._collection = self._client[database_name][collection_name]
        normalized = _normalize_prefix(prefix).rstrip("/")
        self._prefix = f"{normalized}/" if normalized else ""

    def _full(self, key: str) -> str:
        return f"{self._prefix}{_normalize_key(key)}"

    async def write(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``, overwriting any existing value."""
        full = self._full(key)

        def _write() -> None:
            self._collection.replace_one(
                {"_id": full}, {"_id": full, "data": Binary(bytes(data))}, upsert=True
            )

        try:
            await asyncio.to_thread(_write)
        except Exception as error:
            raise StorageError(f"Failed to write '{key}'") from error

    async def read(self, key: str) -> bytes | None:
        """Return the bytes stored under ``key``, or ``None`` if absent."""
        full = self._full(key)

        def _read() -> bytes | None:
            doc = self._collection.find_one({"_id": full})
            return bytes(doc["data"]) if doc is not None else None

        try:
            return await asyncio.to_thread(_read)
        except Exception as error:
            raise StorageError(f"Failed to read '{key}'") from error

    async def delete(self, key: str) -> None:
        """Delete the value stored under ``key``. A no-op if it does not exist."""
        full = self._full(key)

        def _delete() -> None:
            self._collection.delete_one({"_id": full})

        try:
            await asyncio.to_thread(_delete)
        except Exception as error:
            raise StorageError(f"Failed to delete '{key}'") from error

    async def list(self, query: str = "") -> builtins.list[str]:
        """List keys matching the given prefix, sorted ascending (prefix stripped)."""
        prefix = f"{self._prefix}{_normalize_prefix(query)}"

        def _list() -> builtins.list[str]:
            cursor = self._collection.find(
                {"_id": {"$regex": f"^{re.escape(prefix)}"}}, {"_id": 1}
            )
            keys = [doc["_id"] for doc in cursor]
            if self._prefix:
                keys = [k[len(self._prefix) :] for k in keys if k.startswith(self._prefix)]
            return sorted(keys)

        try:
            return await asyncio.to_thread(_list)
        except Exception as error:
            raise StorageError(f"Failed to list keys with prefix '{query}'") from error
