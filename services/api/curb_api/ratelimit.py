"""Per-IP sliding-window rate limit for audit submission.

In-memory on purpose: the API runs as a single process, an audit is
expensive (headless Chromium + LLM calls), and losing the window on
restart is acceptable. BYOK requests get a higher allowance because the
model cost is the caller's, but Chromium time is still ours.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

ANON_LIMIT = 3
BYOK_LIMIT = 20
WINDOW_SECONDS = 3600.0

_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    # Traefik terminates TLS and sets X-Forwarded-For; the first entry is
    # the original client. Direct connections fall back to the socket peer.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(ip: str, *, byok: bool, now: float | None = None) -> float | None:
    """Record a hit and return None if allowed, or seconds until retry."""
    now = time.monotonic() if now is None else now
    limit = BYOK_LIMIT if byok else ANON_LIMIT
    window = _hits[ip]
    while window and now - window[0] >= WINDOW_SECONDS:
        window.popleft()
    if len(window) >= limit:
        return WINDOW_SECONDS - (now - window[0])
    window.append(now)
    return None


def reset() -> None:
    """Test hook."""
    _hits.clear()
