"""SQL session backend for Strands Agents, via SQLAlchemy.

One provider for any SQLAlchemy-supported database (SQLite, PostgreSQL, MySQL, …)
— selected purely by connection URL. Provides a ``SQLSessionStorage``
(implementing the ``SessionStorage`` interface from ``strands-agents-session``)
and a thin ``SQLSessionManager``.

Single table ``(pk, sk, data)`` with a composite primary key. Upsert is done
portably (update-then-insert) so no dialect-specific SQL is required.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from strands_agents_session import KeyValueSessionManager, SessionStorage


class SQLSessionStorage(SessionStorage):
    """SQLAlchemy implementation of the session ``SessionStorage`` interface."""

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        table_name: str = "strands_sessions",
        engine: Optional[Engine] = None,
    ) -> None:
        if engine is None and url is None:
            raise ValueError("Provide either 'url' or 'engine'")
        self.engine = engine or create_engine(url)
        self.metadata = MetaData()
        self.table = Table(
            table_name,
            self.metadata,
            Column("pk", String(255), primary_key=True),
            Column("sk", String(255), primary_key=True),
            Column("data", Text, nullable=False),
        )
        self.metadata.create_all(self.engine)

    # SessionStorage ----------------------------------------------------

    def put(self, item: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            self._upsert(conn, item)

    def put_batch(self, items: List[Dict[str, Any]]) -> None:
        # One transaction, one commit for the whole batch (portable upsert).
        with self.engine.begin() as conn:
            for item in items:
                self._upsert(conn, item)

    def _upsert(self, conn, item: Dict[str, Any]) -> None:
        t = self.table
        result = conn.execute(
            update(t).where(t.c.pk == item["pk"], t.c.sk == item["sk"]).values(data=item["data"])
        )
        if result.rowcount == 0:
            conn.execute(insert(t).values(pk=item["pk"], sk=item["sk"], data=item["data"]))

    def get(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        t = self.table
        with self.engine.connect() as conn:
            row = conn.execute(
                select(t.c.data).where(t.c.pk == pk, t.c.sk == sk)
            ).first()
        return {"pk": pk, "sk": sk, "data": row[0]} if row else None

    def query(
        self, pk: str, sk_gte: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        t = self.table
        stmt = select(t.c.sk, t.c.data).where(t.c.pk == pk)
        if sk_gte is not None:
            stmt = stmt.where(t.c.sk >= sk_gte)
        stmt = stmt.order_by(t.c.sk.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [{"pk": pk, "sk": sk, "data": data} for sk, data in rows]

    def delete(self, pk: str, sk: str) -> None:
        t = self.table
        with self.engine.begin() as conn:
            conn.execute(delete(t).where(t.c.pk == pk, t.c.sk == sk))

    def delete_partition(self, pk: str) -> None:
        t = self.table
        with self.engine.begin() as conn:
            conn.execute(delete(t).where(t.c.pk == pk))


class SQLSessionManager(KeyValueSessionManager):
    """SQL-backed session manager for Strands Agents (any SQLAlchemy database).

        agent = Agent(session_manager=SQLSessionManager(
            session_id="user-123", url="sqlite:///sessions.db",
        ))
    """

    def __init__(
        self,
        session_id: str,
        *,
        url: Optional[str] = None,
        table_name: str = "strands_sessions",
        engine: Optional[Engine] = None,
        **kwargs: Any,
    ) -> None:
        storage = SQLSessionStorage(url, table_name=table_name, engine=engine)
        super().__init__(session_id=session_id, storage=storage)
