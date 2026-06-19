"""Integration test — full happy path through the system.

Tests the complete lifecycle:
1. Spawn session via registry
2. Send prompt
3. Receive streamed events
4. Terminate session

This validates that all components work together correctly.
"""

from pathlib import Path

import pytest

from app.rpc.types import GetStateCommand, PromptCommand
from app.sessions.registry import SessionRegistry

FAKE_PI = str(Path(__file__).parent.parent / "fake_pi.py")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with sample repos."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "project-a").mkdir()
    return ws


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """Create a session directory."""
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture
def registry(workspace: Path, session_dir: Path) -> SessionRegistry:
    """Create a session registry."""
    return SessionRegistry(
        workspace=workspace,
        session_dir=session_dir,
        agent_cmd=["python3", FAKE_PI],
    )


class TestFullHappyPath:
    """Complete lifecycle: spawn → interact → terminate."""

    @pytest.mark.asyncio
    async def test_spawn_prompt_receive_terminate(self, registry: SessionRegistry) -> None:
        """Full flow works end-to-end."""
        # 1. Spawn session
        session = await registry.spawn(repo="project-a", name="e2e-test")
        assert session.is_alive
        assert session.session_id is not None

        # 2. Verify initial state
        state = await session.agent.send(GetStateCommand())
        assert state.success
        assert state.data is not None

        # 3. Send prompt
        response = await session.agent.send(
            PromptCommand(message="Hello from test")
        )
        assert response.success

        # 4. Collect events
        events = []
        async for event in session.agent.subscribe(replay=True):
            events.append(event)
            if event.type == "agent_end":
                break

        # 5. Verify event sequence
        event_types = [e.type for e in events]
        assert "agent_start" in event_types
        assert "agent_end" in event_types
        assert "turn_start" in event_types

        # 6. Terminate
        await registry.terminate(session.session_id)
        assert len(registry.list_live()) == 0

    @pytest.mark.asyncio
    async def test_multiple_prompts_in_sequence(self, registry: SessionRegistry) -> None:
        """Multiple prompts can be sent to the same session."""
        session = await registry.spawn(repo="project-a")

        # Send multiple prompts
        for i in range(3):
            response = await session.agent.send(
                PromptCommand(message=f"Message {i}")
            )
            assert response.success

        # Terminate
        await registry.terminate(session.session_id)

    @pytest.mark.asyncio
    async def test_spawn_multiple_sessions(self, registry: SessionRegistry) -> None:
        """Multiple sessions can run concurrently."""
        sessions = []
        for _ in range(3):
            s = await registry.spawn(repo="project-a")
            sessions.append(s)

        # All should be alive
        for s in sessions:
            assert s.is_alive

        # All should be listed
        assert len(registry.list_live()) == 3

        # Terminate all
        await registry.terminate_all()
        assert len(registry.list_live()) == 0
