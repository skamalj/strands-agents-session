"""
End-to-end tests: a real Strands Agent (OpenAI gpt-4o-mini) persisting to a real
MongoDB via MongoDBSessionManager, then restoring in a fresh manager.

Requires:
  - A reachable MongoDB (MONGO_URI, default mongodb://127.0.0.1:27017/)
  - OPENAI_API_KEY
"""
import os
import uuid

import pytest

from strands import Agent
from strands.models.openai import OpenAIModel

from strands_session_mongodb import MongoDBSessionManager

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017/")
DB = os.environ.get("MONGO_TEST_DB", "strands_sessions_test")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")


def make_model():
    return OpenAIModel(
        client_args={"api_key": OPENAI_API_KEY},
        model_id="gpt-4o-mini",
        params={"temperature": 0},
    )


def make_manager(session_id):
    return MongoDBSessionManager(
        session_id=session_id, connection_string=MONGO_URI, database_name=DB
    )


def text_of(result):
    try:
        return " ".join(
            b.get("text", "") for b in result.message["content"] if isinstance(b, dict)
        )
    except Exception:
        return str(result)


def test_conversation_persists_and_restores_across_managers():
    session_id = f"llm-{uuid.uuid4()}"

    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=make_manager(session_id))
    a1("Hi, my name is Kamal and I live in Pune.")

    a2 = Agent(model=make_model(), agent_id="assistant", session_manager=make_manager(session_id))
    reply = text_of(a2("What is my name?"))
    assert "kamal" in reply.lower(), f"expected restored recall of 'kamal', got: {reply}"


def test_messages_written_to_repository():
    session_id = f"llm-{uuid.uuid4()}"
    m1 = make_manager(session_id)
    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=m1)
    a1("Say hello in one word.")

    msgs = m1.list_messages(session_id, "assistant")
    assert len(msgs) >= 2
    assert [mm.message_id for mm in msgs] == sorted(mm.message_id for mm in msgs)
    assert msgs[0].message["role"] == "user"


def test_agent_record_persisted():
    session_id = f"llm-{uuid.uuid4()}"
    m1 = make_manager(session_id)
    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=m1)
    a1("Hello there.")

    got = m1.read_agent(session_id, "assistant")
    assert got is not None
    assert got.agent_id == "assistant"
    assert isinstance(got.conversation_manager_state, dict)
