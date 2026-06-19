"""Integration tests for /sessions REST endpoints.

Tests verify:
- GET /sessions — list live and cold sessions
- POST /sessions — spawn new session
- POST /sessions/{id}/terminate — terminate a live session

Uses httpx.AsyncClient + pytest-asyncio to avoid event loop mismatch
between TestClient (which runs in a separate thread) and subprocess operations.
"""

from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

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
    (ws / "project-b").mkdir()
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


class TestListSessions:
    """GET /sessions lists live and cold sessions."""

    @pytest.mark.asyncio
    async def test_should_return_200(self, app) -> None:
        """Endpoint returns 200 status."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/sessions")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_should_return_empty_lists_initially(self, app) -> None:
        """Returns empty live and cold lists when no sessions exist."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            data = (await client.get("/sessions")).json()
            assert data == {"live": [], "cold": []}

    @pytest.mark.asyncio
    async def test_should_list_spawned_session(self, app) -> None:
        """After spawning, session appears in live list."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Spawn a session
            resp = await client.post("/sessions", json={"repo": "project-a"})
            assert resp.status_code == 200
            session_id = resp.json()["session_id"]

            # List sessions
            data = (await client.get("/sessions")).json()
            assert len(data["live"]) == 1
            assert data["live"][0]["session_id"] == session_id

            # Cleanup
            await client.post(f"/sessions/{session_id}/terminate")


class TestSpawnSession:
    """POST /sessions spawns a new agent session."""

    @pytest.mark.asyncio
    async def test_should_return_200(self, app) -> None:
        """Endpoint returns 200 status."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={"repo": "project-a"})
            assert resp.status_code == 200
            session_id = resp.json()["session_id"]
            await client.post(f"/sessions/{session_id}/terminate")

    @pytest.mark.asyncio
    async def test_should_return_session_id(self, app) -> None:
        """Response includes session_id."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={"repo": "project-a"})
            data = resp.json()
            assert "session_id" in data
            assert data["session_id"] is not None
            await client.post(f"/sessions/{data['session_id']}/terminate")

    @pytest.mark.asyncio
    async def test_should_set_name(self, app) -> None:
        """Optional name is accepted."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={"repo": "project-a", "name": "my-feature"})
            assert resp.status_code == 200
            session_id = resp.json()["session_id"]
            await client.post(f"/sessions/{session_id}/terminate")

    @pytest.mark.asyncio
    async def test_should_reject_missing_repo(self, app) -> None:
        """Returns 422 when repo is missing."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={})
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_should_reject_nonexistent_repo(self, app) -> None:
        """Returns 404 when repo doesn't exist."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={"repo": "nonexistent"})
            assert resp.status_code == 404


class TestTerminateSession:
    """POST /sessions/{id}/terminate stops a live session."""

    @pytest.mark.asyncio
    async def test_should_return_200(self, app) -> None:
        """Terminating a live session returns 200."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={"repo": "project-a"})
            session_id = resp.json()["session_id"]

            resp = await client.post(f"/sessions/{session_id}/terminate")
            assert resp.status_code == 200
            assert resp.json()["status"] == "terminated"

    @pytest.mark.asyncio
    async def test_should_return_404_for_missing(self, app) -> None:
        """Terminating a non-existent session returns 404."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions/nonexistent/terminate")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_should_remove_from_live_list(self, app) -> None:
        """After termination, session is not in live list."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/sessions", json={"repo": "project-a"})
            session_id = resp.json()["session_id"]

            await client.post(f"/sessions/{session_id}/terminate")

            data = (await client.get("/sessions")).json()
            live_ids = [s["session_id"] for s in data["live"]]
            assert session_id not in live_ids
