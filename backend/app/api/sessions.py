"""/sessions REST endpoints.

- GET  /sessions                    — list live and cold sessions
- POST /sessions                    — spawn new session
- POST /sessions/{id}/terminate     — terminate a live session
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api import get_settings
from app.config import Settings
from app.sessions.cold import scan_cold_sessions
from app.sessions.registry import SessionRegistry

# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class SpawnRequest(BaseModel):
    """Request body for POST /sessions."""

    repo: str
    name: str | None = None


class SessionInfo(BaseModel):
    """Session summary for list endpoints."""

    session_id: str
    repo: str | None
    name: str | None = None
    is_live: bool = True


class SessionsResponse(BaseModel):
    """Response for GET /sessions."""

    live: list[SessionInfo]
    cold: list[SessionInfo]


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def get_registry(request: Request) -> SessionRegistry:
    """Dependency to get the SessionRegistry from app state."""
    registry = request.app.state.registry
    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


def create_sessions_router() -> APIRouter:
    """Create the /sessions router."""
    router = APIRouter(tags=["sessions"])

    @router.get("/sessions")
    async def list_sessions(
        registry: SessionRegistry = Depends(get_registry),
        settings: Settings = Depends(get_settings),
    ) -> SessionsResponse:
        """List all live and cold sessions.

        Returns:
            JSON with 'live' and 'cold' session lists.
        """
        # Live sessions from registry
        live = [
            SessionInfo(
                session_id=s.session_id,
                repo=s.repo,
                name=s.name,
                is_live=True,
            )
            for s in registry.list_live()
        ]

        # Cold sessions from disk
        session_dir = settings.workspace / ".pi" / "agent" / "sessions"
        cold_sessions = scan_cold_sessions(session_dir)

        # Filter out sessions that are already live
        live_ids = {s.session_id for s in registry.list_live()}
        cold = [
            SessionInfo(
                session_id=s.session_id,
                repo=s.repo,
                is_live=False,
            )
            for s in cold_sessions
            if s.session_id not in live_ids
        ]

        return SessionsResponse(live=live, cold=cold)

    @router.post("/sessions")
    async def spawn_session(
        req: SpawnRequest,
        registry: SessionRegistry = Depends(get_registry),
    ) -> dict[str, str]:
        """Spawn a new agent session.

        Args:
            req: Request body with 'repo' and optional 'name'.

        Returns:
            JSON with 'session_id'.

        Raises:
            404: If the repository doesn't exist.
        """
        try:
            session = await registry.spawn(repo=req.repo, name=req.name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        return {"session_id": session.session_id}

    @router.post("/sessions/{session_id}/terminate")
    async def terminate_session(
        session_id: str,
        registry: SessionRegistry = Depends(get_registry),
    ) -> dict[str, str]:
        """Terminate a live session.

        Args:
            session_id: The session ID to terminate.

        Returns:
            JSON with status='terminated'.

        Raises:
            404: If the session is not found.
        """
        try:
            await registry.terminate(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found") from None

        return {"status": "terminated"}

    return router
