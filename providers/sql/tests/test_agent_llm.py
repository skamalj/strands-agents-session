"""
End-to-end test: a real Strands Agent (OpenAI gpt-4o-mini) persisting to SQL
(SQLite by default) via SQLSessionManager, then restoring in a fresh manager.

Requires OPENAI_API_KEY. Override SQL_TEST_URL for Postgres/MySQL.
"""
import os
import uuid

import pytest

from strands import Agent
from strands.models.openai import OpenAIModel

from strands_session_sql import SQLSessionManager

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    override = os.environ.get("SQL_TEST_URL")
    if override:
        return override
    db = tmp_path_factory.mktemp("sql_llm") / "sessions.db"
    return f"sqlite:///{db}"


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


def test_conversation_persists_and_restores_across_managers(url):
    session_id = f"llm-{uuid.uuid4()}"

    a1 = Agent(model=make_model(), agent_id="assistant",
               session_manager=SQLSessionManager(session_id=session_id, url=url))
    a1("Hi, my name is Kamal and I live in Pune.")

    a2 = Agent(model=make_model(), agent_id="assistant",
               session_manager=SQLSessionManager(session_id=session_id, url=url))
    reply = text_of(a2("What is my name?"))
    assert "kamal" in reply.lower(), f"expected restored recall of 'kamal', got: {reply}"


def test_messages_written_to_repository(url):
    session_id = f"llm-{uuid.uuid4()}"
    m1 = SQLSessionManager(session_id=session_id, url=url)
    a1 = Agent(model=make_model(), agent_id="assistant", session_manager=m1)
    a1("Say hello in one word.")

    msgs = m1.list_messages(session_id, "assistant")
    assert len(msgs) >= 2
    assert [mm.message_id for mm in msgs] == sorted(mm.message_id for mm in msgs)
    assert msgs[0].message["role"] == "user"
