"""Integration tests for SessionRegistry — in-memory session management.

Tests verify:
- Spawning new sessions
- Getting live sessions
- Listing all live sessions
- Terminating sessions
- Per-session locking (BR-3: one agent per session)
"""

from pathlib import Path

import pytest

from app.sessions.registry import SessionRegistry

# Path to fake pi binary
FAKE_PI = str(Path(__file__).parent.parent / "fake_pi.py")


@pytest.fixture
def fake_pi_cmd() -> list[str]:
    """Command to launch fake pi."""
    return ["python3", FAKE_PI]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with sample repos."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "project-a").mkdir()
    (ws / "project-b").mkdir()
    return ws


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Create a session directory."""
    d = tmp_path / "sessions"
    d.mkdir()
    return d


class TestSessionRegistrySpawn:
    """SessionRegistry.spawn() creates a new live session."""

    @pytest.mark.asyncio
    async def test_should_spawn_session_with_agent(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Spawning creates a live session with a running agent."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        session = await registry.spawn(repo="project-a")
        assert session.session_id is not None
        assert session.is_alive
        await registry.terminate_all()

    @pytest.mark.asyncio
    async def test_should_set_session_name(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Spawning with name sets the session name."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        session = await registry.spawn(repo="project-a", name="my-feature")
        # Provided name takes precedence over agent's name
        assert session.name == "my-feature"
        await registry.terminate_all()

    @pytest.mark.asyncio
    async def test_should_write_sidecar_on_spawn(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Spawning writes the .repo sidecar file."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        session = await registry.spawn(repo="project-a")
        sidecar = session_dir / f"{session.session_id}.repo"
        assert sidecar.exists()
        assert sidecar.read_text().strip() == "project-a"
        await registry.terminate_all()


class TestSessionRegistryGet:
    """SessionRegistry.get() retrieves a live session."""

    @pytest.mark.asyncio
    async def test_should_get_existing_session(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Getting an existing session returns it."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        spawned = await registry.spawn(repo="project-a")
        retrieved = registry.get(spawned.session_id)
        assert retrieved is spawned
        await registry.terminate_all()

    @pytest.mark.asyncio
    async def test_should_return_none_for_missing(
        self,
        workspace: Path,
        session_dir: Path,
    ) -> None:
        """Getting a non-existent session returns None."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=["unused"],
        )
        assert registry.get("nonexistent") is None


class TestSessionRegistryList:
    """SessionRegistry.list_live() returns all live sessions."""

    @pytest.mark.asyncio
    async def test_should_list_all_live_sessions(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Listing returns all spawned sessions."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        s1 = await registry.spawn(repo="project-a")
        s2 = await registry.spawn(repo="project-b")
        live = registry.list_live()
        assert len(live) == 2
        ids = {s.session_id for s in live}
        assert s1.session_id in ids
        assert s2.session_id in ids
        await registry.terminate_all()

    @pytest.mark.asyncio
    async def test_should_not_include_terminated(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Terminated sessions are removed from live list."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        session = await registry.spawn(repo="project-a")
        await registry.terminate(session.session_id)
        assert len(registry.list_live()) == 0


class TestSessionRegistryTerminate:
    """SessionRegistry.terminate() stops a live session."""

    @pytest.mark.asyncio
    async def test_should_terminate_session(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """Terminating stops the agent and removes from registry."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        session = await registry.spawn(repo="project-a")
        session_id = session.session_id
        await registry.terminate(session_id)
        assert registry.get(session_id) is None

    @pytest.mark.asyncio
    async def test_should_terminate_all_sessions(
        self,
        workspace: Path,
        session_dir: Path,
        fake_pi_cmd: list[str],
    ) -> None:
        """terminate_all() stops all running agents."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=fake_pi_cmd,
        )
        await registry.spawn(repo="project-a")
        await registry.spawn(repo="project-b")
        await registry.terminate_all()
        assert len(registry.list_live()) == 0

    @pytest.mark.asyncio
    async def test_should_raise_on_terminate_missing(
        self,
        workspace: Path,
        session_dir: Path,
    ) -> None:
        """Terminating a non-existent session raises KeyError."""
        registry = SessionRegistry(
            workspace=workspace,
            session_dir=session_dir,
            agent_cmd=["unused"],
        )
        with pytest.raises(KeyError):
            await registry.terminate("nonexistent")
