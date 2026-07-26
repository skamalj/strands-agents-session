"""
End-to-end tests: a real Strands Agent (OpenAI gpt-4o-mini) persisting to real
DynamoDB via DynamoDBSessionManager, then restoring in a fresh manager.

Requires:
  - AWS credentials (AWS_PROFILE / keys) + region
  - OPENAI_API_KEY
"""
import os
import uuid

import pytest

from strands import Agent
from strands.models.openai import OpenAIModel

from strands_session_dynamodb import DynamoDBSessionManager

TABLE = os.environ.get("STRANDS_DDB_TABLE", "strands_sessions_test")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")


def make_model():
    return OpenAIModel(
        client_args={"api_key": OPENAI_API_KEY},
        model_id="gpt-4o-mini",
        params={"temperature": 0},
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

    # First manager/agent: introduce a fact.
    m1 = DynamoDBSessionManager(session_id=session_id, table_name=TABLE)
    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=m1)
    a1("Hi, my name is Kamal and I live in Pune.")

    # Fresh manager + agent bound to the SAME session — must restore history.
    m2 = DynamoDBSessionManager(session_id=session_id, table_name=TABLE)
    a2 = Agent(model=make_model(), agent_id="assistant", session_manager=m2)
    reply = text_of(a2("What is my name?"))

    assert "kamal" in reply.lower(), f"expected restored recall of 'kamal', got: {reply}"


def test_messages_written_to_repository():
    session_id = f"llm-{uuid.uuid4()}"
    m1 = DynamoDBSessionManager(session_id=session_id, table_name=TABLE)
    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=m1)
    a1("Say hello in one word.")

    # user turn + assistant turn should both be persisted, in order
    msgs = m1.list_messages(session_id, "assistant")
    assert len(msgs) >= 2
    assert [mm.message_id for mm in msgs] == sorted(mm.message_id for mm in msgs)
    assert msgs[0].message["role"] == "user"


def test_agent_record_persisted():
    session_id = f"llm-{uuid.uuid4()}"
    m1 = DynamoDBSessionManager(session_id=session_id, table_name=TABLE)
    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=m1)
    a1("Hello there.")

    # The agent record (state + conversation-manager state) must be persisted.
    got = m1.read_agent(session_id, "assistant")
    assert got is not None
    assert got.agent_id == "assistant"
    assert isinstance(got.conversation_manager_state, dict)
