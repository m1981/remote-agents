"""API routes package."""

from fastapi import Request

from app.config import Settings


def get_settings(request: Request) -> Settings:
    """Dependency to get settings from app state."""
    return request.app.state.settings
