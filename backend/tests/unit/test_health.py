"""Tests for the /health endpoint."""

from fastapi.testclient import TestClient

from app.main import create_app


class TestHealthEndpoint:
    """GET /health returns service status."""

    def test_should_return_200_ok(self) -> None:
        """Health endpoint returns 200 status code."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_should_return_status_ok(self) -> None:
        """Health endpoint returns JSON with status='ok'."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.json() == {"status": "ok"}
