"""Contract tests for DynamoDBStorage against real DynamoDB.

Uses AWS credentials from the environment / a profile (AWS_PROFILE). A single
test table is reused; each test isolates itself with a unique key prefix and
cleans up after itself.
"""
import os
import uuid

import boto3
import pytest
from strands.storage import Storage

from strands_dynamodb_storage import DynamoDBStorage

TABLE = os.environ.get("DDB_TEST_TABLE", "strands_storage_test")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _aws_available() -> bool:
    try:
        boto3.client("sts", region_name=REGION).get_caller_identity()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _aws_available(), reason="AWS credentials not available")


@pytest.fixture()
def storage():
    ns = f"test-{uuid.uuid4().hex[:8]}"
    s = DynamoDBStorage(TABLE, region_name=REGION, prefix=ns)
    yield s
    # Sync cleanup: delete every item this test wrote under its namespace.
    from boto3.dynamodb.conditions import Key

    resp = s._table.query(
        KeyConditionExpression=Key("PK").eq(s._pv) & Key("SK").begins_with(f"{ns}/")
    )
    with s._table.batch_writer() as batch:
        for item in resp.get("Items", []):
            batch.delete_item(Key={"PK": s._pv, "SK": item["SK"]})


def test_satisfies_protocol(storage):
    assert isinstance(storage, Storage)


async def test_write_read_round_trip(storage):
    await storage.write("sessions/abc/state.json", b"hello bytes")
    assert await storage.read("sessions/abc/state.json") == b"hello bytes"


async def test_read_missing_returns_none(storage):
    assert await storage.read("nope/missing") is None


async def test_overwrite(storage):
    await storage.write("k", b"one")
    await storage.write("k", b"two")
    assert await storage.read("k") == b"two"


async def test_delete_is_noop_when_absent(storage):
    await storage.delete("never/created")
    await storage.write("k", b"v")
    await storage.delete("k")
    assert await storage.read("k") is None


async def test_binary_payload(storage):
    await storage.write("bin", bytes(range(256)))
    assert await storage.read("bin") == bytes(range(256))


async def test_list_prefix_sorted(storage):
    for k in ["sessions/b", "sessions/a", "sessions/c", "other/x"]:
        await storage.write(k, b"1")
    assert await storage.list("sessions/") == ["sessions/a", "sessions/b", "sessions/c"]
    assert await storage.list("") == ["other/x", "sessions/a", "sessions/b", "sessions/c"]
