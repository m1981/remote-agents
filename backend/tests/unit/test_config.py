"""Tests for app.config.Settings."""

from pathlib import Path

from app.config import Settings


class TestSettings:
    """Settings loads configuration from environment variables."""

    def test_should_load_workspace_from_env(self, tmp_path: Path) -> None:
        """Settings.workspace is read from PI_WORKSPACE env var."""
        env_workspace = str(tmp_path / "workspace")
        settings = Settings(workspace=env_workspace)
        assert settings.workspace == Path(env_workspace)

    def test_should_default_host_to_localhost(self, tmp_path: Path) -> None:
        """Settings.host defaults to 127.0.0.1 when not specified."""
        settings = Settings(workspace=str(tmp_path))
        assert settings.host == "127.0.0.1"

    def test_should_load_host_from_env(self, tmp_path: Path) -> None:
        """Settings.host is read from PI_HOST env var."""
        settings = Settings(workspace=str(tmp_path), host="100.64.0.1")
        assert settings.host == "100.64.0.1"

    def test_should_default_port_to_8080(self, tmp_path: Path) -> None:
        """Settings.port defaults to 8080 when not specified."""
        settings = Settings(workspace=str(tmp_path))
        assert settings.port == 8080

    def test_should_load_port_from_env(self, tmp_path: Path) -> None:
        """Settings.port is read from PI_PORT env var."""
        settings = Settings(workspace=str(tmp_path), port=9090)
        assert settings.port == 9090

    def test_should_resolve_workspace_to_absolute(self, tmp_path: Path) -> None:
        """Settings.workspace is always resolved to an absolute Path."""
        settings = Settings(workspace=str(tmp_path))
        assert settings.workspace.is_absolute()
