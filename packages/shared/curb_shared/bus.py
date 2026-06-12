"""Redis key + channel conventions shared by api and worker.

The API enqueues jobs and subscribes to per-audit event channels.
The worker BLPOPs the queue and publishes to those channels.
"""

from __future__ import annotations

from uuid import UUID

JOB_QUEUE = "curb:jobs"


def events_channel(audit_id: UUID) -> str:
    """Pub/sub channel for one audit's progress events."""
    return f"curb:audit:{audit_id}:events"
