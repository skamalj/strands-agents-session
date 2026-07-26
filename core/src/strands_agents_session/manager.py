"""Backend-agnostic Strands session manager over a ``SessionStorage``.

Implements the Strands ``SessionRepository`` (all 8 CRUD methods) in terms of a
small ``SessionStorage`` interface, and mixes in ``RepositorySessionManager`` so
the Strands session lifecycle (message indexing, restore, offsetting, tool-use
repair, change detection) is reused unchanged.

A concrete backend only needs to provide a ``SessionStorage`` — see
``strands_session_dynamodb`` for an example.
"""

import json
from typing import Any, List, Optional

from strands.session.repository_session_manager import RepositorySessionManager
from strands.session.session_repository import SessionRepository
from strands.types.exceptions import SessionException
from strands.types.session import Session, SessionAgent, SessionMessage

from .keys import (
    SESSION_SK,
    agent_id_from_sk,
    agent_sk,
    message_sk,
    messages_pk,
    session_pk,
)
from .storage import SessionStorage


class KeyValueSessionManager(RepositorySessionManager, SessionRepository):
    """Strands session manager backed by any ``SessionStorage`` implementation."""

    def __init__(self, session_id: str, storage: SessionStorage, **kwargs: Any) -> None:
        self.storage = storage
        super().__init__(session_id=session_id, session_repository=self)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record(pk: str, sk: str, payload: dict) -> dict:
        return {"pk": pk, "sk": sk, "data": json.dumps(payload)}

    # ------------------------------------------------------------------
    # sessions
    # ------------------------------------------------------------------

    def create_session(self, session: Session, **kwargs: Any) -> Session:
        pk = session_pk(session.session_id)
        if self.storage.get(pk, SESSION_SK) is not None:
            raise SessionException(f"Session {session.session_id} already exists")
        self.storage.put(self._record(pk, SESSION_SK, session.to_dict()))
        return session

    def read_session(self, session_id: str, **kwargs: Any) -> Optional[Session]:
        rec = self.storage.get(session_pk(session_id), SESSION_SK)
        if rec is None:
            return None
        return Session.from_dict(json.loads(rec["data"]))

    def delete_session(self, session_id: str, **kwargs: Any) -> None:
        pk = session_pk(session_id)
        items = self.storage.query(pk)
        agent_ids = [agent_id_from_sk(i["sk"]) for i in items if i["sk"].startswith("AGENT#")]
        for agent_id in agent_ids:
            self.storage.delete_partition(messages_pk(session_id, agent_id))
        self.storage.delete_partition(pk)

    # ------------------------------------------------------------------
    # agents
    # ------------------------------------------------------------------

    def create_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        self.storage.put(
            self._record(session_pk(session_id), agent_sk(session_agent.agent_id), session_agent.to_dict())
        )

    def read_agent(self, session_id: str, agent_id: str, **kwargs: Any) -> Optional[SessionAgent]:
        rec = self.storage.get(session_pk(session_id), agent_sk(agent_id))
        if rec is None:
            return None
        return SessionAgent.from_dict(json.loads(rec["data"]))

    def update_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        previous = self.read_agent(session_id, session_agent.agent_id)
        if previous is None:
            raise SessionException(
                f"Agent {session_agent.agent_id} in session {session_id} does not exist"
            )
        session_agent.created_at = previous.created_at  # preserve creation timestamp
        self.storage.put(
            self._record(session_pk(session_id), agent_sk(session_agent.agent_id), session_agent.to_dict())
        )

    # ------------------------------------------------------------------
    # messages
    # ------------------------------------------------------------------

    def create_message(
        self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any
    ) -> None:
        self.storage.put(
            self._record(
                messages_pk(session_id, agent_id),
                message_sk(session_message.message_id),
                session_message.to_dict(),
            )
        )

    def read_message(
        self, session_id: str, agent_id: str, message_id: int, **kwargs: Any
    ) -> Optional[SessionMessage]:
        rec = self.storage.get(messages_pk(session_id, agent_id), message_sk(message_id))
        if rec is None:
            return None
        return SessionMessage.from_dict(json.loads(rec["data"]))

    def update_message(
        self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any
    ) -> None:
        previous = self.read_message(session_id, agent_id, session_message.message_id)
        if previous is None:
            raise SessionException(f"Message {session_message.message_id} does not exist")
        session_message.created_at = previous.created_at
        self.storage.put(
            self._record(
                messages_pk(session_id, agent_id),
                message_sk(session_message.message_id),
                session_message.to_dict(),
            )
        )

    def list_messages(
        self,
        session_id: str,
        agent_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        **kwargs: Any,
    ) -> List[SessionMessage]:
        records = self.storage.query(
            messages_pk(session_id, agent_id), sk_gte=message_sk(offset), limit=limit
        )
        return [SessionMessage.from_dict(json.loads(r["data"])) for r in records]
