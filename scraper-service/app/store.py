"""State owned by the scraper: watched targets and the set of postings already seen.

Redis is the production backend (atomic SADD gives race-free dedup across replicas).
InMemoryStore backs the unit tests and local runs without Redis.
"""

from __future__ import annotations

import json
from typing import Protocol

from redis.asyncio import Redis

from app.models import Target

TARGETS_KEY = "scraper:targets"
SEEN_KEY = "scraper:seen:{target_id}"


class Store(Protocol):
    async def list_targets(self) -> list[Target]: ...
    async def get_target(self, target_id: str) -> Target | None: ...
    async def upsert_target(self, target: Target) -> None: ...
    async def delete_target(self, target_id: str) -> bool: ...
    async def mark_seen(self, target_id: str, key: str) -> bool:
        """Record key as seen. Returns True only the first time a key is seen."""
        ...

    async def forget_seen(self, target_id: str, key: str) -> None: ...
    async def ping(self) -> bool: ...


class RedisStore:
    def __init__(self, redis: Redis):
        self._r = redis

    async def list_targets(self) -> list[Target]:
        raw = await self._r.hgetall(TARGETS_KEY)
        return sorted((Target.model_validate_json(v) for v in raw.values()), key=lambda t: t.id)

    async def get_target(self, target_id: str) -> Target | None:
        raw = await self._r.hget(TARGETS_KEY, target_id)
        return Target.model_validate_json(raw) if raw else None

    async def upsert_target(self, target: Target) -> None:
        await self._r.hset(TARGETS_KEY, target.id, target.model_dump_json())

    async def delete_target(self, target_id: str) -> bool:
        removed = await self._r.hdel(TARGETS_KEY, target_id)
        await self._r.delete(SEEN_KEY.format(target_id=target_id))
        return bool(removed)

    async def mark_seen(self, target_id: str, key: str) -> bool:
        return bool(await self._r.sadd(SEEN_KEY.format(target_id=target_id), key))

    async def forget_seen(self, target_id: str, key: str) -> None:
        await self._r.srem(SEEN_KEY.format(target_id=target_id), key)

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except Exception:
            return False


class InMemoryStore:
    def __init__(self) -> None:
        self._targets: dict[str, str] = {}
        self._seen: dict[str, set[str]] = {}

    async def list_targets(self) -> list[Target]:
        return sorted((Target.model_validate_json(v) for v in self._targets.values()), key=lambda t: t.id)

    async def get_target(self, target_id: str) -> Target | None:
        raw = self._targets.get(target_id)
        return Target.model_validate_json(raw) if raw else None

    async def upsert_target(self, target: Target) -> None:
        self._targets[target.id] = target.model_dump_json()

    async def delete_target(self, target_id: str) -> bool:
        self._seen.pop(target_id, None)
        return self._targets.pop(target_id, None) is not None

    async def mark_seen(self, target_id: str, key: str) -> bool:
        seen = self._seen.setdefault(target_id, set())
        if key in seen:
            return False
        seen.add(key)
        return True

    async def forget_seen(self, target_id: str, key: str) -> None:
        self._seen.get(target_id, set()).discard(key)

    async def ping(self) -> bool:
        return True


async def seed_targets(store: Store, path: str) -> int:
    """Load default targets from JSON on first boot (never overwrites user edits)."""
    if await store.list_targets():
        return 0
    with open(path) as fh:
        targets = [Target.model_validate(t) for t in json.load(fh)]
    for t in targets:
        await store.upsert_target(t)
    return len(targets)
