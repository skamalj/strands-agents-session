"""strands-storage-dynamodb.

Alternate (search-friendly) distribution name for the Amazon DynamoDB
implementation of the Strands Agents ``Storage`` interface. The implementation
lives in ``strands_dynamodb_storage`` (distribution ``strands-dynamodb-store``);
this package re-exports its public API so both names resolve to the same class.
"""

from strands_dynamodb_storage import DynamoDBStorage

__all__ = ["DynamoDBStorage"]
