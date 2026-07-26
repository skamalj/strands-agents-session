"""Key construction helpers shared across session storage backends.

Single-logical-table layout (keys are opaque strings, so any KV/range store fits):

    Session : pk = "SESSION#<session_id>"                  sk = "META"
    Agent   : pk = "SESSION#<session_id>"                  sk = "AGENT#<agent_id>"
    Message : pk = "SESSION#<session_id>#AGENT#<agent_id>" sk = "MSG#<zero-padded id>"

Message sort keys are zero-padded so that lexical ordering matches numeric
ordering — making ``list_messages(offset, limit)`` a simple ordered range scan,
matching the ``removed_message_count`` offset semantics Strands relies on.
"""

# Width for zero-padding message ids so lexical sort == numeric sort.
MESSAGE_ID_WIDTH = 20

SESSION_SK = "META"


def session_pk(session_id: str) -> str:
    return f"SESSION#{session_id}"


def agent_sk(agent_id: str) -> str:
    return f"AGENT#{agent_id}"


def agent_id_from_sk(sk: str) -> str:
    return sk.split("AGENT#", 1)[1]


def messages_pk(session_id: str, agent_id: str) -> str:
    return f"SESSION#{session_id}#AGENT#{agent_id}"


def message_sk(message_id: int) -> str:
    return f"MSG#{int(message_id):0{MESSAGE_ID_WIDTH}d}"
