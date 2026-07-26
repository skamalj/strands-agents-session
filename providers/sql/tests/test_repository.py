"""
Comprehensive repository tests for SQLSessionManager (SQLAlchemy) against SQLite.

Deterministic (no LLM). Uses a shared temp SQLite file so multiple managers see
the same database. Override SQL_TEST_URL to run against Postgres/MySQL.
"""
import os
import uuid

import pytest

from strands.types.exceptions import SessionException
from strands.types.session import SessionAgent, SessionMessage
from strands_session_sql import SQLSessionManager


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    override = os.environ.get("SQL_TEST_URL")
    if override:
        return override
    db = tmp_path_factory.mktemp("sql") / "sessions.db"
    return f"sqlite:///{db}"


def make_manager(url, session_id=None):
    return SQLSessionManager(session_id=session_id or f"sess-{uuid.uuid4()}", url=url)


def msg(i, role="user", text=None):
    return SessionMessage.from_message(
        {"role": role, "content": [{"text": text or f"m{i}"}]}, i
    )


def test_session_created_on_init(url):
    mgr = make_manager(url)
    got = mgr.read_session(mgr.session_id)
    assert got is not None and got.session_id == mgr.session_id


def test_create_duplicate_session_raises(url):
    mgr = make_manager(url)
    with pytest.raises(SessionException):
        mgr.create_session(mgr.session)


def test_read_missing_session_returns_none(url):
    assert make_manager(url).read_session(f"nope-{uuid.uuid4()}") is None


def test_delete_session_removes_everything(url):
    mgr = make_manager(url)
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    mgr.create_message(sid, "a1", msg(0))
    mgr.delete_session(sid)
    assert mgr.read_session(sid) is None
    assert mgr.read_agent(sid, "a1") is None
    assert mgr.list_messages(sid, "a1") == []


def test_agent_state_round_trip(url):
    mgr = make_manager(url)
    mgr.create_agent(mgr.session_id, SessionAgent(
        agent_id="assistant", state={"tier": "gold"},
        conversation_manager_state={"removed_message_count": 0}))
    got = mgr.read_agent(mgr.session_id, "assistant")
    assert got.state == {"tier": "gold"}
    assert got.conversation_manager_state == {"removed_message_count": 0}


def test_update_agent_preserves_created_at(url):
    mgr = make_manager(url)
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={"v": 1}, conversation_manager_state={}))
    created_at = mgr.read_agent(sid, "a1").created_at
    mgr.update_agent(sid, SessionAgent(agent_id="a1", state={"v": 2}, conversation_manager_state={}))
    got = mgr.read_agent(sid, "a1")
    assert got.state == {"v": 2}
    assert got.created_at == created_at


def test_update_missing_agent_raises(url):
    mgr = make_manager(url)
    with pytest.raises(SessionException):
        mgr.update_agent(mgr.session_id, SessionAgent(agent_id="x", state={}, conversation_manager_state={}))


def test_message_round_trip(url):
    mgr = make_manager(url)
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    mgr.create_message(sid, "a1", msg(0, text="hello"))
    got = mgr.read_message(sid, "a1", 0)
    assert got.message["content"][0]["text"] == "hello"


def test_list_messages_sorted(url):
    mgr = make_manager(url)
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    for i in [2, 0, 4, 1, 3]:
        mgr.create_message(sid, "a1", msg(i))
    assert [m.message_id for m in mgr.list_messages(sid, "a1")] == [0, 1, 2, 3, 4]


def test_list_messages_offset_and_limit(url):
    mgr = make_manager(url)
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    for i in range(10):
        mgr.create_message(sid, "a1", msg(i))
    assert [m.message_id for m in mgr.list_messages(sid, "a1", offset=2)] == [2, 3, 4, 5, 6, 7, 8, 9]
    assert [m.message_id for m in mgr.list_messages(sid, "a1", limit=3)] == [0, 1, 2]
    assert [m.message_id for m in mgr.list_messages(sid, "a1", offset=3, limit=4)] == [3, 4, 5, 6]


def test_update_message_redaction(url):
    mgr = make_manager(url)
    sid = mgr.session_id
    mgr.create_agent(sid, SessionAgent(agent_id="a1", state={}, conversation_manager_state={}))
    m = msg(0, text="secret 4271")
    mgr.create_message(sid, "a1", m)
    m.redact_message = {"role": "user", "content": [{"text": "[REDACTED]"}]}
    mgr.update_message(sid, "a1", m)
    got = mgr.read_message(sid, "a1", 0)
    assert got.redact_message["content"][0]["text"] == "[REDACTED]"


def test_sessions_isolated(url):
    m1 = make_manager(url)
    m2 = make_manager(url)
    m1.create_agent(m1.session_id, SessionAgent(agent_id="a", state={"who": "one"}, conversation_manager_state={}))
    m2.create_agent(m2.session_id, SessionAgent(agent_id="a", state={"who": "two"}, conversation_manager_state={}))
    assert m1.read_agent(m1.session_id, "a").state == {"who": "one"}
    assert m2.read_agent(m2.session_id, "a").state == {"who": "two"}
