"""Tests for app.sessions.sidecar — .repo file I/O.

The sidecar file maps a session ID to its bound repository.
Format: single line containing the repo name.
Path: ~/.pi/agent/sessions/<workspace>/<session_id>.repo
"""

from pathlib import Path

from app.sessions.sidecar import read_repo_binding, write_repo_binding


class TestWriteRepoBinding:
    """write_repo_binding creates a .repo file with the repo name."""

    def test_should_create_repo_file(self, tmp_path: Path) -> None:
        """Writing creates <session_id>.repo in session_dir."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        write_repo_binding(session_dir, "sess-001", "my-project")
        repo_file = session_dir / "sess-001.repo"
        assert repo_file.exists()

    def test_should_write_repo_name_as_content(self, tmp_path: Path) -> None:
        """File contains the repo name as a single line."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        write_repo_binding(session_dir, "sess-001", "my-project")
        content = (session_dir / "sess-001.repo").read_text()
        assert content.strip() == "my-project"

    def test_should_overwrite_existing(self, tmp_path: Path) -> None:
        """Writing again overwrites the previous value."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        write_repo_binding(session_dir, "sess-001", "old-repo")
        write_repo_binding(session_dir, "sess-001", "new-repo")
        content = (session_dir / "sess-001.repo").read_text()
        assert content.strip() == "new-repo"


class TestReadRepoBinding:
    """read_repo_binding reads the repo name from a .repo file."""

    def test_should_read_existing_binding(self, tmp_path: Path) -> None:
        """Returns the repo name from an existing .repo file."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        (session_dir / "sess-001.repo").write_text("my-project\n")
        result = read_repo_binding(session_dir, "sess-001")
        assert result == "my-project"

    def test_should_return_none_when_missing(self, tmp_path: Path) -> None:
        """Returns None when .repo file does not exist."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        result = read_repo_binding(session_dir, "sess-001")
        assert result is None

    def test_should_handle_empty_file(self, tmp_path: Path) -> None:
        """Returns None when .repo file is empty."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        (session_dir / "sess-001.repo").write_text("")
        result = read_repo_binding(session_dir, "sess-001")
        assert result is None
