"""API test fixtures.

Unit tests use TestClient and never actually need Postgres or Redis. We patch
the startup hooks to no-ops on the API package itself.
"""

from __future__ import annotations

import pytest
from curb_api import db, queue
from curb_api import main as api_main


async def _noop_async(*_args: object, **_kwargs: object) -> None:
    return None


def _noop_sync(*_args: object, **_kwargs: object) -> None:
    return None


@pytest.fixture(autouse=True)
def _stub_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op the db + redis init so TestClient doesn't dial real services."""
    monkeypatch.setattr(db, "init_pool", _noop_async)
    monkeypatch.setattr(db, "close_pool", _noop_async)
    monkeypatch.setattr(queue, "init_redis", _noop_sync)
    monkeypatch.setattr(queue, "close_redis", _noop_async)
    # main.py imports the symbols by name, so patch its bindings too.
    monkeypatch.setattr(api_main, "init_pool", _noop_async)
    monkeypatch.setattr(api_main, "close_pool", _noop_async)
    monkeypatch.setattr(api_main, "init_redis", _noop_sync)
    monkeypatch.setattr(api_main, "close_redis", _noop_async)
