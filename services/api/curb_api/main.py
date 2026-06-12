"""Curb FastAPI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from curb_shared.config import load_settings
from fastapi import FastAPI
from pydantic import BaseModel

from curb_api.db import close_pool, init_pool
from curb_api.queue import close_redis, init_redis
from curb_api.routes.audits import router as audits_router


class Health(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    await init_pool(settings.database_url)
    init_redis(settings.redis_url)
    try:
        yield
    finally:
        await close_redis()
        await close_pool()


app = FastAPI(title="Curb API", version="0.1.0", lifespan=lifespan)
app.include_router(audits_router)


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", service="curb-api")


@app.get("/api/hello")
async def hello() -> dict[str, str]:
    return {"message": "curb is alive"}
