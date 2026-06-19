"""Sidecar file I/O for session-to-repository binding.

pi.dev does not store the working directory (cwd) in its session file.
We need this mapping for UC-3 (Resume Cold Session) to know which repo
to restart the agent in.

Format: single line containing the repo name.
Path: <session_dir>/<session_id>.repo
"""

from pathlib import Path


def write_repo_binding(session_dir: Path, session_id: str, repo: str) -> None:
    """Write the repo binding for a session.

    Args:
        session_dir: Directory containing session files.
        session_id: The pi.dev session ID.
        repo: The repository name (subdirectory of workspace).
    """
    repo_file = session_dir / f"{session_id}.repo"
    repo_file.write_text(repo + "\n")


def read_repo_binding(session_dir: Path, session_id: str) -> str | None:
    """Read the repo binding for a session.

    Args:
        session_dir: Directory containing session files.
        session_id: The pi.dev session ID.

    Returns:
        The repository name, or None if not found or empty.
    """
    repo_file = session_dir / f"{session_id}.repo"
    if not repo_file.exists():
        return None

    content = repo_file.read_text().strip()
    return content if content else None
