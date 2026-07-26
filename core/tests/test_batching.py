"""
Offline tests for batched write mode on KeyValueSessionManager (InMemory backend).

Covers the size trigger, the lazy time trigger, turn-boundary/explicit flush,
the on_flush seam, flush-before-read consistency, and equivalence to immediate
mode. Deterministic, no cloud.
"""
import time
import uuid

from strands.types.session import SessionMessage
from strands_agents_session import InMemorySessionStorage, KeyValueSessionManager
from strands_agents_session.keys import message_sk, messages_pk


def msg(i, text=None):
    return SessionMessage.from_message(
        {"role": "user", "content": [{"text": text or f"m{i}"}]}, i
    )


def make(storage=None, **cfg):
    return KeyValueSessionManager(
        session_id=f"sess-{uuid.uuid4()}",
        storage=storage or InMemorySessionStorage(),
        **cfg,
    )


def stored_count(mgr, agent_id="a1"):
    """Read storage directly (bypasses the manager's flush) to see durable state."""
    return len(mgr.storage.query(messages_pk(mgr.session_id, agent_id)))


# --- immediate mode (default) ---------------------------------------------

def test_immediate_writes_through():
    mgr = make()  # default write_mode="immediate"
    mgr.create_message(mgr.session_id, "a1", msg(0))
    assert stored_count(mgr) == 1


# --- batched: size trigger -------------------------------------------------

def test_batched_buffers_until_size():
    mgr = make(write_mode="batched", max_batch_size=3)
    mgr.create_message(mgr.session_id, "a1", msg(0))
    mgr.create_message(mgr.session_id, "a1", msg(1))
    assert stored_count(mgr) == 0          # buffered, not yet durable
    mgr.create_message(mgr.session_id, "a1", msg(2))
    assert stored_count(mgr) == 3          # size hit -> flushed


# --- batched: lazy time trigger -------------------------------------------

def test_batched_lazy_time_flush():
    mgr = make(write_mode="batched", max_batch_size=100, max_batch_interval=0.05)
    mgr.create_message(mgr.session_id, "a1", msg(0))
    assert stored_count(mgr) == 0
    time.sleep(0.06)
    mgr.create_message(mgr.session_id, "a1", msg(1))  # append re-checks time -> flush
    assert stored_count(mgr) == 2


def test_time_trigger_is_lazy_not_idle():
    # With only a time trigger and no further writes, the buffer stays until a
    # subsequent write/flush -- lazy by design (no background thread).
    mgr = make(write_mode="batched", max_batch_size=100, max_batch_interval=0.01)
    mgr.create_message(mgr.session_id, "a1", msg(0))
    time.sleep(0.05)
    assert stored_count(mgr) == 0          # idle: not flushed
    mgr.flush()
    assert stored_count(mgr) == 1


# --- explicit flush + on_flush seam ---------------------------------------

def test_explicit_flush_drains():
    mgr = make(write_mode="batched", max_batch_size=100)
    mgr.create_message(mgr.session_id, "a1", msg(0))
    mgr.create_message(mgr.session_id, "a1", msg(1))
    assert stored_count(mgr) == 0
    mgr.flush()
    assert stored_count(mgr) == 2
    mgr.flush()  # no-op on empty buffer


def test_on_flush_callback_receives_batch():
    seen = []
    mgr = make(write_mode="batched", max_batch_size=2, on_flush=lambda recs: seen.append(recs))
    mgr.create_message(mgr.session_id, "a1", msg(0))
    mgr.create_message(mgr.session_id, "a1", msg(1))  # size hit -> flush -> callback
    assert len(seen) == 1
    assert len(seen[0]) == 2
    # the flushed records carry the message keys (the memory-trigger seam)
    assert all("sk" in r and "data" in r for r in seen[0])


# --- read consistency ------------------------------------------------------

def test_flush_before_read():
    mgr = make(write_mode="batched", max_batch_size=100)
    for i in range(3):
        mgr.create_message(mgr.session_id, "a1", msg(i))
    # list_messages flushes first, so buffered writes are visible
    got = mgr.list_messages(mgr.session_id, "a1")
    assert [m.message_id for m in got] == [0, 1, 2]
    assert stored_count(mgr) == 3


# --- equivalence + cleanup -------------------------------------------------

def test_batched_equals_immediate():
    imm = make(write_mode="immediate")
    bat = make(write_mode="batched", max_batch_size=100)
    for i in range(5):
        imm.create_message(imm.session_id, "a1", msg(i, f"same {i}"))
        bat.create_message(bat.session_id, "a1", msg(i, f"same {i}"))
    bat.flush()
    imm_msgs = [m.message["content"][0]["text"] for m in imm.list_messages(imm.session_id, "a1")]
    bat_msgs = [m.message["content"][0]["text"] for m in bat.list_messages(bat.session_id, "a1")]
    assert imm_msgs == bat_msgs == [f"same {i}" for i in range(5)]


def test_delete_session_drops_buffer():
    mgr = make(write_mode="batched", max_batch_size=100)
    mgr.create_message(mgr.session_id, "a1", msg(0))
    mgr.delete_session(mgr.session_id)
    mgr.flush()  # buffer was cleared by delete -> nothing resurrected
    assert stored_count(mgr) == 0
