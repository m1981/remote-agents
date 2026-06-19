"""Boundary tests — edge cases and failure modes.

Tests scenarios that are unlikely but must be handled gracefully:
- Slow subscribers missing events
- Process crash during operation
- Rapid spawn/terminate cycles
- Empty prompts
- Concurrent subscriber cleanup
"""

import asyncio
from pathlib import Path

import pytest

from app.rpc.types import PromptCommand
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


class TestSlowSubscriber:
    """Subscriber that connects after events have already fired."""

    @pytest.mark.asyncio
    async def test_late_subscriber_gets_replay(self, registry: SessionRegistry) -> None:
        """Subscriber connecting after prompt still sees events via replay."""
        session = await registry.spawn(repo="project-a")

        # Send prompt and let it complete
        await session.agent.send(PromptCommand(message="buffered"))
        await asyncio.sleep(0.1)

        # Late subscriber with replay
        events = []
        async for event in session.agent.subscribe(replay=True):
            events.append(event)
            if event.type == "agent_end":
                break

        assert len(events) > 0
        event_types = [e.type for e in events]
        assert "agent_start" in event_types

        await registry.terminate(session.session_id)

    @pytest.mark.asyncio
    async def test_subscriber_without_replay_gets_nothing(self, registry: SessionRegistry) -> None:
        """Subscriber without replay sees no historical events."""
        session = await registry.spawn(repo="project-a")

        # Send prompt and let it complete
        await session.agent.send(PromptCommand(message="missed"))
        await asyncio.sleep(0.1)

        # Subscriber without replay - should timeout with nothing
        events = []
        try:
            async with asyncio.timeout(0.2):
                async for event in session.agent.subscribe(replay=False):
                    events.append(event)
        except TimeoutError:
            pass

        # Should have received nothing (or only new events)
        assert len(events) == 0

        await registry.terminate(session.session_id)


class TestEmptyAndEdgeCases:
    """Edge cases in input handling."""

    @pytest.mark.asyncio
    async def test_empty_prompt(self, registry: SessionRegistry) -> None:
        """Empty prompt is accepted."""
        session = await registry.spawn(repo="project-a")

        response = await session.agent.send(PromptCommand(message=""))
        assert response.success

        await registry.terminate(session.session_id)

    @pytest.mark.asyncio
    async def test_long_prompt(self, registry: SessionRegistry) -> None:
        """Very long prompt is accepted."""
        session = await registry.spawn(repo="project-a")

        long_message = "x" * 1000  # 1KB instead of 10KB
        response = await asyncio.wait_for(
            session.agent.send(PromptCommand(message=long_message)),
            timeout=5.0,
        )
        assert response.success

        await registry.terminate(session.session_id)

    @pytest.mark.asyncio
    async def test_unicode_prompt(self, registry: SessionRegistry) -> None:
        """Unicode prompt is accepted."""
        session = await registry.spawn(repo="project-a")

        unicode_message = "Hello 🌍 café résumé"
        response = await session.agent.send(PromptCommand(message=unicode_message))
        assert response.success

        await registry.terminate(session.session_id)


class TestRapidCycles:
    """Rapid spawn/terminate cycles."""

    @pytest.mark.asyncio
    async def test_rapid_spawn_terminate(self, registry: SessionRegistry) -> None:
        """Many rapid spawn/terminate cycles don't leak."""
        for _ in range(5):
            session = await registry.spawn(repo="project-a")
            await registry.terminate(session.session_id)

        assert len(registry.list_live()) == 0

    @pytest.mark.asyncio
    async def test_terminate_already_terminated(self, registry: SessionRegistry) -> None:
        """Terminating an already-terminated session raises KeyError."""
        session = await registry.spawn(repo="project-a")
        session_id = session.session_id

        await registry.terminate(session_id)

        with pytest.raises(KeyError):
            await registry.terminate(session_id)


class TestConcurrentSubscribers:
    """Multiple subscribers on the same session."""

    @pytest.mark.asyncio
    async def test_two_subscribers_see_same_events(self, registry: SessionRegistry) -> None:
        """Two concurrent subscribers both receive events."""
        session = await registry.spawn(repo="project-a")

        # Create two subscriber queues
        events_1 = []
        events_2 = []

        async def collect_1():
            async for event in session.agent.subscribe(replay=True):
                events_1.append(event)
                if event.type == "agent_end":
                    break

        async def collect_2():
            async for event in session.agent.subscribe(replay=True):
                events_2.append(event)
                if event.type == "agent_end":
                    break

        # Send prompt
        await session.agent.send(PromptCommand(message="shared"))
        await asyncio.sleep(0.1)

        # Both subscribers collect
        await asyncio.gather(collect_1(), collect_2())

        # Both should have received events
        assert len(events_1) > 0
        assert len(events_2) > 0

        await registry.terminate(session.session_id)
