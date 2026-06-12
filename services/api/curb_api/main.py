"""Curb FastAPI entrypoint.

Phase 0: health check and hello endpoint only. The audit endpoints
(`POST /audits`, `GET /audits/:id`, SSE stream) land in Phase 1.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Curb API", version="0.0.0")


class Health(BaseModel):
    status: str
    service: str


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", service="curb-api")


@app.get("/api/hello")
async def hello() -> dict[str, str]:
    return {"message": "curb is alive"}
