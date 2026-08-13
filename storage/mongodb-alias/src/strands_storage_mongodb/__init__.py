"""strands-storage-mongodb.

Alternate (search-friendly) distribution name for the MongoDB implementation of
the Strands Agents ``Storage`` interface. The implementation lives in
``strands_mongodb_storage`` (distribution ``strands-mongodb-storage``); this
package re-exports its public API so both names resolve to the same class.
"""

from strands_mongodb_storage import MongoDBStorage

__all__ = ["MongoDBStorage"]
