"""Cold session scanner — reads session metadata from JSONL files.

Cold sessions are sessions that exist on disk but have no running agent process.
This module scans the session directory to enumerate them for UC-5 (Survey Sessions).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.sessions.sidecar import read_repo_binding

logger = logging.getLogger(__name__)


@dataclass
class ColdSession:
    """Metadata for a cold (not-running) session."""

    session_id: str
    repo: str | None
    last_modified: float
    message_count: int = 0


def scan_cold_sessions(session_dir: Path) -> list[ColdSession]:
    """Scan a session directory for cold sessions.

    Reads JSONL files and extracts session metadata. Malformed files
    are skipped with a warning.

    Args:
        session_dir: Path to the session directory containing JSONL files.

    Returns:
        List of ColdSession metadata objects.
    """
    if not session_dir.is_dir():
        return []

    sessions: list[ColdSession] = []

    for filepath in sorted(session_dir.glob("*.jsonl")):
        session_id = filepath.stem

        try:
            # Read first line to get session metadata
            with filepath.open("r") as f:
                first_line = f.readline().strip()

            if not first_line:
                logger.warning("Empty session file: %s", filepath)
                continue

            # Validate JSON by parsing first line
            json.loads(first_line)

            # Read repo binding from sidecar
            repo = read_repo_binding(session_dir, session_id)

            # Get file modification time
            last_modified = filepath.stat().st_mtime

            # Count messages (lines in file)
            message_count = _count_lines(filepath)

            sessions.append(ColdSession(
                session_id=session_id,
                repo=repo,
                last_modified=last_modified,
                message_count=message_count,
            ))

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Skipping malformed session file %s: %s", filepath, e)
            continue

    return sessions


def _count_lines(filepath: Path) -> int:
    """Count the number of lines in a file efficiently."""
    try:
        with filepath.open("rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
