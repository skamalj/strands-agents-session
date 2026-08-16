"""Shared fixtures for the DynamoDB storage tests.

A single test table is reused; each test isolates itself with a unique key
prefix (``ns``) and the fixture deletes everything under that prefix afterwards.
Requires AWS credentials (AWS_PROFILE / env); tests skip without them.
"""
import os
import uuid

import boto3
import pytest
from boto3.dynamodb.conditions import Key

from strands_dynamodb_storage import DynamoDBStorage

TABLE = os.environ.get("DDB_TEST_TABLE", "strands_storage_test")
REGION = os.environ.get("AWS_REGION", "us-east-1")


@pytest.fixture(scope="session", autouse=True)
def _require_aws():
    try:
        boto3.client("sts", region_name=REGION).get_caller_identity()
    except Exception:
        pytest.skip("AWS credentials not available")


@pytest.fixture()
def ns():
    name = f"test-{uuid.uuid4().hex[:8]}"
    yield name
    # Delete every item written under this test's namespace.
    s = DynamoDBStorage(TABLE, region_name=REGION)
    resp = s._table.query(
        KeyConditionExpression=Key("PK").eq(s._pv) & Key("SK").begins_with(f"{name}/")
    )
    with s._table.batch_writer() as batch:
        for item in resp.get("Items", []):
            batch.delete_item(Key={"PK": s._pv, "SK": item["SK"]})


@pytest.fixture()
def storage(ns):
    return DynamoDBStorage(TABLE, region_name=REGION, prefix=ns)


@pytest.fixture()
def table_name():
    return TABLE


@pytest.fixture()
def region():
    return REGION
