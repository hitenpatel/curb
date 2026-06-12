"""Asyncpg pool management. Init at startup, close at shutdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import asyncpg

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


@dataclass
class _Holder:
    pool: asyncpg.Pool | None = None


_holder = _Holder()


async def init_pool(dsn: str) -> asyncpg.Pool:
    """Create the pool and apply the schema. Safe to call once at startup."""
    if _holder.pool is not None:
        return _holder.pool
    _holder.pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    async with _holder.pool.acquire() as conn:
        await conn.execute(_SCHEMA)
    return _holder.pool


def get_pool() -> asyncpg.Pool:
    if _holder.pool is None:
        raise RuntimeError("db pool not initialised; call init_pool() at startup")
    return _holder.pool


async def close_pool() -> None:
    if _holder.pool is not None:
        await _holder.pool.close()
        _holder.pool = None
