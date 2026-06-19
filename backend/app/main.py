"""FastAPI application factory."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.repos import create_repos_router
from app.api.sessions import create_sessions_router
from app.api.ws import create_ws_router
from app.config import Settings
from app.sessions.registry import SessionRegistry


def create_app(
    settings: Settings | None = None,
    registry: SessionRegistry | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Application settings. If None, loaded from environment.
        registry: Session registry. If None, created from settings.

    Returns:
        Configured FastAPI instance with all routes registered.
    """
    if settings is None:
        workspace = os.environ.get("PI_WORKSPACE", "/tmp/workspace")
        settings = Settings(workspace=workspace)

    if registry is None:
        # Create registry from settings
        session_dir = Path.home() / ".pi" / "agent" / "sessions"
        registry = SessionRegistry(
            workspace=settings.workspace,
            session_dir=session_dir,
            agent_cmd=["pi", "--mode", "rpc"],
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Application lifespan — startup and shutdown."""
        yield
        # Shutdown: terminate all live sessions
        if registry:
            await registry.terminate_all()

    app = FastAPI(
        title="remote-agents",
        description="Remote control for pi.dev coding agent sessions.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store dependencies in app state
    app.state.settings = settings
    app.state.registry = registry

    # Register routers
    app.include_router(create_repos_router())
    app.include_router(create_sessions_router())
    app.include_router(create_ws_router())

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            JSON object with status='ok'.
        """
        return {"status": "ok"}

    return app


# Default app for uvicorn
app = create_app()
