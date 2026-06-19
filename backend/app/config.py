"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Configuration for the remote-agents backend.

    Values are loaded from environment variables with sensible defaults
    for local development.
    """

    workspace: Path = Field(
        description="Root directory containing all repositories the Agent may operate on."
    )
    host: str = Field(
        default="127.0.0.1",
        description="Bind address. Set to tailnet IP in production.",
    )
    port: int = Field(
        default=8080,
        description="Port to listen on.",
    )

    def model_post_init(self, __context: object) -> None:
        """Resolve workspace to absolute path."""
        self.workspace = self.workspace.resolve()
