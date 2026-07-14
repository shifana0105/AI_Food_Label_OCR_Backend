"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_envelope() -> None:
    """GET /api/v1/health should return the standard success envelope."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["message"]
    assert body["data"]["status"] == "healthy"
    assert body["data"]["service"]
    assert body["data"]["version"]


def test_unversioned_health_is_gone() -> None:
    """The legacy unversioned /health route should not exist."""
    response = client.get("/health")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["status_code"] == 404
