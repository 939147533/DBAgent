from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from .models import ResultCacheEntry


@dataclass
class _StoredEntry:
    entry: ResultCacheEntry
    expires_at: float


class ResultCache:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, _StoredEntry] = {}

    def set(self, entry: ResultCacheEntry) -> str:
        self.cleanup()
        query_id = uuid.uuid4().hex
        self._entries[query_id] = _StoredEntry(entry=entry, expires_at=time.time() + self.ttl_seconds)
        return query_id

    def get(self, query_id: str) -> ResultCacheEntry | None:
        self.cleanup()
        stored = self._entries.get(query_id)
        if not stored:
            return None
        return stored.entry

    def cleanup(self) -> None:
        now = time.time()
        expired = [key for key, value in self._entries.items() if value.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)


result_cache = ResultCache()
