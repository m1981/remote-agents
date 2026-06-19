"""GET /repos — list repositories in workspace."""

from fastapi import APIRouter, Depends

from app.api import get_settings
from app.config import Settings


def create_repos_router() -> APIRouter:
    """Create the /repos router."""
    router = APIRouter(tags=["repos"])

    @router.get("/repos")
    async def list_repos(settings: Settings = Depends(get_settings)) -> dict[str, list[str]]:
        """List repository directories in the workspace.

        Returns immediate subdirectories of the configured workspace path.
        Files are excluded.

        Returns:
            JSON object with 'repos' key containing sorted list of repo names.
        """
        workspace = settings.workspace

        if not workspace.is_dir():
            return {"repos": []}

        repos = [
            item.name
            for item in workspace.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        ]

        return {"repos": sorted(repos)}

    return router
