"""MongoDB session backend for Strands Agents.

Provides a ``MongoDBSessionStorage`` (implementing the ``SessionStorage``
interface from ``strands-agents-session``) and a thin ``MongoDBSessionManager``
that wires it into ``KeyValueSessionManager``. All the session-repository logic
lives in the base package; this module is just the storage layer.

Records are stored in a single collection with a compound ``_id`` of the form
``{pk, sk}``, and a ``data`` field holding the serialized payload. A compound
index on ``(pk, sk)`` gives ordered range scans for ``list_messages``.
"""

from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, MongoClient

from strands_agents_session import KeyValueSessionManager, SessionStorage


class MongoDBSessionStorage(SessionStorage):
    """MongoDB implementation of the session ``SessionStorage`` interface."""

    def __init__(
        self,
        *,
        connection_string: str = "mongodb://127.0.0.1:27017/",
        database_name: str = "strands_sessions",
        collection_name: str = "sessions",
        client: Optional[MongoClient] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self.client = client or MongoClient(connection_string)
        self.collection = self.client[database_name][collection_name]
        # Compound index on (pk, sk) — unique identity + ordered range scans.
        self.collection.create_index([("pk", ASCENDING), ("sk", ASCENDING)], unique=True)
        self.ttl_seconds = ttl_seconds
        if ttl_seconds:
            # MongoDB TTL index expires documents `ttl_seconds` after `created_at`.
            self.collection.create_index("created_at", expireAfterSeconds=ttl_seconds)

    # SessionStorage ----------------------------------------------------

    def put(self, item: Dict[str, Any]) -> None:
        self.collection.replace_one(
            {"pk": item["pk"], "sk": item["sk"]}, self._to_doc(item), upsert=True
        )

    def _to_doc(self, item: Dict[str, Any]) -> Dict[str, Any]:
        doc = {"pk": item["pk"], "sk": item["sk"], "data": item["data"]}
        if self.ttl_seconds:
            import datetime

            doc["created_at"] = datetime.datetime.now(datetime.timezone.utc)
        return doc

    def put_batch(self, items: List[Dict[str, Any]]) -> None:
        from pymongo import ReplaceOne

        ops = [
            ReplaceOne({"pk": i["pk"], "sk": i["sk"]}, self._to_doc(i), upsert=True)
            for i in items
        ]
        if ops:
            self.collection.bulk_write(ops, ordered=True)

    def get(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({"pk": pk, "sk": sk})
        if doc is None:
            return None
        return {"pk": doc["pk"], "sk": doc["sk"], "data": doc["data"]}

    def query(
        self, pk: str, sk_gte: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"pk": pk}
        if sk_gte is not None:
            query["sk"] = {"$gte": sk_gte}
        cursor = self.collection.find(query).sort("sk", ASCENDING)
        if limit is not None:
            cursor = cursor.limit(limit)
        return [{"pk": d["pk"], "sk": d["sk"], "data": d["data"]} for d in cursor]

    def delete(self, pk: str, sk: str) -> None:
        self.collection.delete_one({"pk": pk, "sk": sk})

    def delete_partition(self, pk: str) -> None:
        self.collection.delete_many({"pk": pk})


class MongoDBSessionManager(KeyValueSessionManager):
    """MongoDB-backed session manager for Strands Agents.

        agent = Agent(session_manager=MongoDBSessionManager(
            session_id="user-123",
            connection_string="mongodb://127.0.0.1:27017/",
        ))
    """

    def __init__(
        self,
        session_id: str,
        *,
        connection_string: str = "mongodb://127.0.0.1:27017/",
        database_name: str = "strands_sessions",
        collection_name: str = "sessions",
        client: Optional[MongoClient] = None,
        ttl_seconds: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        storage = MongoDBSessionStorage(
            connection_string=connection_string,
            database_name=database_name,
            collection_name=collection_name,
            client=client,
            ttl_seconds=ttl_seconds,
        )
        super().__init__(session_id=session_id, storage=storage)
