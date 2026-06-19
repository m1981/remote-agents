"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory with sample repos."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # Create sample repository directories
    (workspace / "project-a").mkdir()
    (workspace / "project-b").mkdir()
    return workspace
