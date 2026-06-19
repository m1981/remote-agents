"""SessionRegistry — in-memory registry of live agent sessions.

Manages the lifecycle of AgentProcess instances:
- Spawning new sessions bound to repositories
- Tracking live sessions
- Terminating individual or all sessions
- Per-session locking (BR-3: one agent per session ID)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from app.rpc.agent_process import AgentProcess
from app.sessions.sidecar import write_repo_binding

logger = logging.getLogger(__name__)


@dataclass
class LiveSession:
    """A live session with its agent process and metadata."""

    session_id: str
    repo: str
    agent: AgentProcess
    name: str | None = None

    @property
    def is_alive(self) -> bool:
        """Whether the agent process is still running."""
        return self.agent.is_alive


class SessionRegistry:
    """In-memory registry of live agent sessions.

    Enforces BR-3: one agent per session ID via per-session locks.
    """

    def __init__(
        self,
        workspace: Path,
        session_dir: Path,
        agent_cmd: list[str],
    ) -> None:
        """Initialize the registry.

        Args:
            workspace: Root directory containing all repositories.
            session_dir: Directory for session files and sidecars.
            agent_cmd: Base command to launch pi (e.g., ["pi", "--mode", "rpc"]).
        """
        self._workspace = workspace
        self._session_dir = session_dir
        self._agent_cmd = agent_cmd
        self._sessions: dict[str, LiveSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create a lock for a session ID."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def spawn(self, repo: str, name: str | None = None) -> LiveSession:
        """Spawn a new agent session bound to a repository.

        Args:
            repo: Repository name (subdirectory of workspace).
            name: Optional human-readable session name.

        Returns:
            The newly created LiveSession.

        Raises:
            ValueError: If the repository does not exist.
        """
        repo_path = self._workspace / repo
        if not repo_path.is_dir():
            raise ValueError(f"Repository not found: {repo}")

        # Ensure session directory exists
        self._session_dir.mkdir(parents=True, exist_ok=True)

        # Start agent process (detached — registry manages lifetime)
        agent = await AgentProcess.start_detached(
            self._agent_cmd,
            cwd=str(repo_path),
        )

        session_id = agent.session_id
        if not session_id:
            await agent.terminate()
            raise RuntimeError("Agent did not provide a session ID")

        # Write sidecar for cold session recovery
        write_repo_binding(self._session_dir, session_id, repo)

        # Register live session
        session = LiveSession(
            session_id=session_id,
            repo=repo,
            agent=agent,
            name=name or agent.session_name,
        )
        self._sessions[session_id] = session

        logger.info(
            "Spawned session %s for repo=%s name=%s",
            session_id,
            repo,
            session.name,
        )
        return session

    def get(self, session_id: str) -> LiveSession | None:
        """Get a live session by ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The LiveSession, or None if not found or not alive.
        """
        session = self._sessions.get(session_id)
        if session and not session.is_alive:
            # Auto-clean dead sessions
            self._sessions.pop(session_id, None)
            return None
        return session

    def list_live(self) -> list[LiveSession]:
        """List all live sessions.

        Returns:
            List of currently live sessions.
        """
        # Clean dead sessions
        dead = [sid for sid, s in self._sessions.items() if not s.is_alive]
        for sid in dead:
            self._sessions.pop(sid, None)
        return list(self._sessions.values())

    async def terminate(self, session_id: str) -> None:
        """Terminate a live session.

        Args:
            session_id: The session ID to terminate.

        Raises:
            KeyError: If the session is not found.
        """
        session = self._sessions.pop(session_id, None)
        if not session:
            raise KeyError(f"Session not found: {session_id}")

        logger.info("Terminating session %s", session_id)
        await session.agent.terminate()
        self._locks.pop(session_id, None)

    async def terminate_all(self) -> None:
        """Terminate all live sessions."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            try:
                await self.terminate(session_id)
            except Exception as e:
                logger.error("Failed to terminate session %s: %s", session_id, e)
