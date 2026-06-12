"""Database layer for the API. asyncpg pool + thin query helpers.

Schema lives in sibling .sql files and is applied at startup; we own the
migration tooling rather than pull in Alembic until the schema actually
grows (Phase 3+).
"""

from curb_api.db.pool import close_pool, get_pool, init_pool

__all__ = ["close_pool", "get_pool", "init_pool"]
