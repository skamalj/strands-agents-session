"""Backend-agnostic session management for Strands Agents.

Provides a ``SessionStorage`` interface and a ``KeyValueSessionManager`` that
implements the full Strands ``SessionRepository`` over it, so new storage
backends (DynamoDB, Redis, MongoDB, …) only need to implement a handful of
keyed-record methods.
"""

from . import keys
from .manager import KeyValueSessionManager
from .storage import InMemorySessionStorage, SessionStorage

__all__ = [
    "KeyValueSessionManager",
    "SessionStorage",
    "InMemorySessionStorage",
    "keys",
]
