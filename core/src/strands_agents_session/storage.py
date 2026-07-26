"""Storage interface for session backends.

A backend implements this small keyed-record interface; the
``KeyValueSessionManager`` builds the full Strands ``SessionRepository`` on top
of it. Records are plain dicts with at least ``pk``, ``sk``, and ``data`` keys
(``data`` is a serialized payload string).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SessionStorage(ABC):
    """Minimal ordered keyed-record store backing a session manager."""

    @abstractmethod
    def put(self, item: Dict[str, Any]) -> None:
        """Insert or overwrite a record. ``item`` has ``pk``, ``sk``, ``data``."""

    @abstractmethod
    def get(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """Return the record for (pk, sk), or None."""

    @abstractmethod
    def query(
        self, pk: str, sk_gte: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return records under ``pk`` ordered by ``sk`` ascending.

        If ``sk_gte`` is given, only records with ``sk >= sk_gte``. If ``limit``
        is given, return at most that many.
        """

    @abstractmethod
    def delete(self, pk: str, sk: str) -> None:
        """Delete the record for (pk, sk) if present."""

    @abstractmethod
    def delete_partition(self, pk: str) -> None:
        """Delete every record under ``pk``."""


class InMemorySessionStorage(SessionStorage):
    """In-memory storage — useful for tests and local development."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def put(self, item: Dict[str, Any]) -> None:
        self._data.setdefault(item["pk"], {})[item["sk"]] = dict(item)

    def get(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        rec = self._data.get(pk, {}).get(sk)
        return dict(rec) if rec is not None else None

    def query(
        self, pk: str, sk_gte: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        partition = self._data.get(pk, {})
        keys = sorted(k for k in partition if sk_gte is None or k >= sk_gte)
        if limit is not None:
            keys = keys[:limit]
        return [dict(partition[k]) for k in keys]

    def delete(self, pk: str, sk: str) -> None:
        self._data.get(pk, {}).pop(sk, None)

    def delete_partition(self, pk: str) -> None:
        self._data.pop(pk, None)
