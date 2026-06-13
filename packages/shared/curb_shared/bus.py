"""Redis key + channel conventions shared by api and worker.

The API enqueues jobs and subscribes to per-audit event channels.
The worker BLPOPs the queue and publishes to those channels.

Jobs are JSON-encoded on the wire so the API can attach a per-request BYOK
override (provider + key) that the worker uses for that audit only. The
key is never persisted; it lives only on the Redis queue until the worker
pops it and forgets it after the run.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel

JOB_QUEUE = "curb:jobs"


class Job(BaseModel):
    audit_id: UUID
    byok_provider: str | None = None
    byok_api_key: str | None = None
    byok_model: str | None = None


def serialize_job(job: Job) -> str:
    return job.model_dump_json()


def deserialize_job(raw: str | bytes) -> Job:
    s = raw.decode() if isinstance(raw, bytes) else raw
    data: dict[str, Any] = json.loads(s)
    return Job(**data)


def events_channel(audit_id: UUID) -> str:
    """Pub/sub channel for one audit's progress events."""
    return f"curb:audit:{audit_id}:events"
