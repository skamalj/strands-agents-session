"""Amazon DynamoDB session backend for Strands Agents.

Provides a ``DynamoDBSessionStorage`` (implementing the ``SessionStorage``
interface from ``strands-agents-session``) and a thin ``DynamoDBSessionManager``
that wires it into ``KeyValueSessionManager``. All the session-repository logic
lives in the base package; this module is just the storage layer.

Single DynamoDB table, both keys strings (``PK`` HASH, ``SK`` RANGE). Payloads
are stored as a JSON string in a ``data`` attribute, which sidesteps DynamoDB's
float/empty-value quirks.
"""

import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from strands_agents_session import KeyValueSessionManager, SessionStorage

if TYPE_CHECKING:  # pragma: no cover
    from botocore.config import Config as BotocoreConfig


class DynamoDBSessionStorage(SessionStorage):
    """DynamoDB implementation of the session ``SessionStorage`` interface."""

    def __init__(
        self,
        table_name: str,
        *,
        boto_session: "boto3.Session | None" = None,
        boto_client_config: "BotocoreConfig | None" = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        session = boto_session or boto3.Session(region_name=region_name)
        self.dynamodb = session.resource(
            "dynamodb", endpoint_url=endpoint_url, config=boto_client_config
        )
        self.client = session.client(
            "dynamodb", endpoint_url=endpoint_url, config=boto_client_config
        )
        self.table_name = table_name
        self.ttl_seconds = ttl_seconds
        self.table = self._get_or_create_table(table_name)

    def _get_or_create_table(self, table_name: str):
        table = self.dynamodb.Table(table_name)
        try:
            table.load()
            return table
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        table = self.dynamodb.create_table(
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
        if self.ttl_seconds:
            try:
                self.client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
                )
            except ClientError:  # pragma: no cover
                pass
        return table

    # SessionStorage ----------------------------------------------------

    def put(self, item: Dict[str, Any]) -> None:
        self.table.put_item(Item=self._to_ddb(item))

    def _to_ddb(self, item: Dict[str, Any]) -> Dict[str, Any]:
        ddb_item = {"PK": item["pk"], "SK": item["sk"], "data": item["data"]}
        if self.ttl_seconds:
            ddb_item["ttl"] = int(time.time()) + self.ttl_seconds
        return ddb_item

    def put_batch(self, items: List[Dict[str, Any]]) -> None:
        # batch_writer transparently chunks to DynamoDB's 25-item limit and
        # retries any UnprocessedItems.
        with self.table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=self._to_ddb(item))

    def get(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        item = self.table.get_item(Key={"PK": pk, "SK": sk}).get("Item")
        if not item:
            return None
        return {"pk": item["PK"], "sk": item["SK"], "data": item["data"]}

    def query(
        self, pk: str, sk_gte: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        condition = Key("PK").eq(pk)
        if sk_gte is not None:
            condition = condition & Key("SK").gte(sk_gte)

        items: List[dict] = []
        start_key = None
        while True:
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": condition,
                "ScanIndexForward": True,
            }
            if start_key is not None:
                query_kwargs["ExclusiveStartKey"] = start_key
            if limit is not None:
                query_kwargs["Limit"] = limit - len(items)
            resp = self.table.query(**query_kwargs)
            items.extend(resp.get("Items", []))
            start_key = resp.get("LastEvaluatedKey")
            if limit is not None and len(items) >= limit:
                items = items[:limit]
                break
            if not start_key:
                break

        return [{"pk": i["PK"], "sk": i["SK"], "data": i["data"]} for i in items]

    def delete(self, pk: str, sk: str) -> None:
        self.table.delete_item(Key={"PK": pk, "SK": sk})

    def delete_partition(self, pk: str) -> None:
        start_key = None
        while True:
            query_kwargs: Dict[str, Any] = {"KeyConditionExpression": Key("PK").eq(pk)}
            if start_key is not None:
                query_kwargs["ExclusiveStartKey"] = start_key
            resp = self.table.query(**query_kwargs)
            items = resp.get("Items", [])
            with self.table.batch_writer() as batch:
                for i in items:
                    batch.delete_item(Key={"PK": i["PK"], "SK": i["SK"]})
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break


class DynamoDBSessionManager(KeyValueSessionManager):
    """DynamoDB-backed session manager for Strands Agents.

        agent = Agent(session_manager=DynamoDBSessionManager(
            session_id="user-123", table_name="strands-sessions",
        ))

    The table is created automatically (on-demand billing) if it does not exist.
    """

    def __init__(
        self,
        session_id: str,
        table_name: str,
        *,
        boto_session: "boto3.Session | None" = None,
        boto_client_config: "BotocoreConfig | None" = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        ttl_seconds: int | None = None,
        **kwargs: Any,
    ) -> None:
        storage = DynamoDBSessionStorage(
            table_name,
            boto_session=boto_session,
            boto_client_config=boto_client_config,
            region_name=region_name,
            endpoint_url=endpoint_url,
            ttl_seconds=ttl_seconds,
        )
        super().__init__(session_id=session_id, storage=storage)
