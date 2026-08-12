"""strands-sql-session-manager.

Catalog-friendly distribution name for the SQL (SQLAlchemy) session manager. The
implementation lives in ``strands_session_sql`` (distribution
``strands-session-sql``); this package re-exports its public API so both names
resolve to the same classes.
"""

from strands_session_sql import SQLSessionManager, SQLSessionStorage

__all__ = ["SQLSessionManager", "SQLSessionStorage"]
