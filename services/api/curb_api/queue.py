"""Redis client lifecycle for the API.

Same pattern as the db pool: a tiny holder we init at startup and drain at
shutdown. The worker keeps its own client; we don't share it across processes.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass
class _Holder:
    redis: Redis | None = None


_holder = _Holder()


def init_redis(url: str) -> Redis:
    if _holder.redis is None:
        _holder.redis = Redis.from_url(url)
    return _holder.redis


def get_redis() -> Redis:
    if _holder.redis is None:
        raise RuntimeError("redis not initialised; call init_redis() at startup")
    return _holder.redis


async def close_redis() -> None:
    if _holder.redis is not None:
        await _holder.redis.aclose()
        _holder.redis = None
