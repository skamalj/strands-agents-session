"""Backend-agnostic Strands session manager over a ``SessionStorage``.

Implements the Strands ``SessionRepository`` (all 8 CRUD methods) in terms of a
small ``SessionStorage`` interface, and mixes in ``RepositorySessionManager`` so
the Strands session lifecycle (message indexing, restore, offsetting, tool-use
repair, change detection) is reused unchanged.

A concrete backend only needs to provide a ``SessionStorage`` — see
``strands_session_dynamodb`` for an example.
"""

import json
import time
from typing import Any, Callable, List, Optional

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

    def __init__(
        self,
        session_id: str,
        storage: SessionStorage,
        *,
        write_mode: str = "immediate",
        max_batch_size: int = 25,
        max_batch_interval: Optional[float] = None,
        flush_on_turn_end: bool = True,
        on_flush: Optional[Callable[[List[dict]], None]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the session manager.

        Args:
            session_id: Session identifier.
            storage: Backend storage implementation.
            write_mode: ``"immediate"`` (default, one write per message) or
                ``"batched"`` (buffer messages and flush in one batched write).
            max_batch_size: In batched mode, flush once this many messages are
                buffered.
            max_batch_interval: In batched mode, also flush when at least this
                many seconds have elapsed since the first buffered message. The
                check is *lazy* — evaluated on each new message, so it does not
                flush while the session is idle. Pair with ``flush_on_turn_end``
                (and ``flush()``) as the durability backstop. ``None`` disables
                the time trigger.
            flush_on_turn_end: In batched mode, flush at each turn boundary
                (``sync_agent``). Recommended; guarantees a turn's messages are
                durable once the turn completes.
            on_flush: Optional callback invoked with the list of records after a
                successful flush. The seam for driving downstream consumers (e.g.
                memory extraction) off a coherent, just-persisted batch.

        Durability trade-off (batched mode): on a crash you lose at most
        ``max_batch_size`` messages, or ``max_batch_interval`` seconds of
        un-flushed writes — whichever is smaller — plus anything since the last
        turn boundary when ``flush_on_turn_end`` is set.
        """
        self.storage = storage
        self._write_mode = write_mode
        self._max_batch_size = max_batch_size
        self._max_batch_interval = max_batch_interval
        self._flush_on_turn_end = flush_on_turn_end
        self._on_flush = on_flush
        self._buffer: List[dict] = []
        self._buffer_started: Optional[float] = None
        super().__init__(session_id=session_id, session_repository=self)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record(pk: str, sk: str, payload: dict) -> dict:
        return {"pk": pk, "sk": sk, "data": json.dumps(payload)}

    # ------------------------------------------------------------------
    # write buffering (batched mode)
    # ------------------------------------------------------------------

    def _should_flush(self) -> bool:
        if len(self._buffer) >= self._max_batch_size:
            return True
        if (
            self._max_batch_interval is not None
            and self._buffer_started is not None
            and time.monotonic() - self._buffer_started >= self._max_batch_interval
        ):
            return True
        return False

    def flush(self) -> None:
        """Write any buffered messages via a single batched storage call.

        A no-op when the buffer is empty. On success the ``on_flush`` callback
        (if any) receives the flushed records. If the batched write raises, the
        buffer is left intact so the caller can retry.
        """
        if not self._buffer:
            return
        records = list(self._buffer)
        self.storage.put_batch(records)  # may raise; buffer untouched until success
        self._buffer.clear()
        self._buffer_started = None
        if self._on_flush is not None:
            self._on_flush(records)

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
        record = self._record(
            messages_pk(session_id, agent_id),
            message_sk(session_message.message_id),
            session_message.to_dict(),
        )
        if self._write_mode != "batched":
            self.storage.put(record)
            return
        # Batched mode: buffer and flush on size / lazy-time triggers.
        self._buffer.append(record)
        if self._buffer_started is None:
            self._buffer_started = time.monotonic()
        if self._should_flush():
            self.flush()

    def read_message(
        self, session_id: str, agent_id: str, message_id: int, **kwargs: Any
    ) -> Optional[SessionMessage]:
        self.flush()  # ensure buffered writes are visible before reading
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
        self.flush()  # ensure buffered writes are visible before reading
        records = self.storage.query(
            messages_pk(session_id, agent_id), sk_gte=message_sk(offset), limit=limit
        )
        return [SessionMessage.from_dict(json.loads(r["data"])) for r in records]

    # ------------------------------------------------------------------
    # lifecycle overrides for batching
    # ------------------------------------------------------------------

    def sync_agent(self, agent: Any, **kwargs: Any) -> None:
        """Turn boundary: flush buffered messages (if enabled) before syncing
        the agent record, so a completed turn is durable."""
        if self._flush_on_turn_end:
            self.flush()
        return super().sync_agent(agent, **kwargs)

    def delete_session(self, session_id: str, **kwargs: Any) -> None:
        # Drop any pending buffered writes for this (single-session) manager,
        # then delete — avoids re-materialising deleted messages on a later flush.
        self._buffer.clear()
        self._buffer_started = None
        pk = session_pk(session_id)
        items = self.storage.query(pk)
        agent_ids = [agent_id_from_sk(i["sk"]) for i in items if i["sk"].startswith("AGENT#")]
        for agent_id in agent_ids:
            self.storage.delete_partition(messages_pk(session_id, agent_id))
        self.storage.delete_partition(pk)
