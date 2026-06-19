"""Tests for app.sessions.cold — JSONL directory scanner.

Cold sessions are sessions that exist on disk but have no running agent process.
This module scans the session directory and parses JSONL headers to extract
session metadata.
"""

import json
from pathlib import Path

from app.sessions.cold import scan_cold_sessions


def _create_session_file(
    session_dir: Path,
    session_id: str,
    session_name: str | None = None,
    messages: list[dict] | None = None,
) -> Path:
    """Create a minimal JSONL session file for testing."""
    filepath = session_dir / f"{session_id}.jsonl"

    # Write session header entries
    entries = []

    # Add session start entry
    entries.append({
        "type": "session_start",
        "sessionId": session_id,
        "timestamp": 1700000000000,
    })

    # Add messages if provided
    if messages:
        entries.extend(messages)

    with filepath.open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return filepath


class TestScanColdSessions:
    """scan_cold_sessions reads session metadata from JSONL files."""

    def test_should_find_sessions_in_directory(self, tmp_path: Path) -> None:
        """Scanner finds JSONL files in the session directory."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        _create_session_file(session_dir, "sess-001")
        _create_session_file(session_dir, "sess-002")

        sessions = scan_cold_sessions(session_dir)
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert "sess-001" in ids
        assert "sess-002" in ids

    def test_should_extract_session_id(self, tmp_path: Path) -> None:
        """Session ID is extracted from the filename."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        _create_session_file(session_dir, "abc-123")

        sessions = scan_cold_sessions(session_dir)
        assert len(sessions) == 1
        assert sessions[0].session_id == "abc-123"

    def test_should_return_empty_for_empty_directory(self, tmp_path: Path) -> None:
        """Empty session directory returns empty list."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        sessions = scan_cold_sessions(session_dir)
        assert sessions == []

    def test_should_return_empty_for_missing_directory(self, tmp_path: Path) -> None:
        """Missing session directory returns empty list."""
        session_dir = tmp_path / "nonexistent"

        sessions = scan_cold_sessions(session_dir)
        assert sessions == []

    def test_should_ignore_non_jsonl_files(self, tmp_path: Path) -> None:
        """Non-JSONL files are ignored."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        _create_session_file(session_dir, "sess-001")
        # Create a .repo sidecar file
        (session_dir / "sess-001.repo").write_text("my-project")
        # Create a random file
        (session_dir / "notes.txt").write_text("not a session")

        sessions = scan_cold_sessions(session_dir)
        assert len(sessions) == 1
        assert sessions[0].session_id == "sess-001"

    def test_should_read_repo_binding(self, tmp_path: Path) -> None:
        """Repo binding is read from sidecar .repo file."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        _create_session_file(session_dir, "sess-001")
        (session_dir / "sess-001.repo").write_text("my-project\n")

        sessions = scan_cold_sessions(session_dir)
        assert len(sessions) == 1
        assert sessions[0].repo == "my-project"

    def test_should_handle_missing_repo_binding(self, tmp_path: Path) -> None:
        """Missing .repo file results in None repo."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        _create_session_file(session_dir, "sess-001")

        sessions = scan_cold_sessions(session_dir)
        assert len(sessions) == 1
        assert sessions[0].repo is None

    def test_should_get_last_modified_time(self, tmp_path: Path) -> None:
        """Last modified time is from the file's mtime."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        _create_session_file(session_dir, "sess-001")

        sessions = scan_cold_sessions(session_dir)
        assert len(sessions) == 1
        assert sessions[0].last_modified > 0

    def test_should_skip_malformed_jsonl(self, tmp_path: Path) -> None:
        """Malformed JSONL files are skipped gracefully."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        # Create a valid session
        _create_session_file(session_dir, "sess-good")
        # Create a malformed session file
        bad_file = session_dir / "sess-bad.jsonl"
        bad_file.write_text("not valid json\n")

        sessions = scan_cold_sessions(session_dir)
        # Should still find the good session
        assert len(sessions) >= 1
        ids = {s.session_id for s in sessions}
        assert "sess-good" in ids
