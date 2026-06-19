"""Integration tests for GET /repos endpoint."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with sample repos."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "project-a").mkdir()
    (ws / "project-b").mkdir()
    (ws / "utils").mkdir()
    # Create a file (should be ignored)
    (ws / "README.md").write_text("not a repo")
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    """Create a test client with the workspace configured."""
    settings = Settings(workspace=str(workspace))
    app = create_app(settings)
    return TestClient(app)


class TestReposEndpoint:
    """GET /repos lists repository directories in workspace."""

    def test_should_return_200(self, client: TestClient) -> None:
        """Endpoint returns 200 status."""
        response = client.get("/repos")
        assert response.status_code == 200

    def test_should_list_subdirectories(self, client: TestClient) -> None:
        """Returns only subdirectories, not files."""
        data = client.get("/repos").json()
        assert "repos" in data
        repos = data["repos"]
        assert "project-a" in repos
        assert "project-b" in repos
        assert "utils" in repos

    def test_should_not_include_files(self, client: TestClient) -> None:
        """Files like README.md are not included."""
        data = client.get("/repos").json()
        repos = data["repos"]
        assert "README.md" not in repos

    def test_should_return_sorted_list(self, client: TestClient) -> None:
        """Repos are returned in sorted order."""
        data = client.get("/repos").json()
        repos = data["repos"]
        assert repos == sorted(repos)

    def test_should_return_empty_list_for_empty_workspace(
        self, tmp_path: Path
    ) -> None:
        """Empty workspace returns empty list."""
        ws = tmp_path / "empty"
        ws.mkdir()
        settings = Settings(workspace=str(ws))
        app = create_app(settings)
        client = TestClient(app)

        data = client.get("/repos").json()
        assert data["repos"] == []
