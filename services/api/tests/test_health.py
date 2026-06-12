from curb_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "service": "curb-api"}


def test_hello_responds() -> None:
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json()["message"] == "curb is alive"
