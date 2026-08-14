"""strands-storage-postgres.

Alternate (search-friendly) distribution name for the PostgreSQL implementation
of the Strands Agents ``Storage`` interface. The implementation lives in
``strands_postgres_storage`` (distribution ``strands-postgres-storage``); this
package re-exports its public API so both names resolve to the same classes.
"""

from strands_postgres_storage import PostgresStorage, SQLStorage

__all__ = ["PostgresStorage", "SQLStorage"]
