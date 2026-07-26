"""
Comprehensive repository tests for MongoDBSessionManager against a real MongoDB.

Deterministic (no LLM): exercises the SessionRepository CRUD surface — sessions,
agents (with agent state), messages, pagination, updates/redaction, isolation.

Requires a reachable MongoDB (default mongodb://127.0.0.1:27017/, override with
MONGO_URI).
"""
import os
import uuid

import pytest

from strands.types.exceptions import SessionException
from strands.types.session import SessionAgent, SessionMessage
from strands_session_mongodb import MongoDBSessionManager

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017/")
DB = os.environ.get("MONGO_TEST_DB", "strands_sessions_test")


def make_manager(session_id=None):
    return MongoDBSessionManager(
        session_id=session_id or f"sess-{uuid.uuid4()}",
        connection_string=MONGO_URI,
        database_name=DB,
    )


def msg(i, role="user", text=None):
    return SessionMessage.from_message(
        {"role": role, "content": [{"text": text or f"m{i}"}]}, i
    )


# sessions ------------------------------------------------------------------

def test_session_created_on_init():
    mgr = make_manager()
    got = mgr.read_session(mgr.session_id)
    assert got is not None and got.session_id == mgr.session_id


def test_create_duplicate_session_raises():
    mgr = make_manager()
    with pytest.raises(SessionException):
        mgr.create_session(mgr.session)


def test_read_missing_session_returns_none():
    assert make_manager().read_session(f"nope-{uuid.uuid4()}") is None


def test_delete_session_removes_everything():
    mgr = make_manager()
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    mgr.create_message(sid, "a1", msg(0))
    mgr.delete_session(sid)
    assert mgr.read_session(sid) is None
    assert mgr.read_agent(sid, "a1") is None
    assert mgr.list_messages(sid, "a1") == []


# agents (+ state) ----------------------------------------------------------

def test_agent_state_round_trip():
    mgr = make_manager()
    mgr.create_agent(mgr.session_id, SessionAgent(
        agent_id="assistant", state={"tier": "gold", "lang": "en"},
        conversation_manager_state={"removed_message_count": 0}))
    got = mgr.read_agent(mgr.session_id, "assistant")
    assert got.state == {"tier": "gold", "lang": "en"}
    assert got.conversation_manager_state == {"removed_message_count": 0}


def test_read_missing_agent_returns_none():
    mgr = make_manager()
    assert mgr.read_agent(mgr.session_id, "ghost") is None


def test_update_agent_preserves_created_at():
    mgr = make_manager()
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={"v": 1}, conversation_manager_state={}))
    created_at = mgr.read_agent(sid, "a1").created_at
    mgr.update_agent(sid, SessionAgent(agent_id="a1", state={"v": 2}, conversation_manager_state={}))
    got = mgr.read_agent(sid, "a1")
    assert got.state == {"v": 2}
    assert got.created_at == created_at


def test_update_missing_agent_raises():
    mgr = make_manager()
    with pytest.raises(SessionException):
        mgr.update_agent(mgr.session_id, SessionAgent(agent_id="x", state={}, conversation_manager_state={}))


# messages + pagination -----------------------------------------------------

def test_message_round_trip():
    mgr = make_manager()
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    mgr.create_message(sid, "a1", msg(0, text="hello"))
    got = mgr.read_message(sid, "a1", 0)
    assert got.message["content"][0]["text"] == "hello"


def test_list_messages_sorted():
    mgr = make_manager()
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    for i in [2, 0, 4, 1, 3]:
        mgr.create_message(sid, "a1", msg(i))
    assert [m.message_id for m in mgr.list_messages(sid, "a1")] == [0, 1, 2, 3, 4]


def test_list_messages_offset_and_limit():
    mgr = make_manager()
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    for i in range(10):
        mgr.create_message(sid, "a1", msg(i))
    assert [m.message_id for m in mgr.list_messages(sid, "a1", offset=2)] == [2, 3, 4, 5, 6, 7, 8, 9]
    assert [m.message_id for m in mgr.list_messages(sid, "a1", limit=3)] == [0, 1, 2]
    assert [m.message_id for m in mgr.list_messages(sid, "a1", offset=3, limit=4)] == [3, 4, 5, 6]


def test_update_message_redaction():
    mgr = make_manager()
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    m = msg(0, text="secret 4271")
    mgr.create_message(sid, "a1", m)
    m.redact_message = {"role": "user", "content": [{"text": "[REDACTED]"}]}
    mgr.update_message(sid, "a1", m)
    got = mgr.read_message(sid, "a1", 0)
    assert got.redact_message["content"][0]["text"] == "[REDACTED]"


def test_sessions_isolated():
    m1 = make_manager()
    m2 = make_manager()
    m1.create_agent(m1.session_id, SessionAgent(agent_id="a", state={"who": "one"}, conversation_manager_state={}))
    m2.create_agent(m2.session_id, SessionAgent(agent_id="a", state={"who": "two"}, conversation_manager_state={}))
    assert m1.read_agent(m1.session_id, "a").state == {"who": "one"}
    assert m2.read_agent(m2.session_id, "a").state == {"who": "two"}
