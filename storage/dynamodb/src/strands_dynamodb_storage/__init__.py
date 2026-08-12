"""Amazon DynamoDB implementation of the Strands Agents unified ``Storage`` interface.

``DynamoDBStorage`` persists raw bytes under string keys in a single table,
backing session snapshots, context offloading, memory stores, and anything else
that consumes ``strands.storage.Storage``.

Keys are stored as the sort key under a constant partition, so ``list(prefix)``
is a ``begins_with`` range query returning keys already sorted ascending.
"""

from __future__ import annotations

import asyncio
import builtins
import re
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key

from strands.types.exceptions import StorageError

__all__ = ["DynamoDBStorage"]


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


def _to_bytes(value: Any) -> bytes:
    """Coerce a DynamoDB Binary attribute (or raw bytes) to ``bytes``."""
    return value.value if hasattr(value, "value") else bytes(value)


class DynamoDBStorage:
    """Persists bytes under string keys in an Amazon DynamoDB table.

    All values share one partition (``partition_value``) with the storage key as
    the sort key, which keeps ``list`` an ordered ``begins_with`` query. For very
    large or high-throughput datasets this concentrates load on one partition;
    use distinct tables (or ``partition_value``) per namespace to spread it.

    Example:
        ```python
        from strands_dynamodb_storage import DynamoDBStorage

        storage = DynamoDBStorage("strands_storage")
        await storage.write("sessions/abc/state.json", data)
        ```
    """

    def __init__(
        self,
        table_name: str,
        *,
        region_name: Optional[str] = None,
        boto_session: Optional["boto3.Session"] = None,
        endpoint_url: Optional[str] = None,
        partition_value: str = "storage",
        prefix: str = "",
    ) -> None:
        """Initialize DynamoDB storage.

        Args:
            table_name: DynamoDB table (auto-created, PAY_PER_REQUEST, if absent).
            region_name: AWS region; ignored if ``boto_session`` is given.
            boto_session: Pre-built boto3 session (profiles / custom credentials).
            endpoint_url: Override endpoint — e.g. local DynamoDB.
            partition_value: Constant partition key value under which keys live.
            prefix: Key prefix prepended to every key (namespace within the table).
        """
        session = boto_session or boto3.Session(region_name=region_name)
        self._dynamodb = session.resource("dynamodb", endpoint_url=endpoint_url)
        self._table = self._get_or_create_table(table_name)
        self._pv = partition_value
        normalized = _normalize_prefix(prefix).rstrip("/")
        self._prefix = f"{normalized}/" if normalized else ""

    def _get_or_create_table(self, table_name: str) -> Any:
        table = self._dynamodb.Table(table_name)
        try:
            table.load()
            return table
        except self._dynamodb.meta.client.exceptions.ResourceNotFoundException:
            table = self._dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            return table

    def _full(self, key: str) -> str:
        return f"{self._prefix}{_normalize_key(key)}"

    async def write(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``, overwriting any existing value."""
        full = self._full(key)

        def _write() -> None:
            self._table.put_item(Item={"PK": self._pv, "SK": full, "data": bytes(data)})

        try:
            await asyncio.to_thread(_write)
        except Exception as error:
            raise StorageError(f"Failed to write '{key}'") from error

    async def read(self, key: str) -> bytes | None:
        """Return the bytes stored under ``key``, or ``None`` if absent."""
        full = self._full(key)

        def _read() -> bytes | None:
            item = self._table.get_item(Key={"PK": self._pv, "SK": full}).get("Item")
            return _to_bytes(item["data"]) if item is not None else None

        try:
            return await asyncio.to_thread(_read)
        except Exception as error:
            raise StorageError(f"Failed to read '{key}'") from error

    async def delete(self, key: str) -> None:
        """Delete the value stored under ``key``. A no-op if it does not exist."""
        full = self._full(key)

        def _delete() -> None:
            self._table.delete_item(Key={"PK": self._pv, "SK": full})

        try:
            await asyncio.to_thread(_delete)
        except Exception as error:
            raise StorageError(f"Failed to delete '{key}'") from error

    async def list(self, query: str = "") -> builtins.list[str]:
        """List keys matching the given prefix, sorted ascending (prefix stripped)."""
        prefix = f"{self._prefix}{_normalize_prefix(query)}"

        def _list() -> builtins.list[str]:
            condition = Key("PK").eq(self._pv)
            if prefix:
                condition = condition & Key("SK").begins_with(prefix)

            keys: builtins.list[str] = []
            kwargs: dict[str, Any] = {"KeyConditionExpression": condition}
            while True:
                response = self._table.query(**kwargs)
                for item in response.get("Items", []):
                    sk = item["SK"]
                    if self._prefix and sk.startswith(self._prefix):
                        sk = sk[len(self._prefix) :]
                    keys.append(sk)
                last = response.get("LastEvaluatedKey")
                if not last:
                    break
                kwargs["ExclusiveStartKey"] = last
            return sorted(keys)

        try:
            return await asyncio.to_thread(_list)
        except Exception as error:
            raise StorageError(f"Failed to list keys with prefix '{query}'") from error
