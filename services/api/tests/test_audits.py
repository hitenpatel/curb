"""POST /audits + GET /audits/:id contract tests.

We stub the pool and redis client so the test stays unit-level. Real-DB
exercise happens via the worker tests and the e2e smoke later in Phase 1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from curb_api import db, queue, ratelimit
from curb_api.main import app
from curb_shared import Audit
from fastapi.testclient import TestClient


class _FakePool:
    def __init__(self) -> None:
        self.audits: dict[str, Audit] = {}
        self.samples: list[Audit] = []

    async def fetchrow(self, sql: str, *args: object):  # type: ignore[no-untyped-def]
        if "INSERT INTO audits" in sql:
            url = str(args[0])
            audit = Audit(
                id=uuid4(),
                url=url,
                status="queued",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.audits[str(audit.id)] = audit
            return {
                "id": audit.id,
                "url": audit.url,
                "status": audit.status,
                "created_at": audit.created_at,
                "updated_at": audit.updated_at,
                "error": None,
                "violation_count": 0,
            }
        if "SELECT id, url, status" in sql and "FROM audits" in sql:
            audit = self.audits.get(str(args[0]))
            if audit is None:
                return None
            return {
                "id": audit.id,
                "url": audit.url,
                "status": audit.status,
                "created_at": audit.created_at,
                "updated_at": audit.updated_at,
                "error": audit.error,
                "violation_count": audit.violation_count,
            }
        raise AssertionError(f"unexpected sql: {sql}")

    async def fetch(self, sql: str, *_args: object) -> list[dict[str, object]]:
        if "is_sample" in sql:
            return [
                {
                    "id": a.id,
                    "url": a.url,
                    "status": a.status,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                    "error": a.error,
                    "violation_count": a.violation_count,
                }
                for a in self.samples
            ]
        return []


class _FakeRedis:
    def __init__(self) -> None:
        self.pushed: list[tuple[str, str]] = []

    async def rpush(self, key: str, value: str) -> int:
        self.pushed.append((key, value))
        return len(self.pushed)


@pytest.fixture(autouse=True)
def _fresh_ratelimit() -> None:
    ratelimit.reset()


@pytest.fixture
def pool() -> _FakePool:
    return _FakePool()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, pool: _FakePool) -> TestClient:
    redis = _FakeRedis()
    monkeypatch.setattr(db.pool, "_holder", type(db.pool._holder)(pool=pool))  # type: ignore[arg-type]
    monkeypatch.setattr(queue, "_holder", type(queue._holder)(redis=redis))  # type: ignore[arg-type]
    return TestClient(app)


def test_post_audits_enqueues_and_returns_queued(client: TestClient) -> None:
    response = client.post("/api/audits", json={"url": "https://example.com"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["url"] == "https://example.com/"
    assert body["violation_count"] == 0


def test_post_audits_rejects_bad_url(client: TestClient) -> None:
    response = client.post("/api/audits", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_get_audit_404_when_missing(client: TestClient) -> None:
    response = client.get(f"/api/audits/{uuid4()}")
    assert response.status_code == 404


def test_get_audit_returns_detail_after_post(client: TestClient) -> None:
    post = client.post("/api/audits", json={"url": "https://example.org"})
    audit_id = post.json()["id"]
    response = client.get(f"/api/audits/{audit_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["audit"]["id"] == audit_id
    assert body["violations"] == []


def test_post_audits_rate_limited_after_anon_quota(client: TestClient) -> None:
    for _ in range(ratelimit.ANON_LIMIT):
        assert client.post("/api/audits", json={"url": "https://example.com"}).status_code == 201
    response = client.post("/api/audits", json={"url": "https://example.com"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "sample" in response.json()["detail"]


def test_post_audits_byok_gets_higher_quota(client: TestClient) -> None:
    payload = {
        "url": "https://example.com",
        "model_provider": "google-gla",
        "model_api_key": "test-key",
    }
    for _ in range(ratelimit.ANON_LIMIT + 1):
        assert client.post("/api/audits", json=payload).status_code == 201


def test_get_samples_empty(client: TestClient) -> None:
    response = client.get("/api/audits/samples")
    assert response.status_code == 200
    assert response.json() == []


def test_get_samples_returns_flagged_audits(client: TestClient, pool: _FakePool) -> None:
    pool.samples = [
        Audit(
            id=uuid4(),
            url="https://dequeuniversity.com/demo/mars/",
            status="complete",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    ]
    response = client.get("/api/audits/samples")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["url"] == "https://dequeuniversity.com/demo/mars/"
    assert body[0]["status"] == "complete"
