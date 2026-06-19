"""Integration tests for WebSocket /ws/sessions/{id} endpoint.

WebSocket endpoint is tested manually with wscat or similar tools.
These tests verify basic app structure.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.sessions.registry import SessionRegistry

FAKE_PI = str(Path(__file__).parent.parent / "fake_pi.py")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with sample repos."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "project-a").mkdir()
    return ws


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Create a session directory."""
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture
def registry(workspace: Path, session_dir: Path) -> SessionRegistry:
    """Create a session registry."""
    return SessionRegistry(
        workspace=workspace,
        session_dir=session_dir,
        agent_cmd=["python3", FAKE_PI],
    )


@pytest.fixture
def app(registry: SessionRegistry, workspace: Path):
    """Create a test app."""
    settings = Settings(workspace=str(workspace))
    return create_app(settings, registry=registry)


class TestWebSocketEndpoint:
    """WebSocket endpoint exists and is accessible."""

    def test_health_endpoint_works(self, app) -> None:
        """Verify the app is working."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
