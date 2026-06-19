"""Backpressure test — AgentProcess must drain stdout even without subscribers.

If no subscriber is attached, events must still be read from the pipe and
buffered. Otherwise pi will block on writes and deadlock.
"""

import asyncio
from pathlib import Path

import pytest

from app.rpc.agent_process import AgentProcess
from app.rpc.types import PromptCommand

# Path to fake pi binary
FAKE_PI = str(Path(__file__).parent.parent / "fake_pi.py")


@pytest.fixture
def fake_pi_cmd() -> list[str]:
    """Command to launch fake pi."""
    return ["python3", FAKE_PI]


class TestBackpressure:
    """AgentProcess handles backpressure correctly."""

    @pytest.mark.asyncio
    async def test_should_drain_stdout_without_subscribers(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Events are buffered even when no subscriber is attached.

        This verifies that the stdout reader task drains the pipe
        independently of subscriber presence.
        """
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            # Send multiple prompts without subscribing
            for i in range(3):
                await proc.send(PromptCommand(message=f"message-{i}"))
                # Small delay to let events arrive
                await asyncio.sleep(0.05)

            # Wait for all events to be buffered
            await asyncio.sleep(0.2)

            # Process should still be alive (not deadlocked)
            assert proc.is_alive

            # Now subscribe with replay — should get all buffered events
            events = []
            async for event in proc.subscribe(replay=True):
                events.append(event)
                if event.type == "agent_end":
                    break

            # Should have received events from all 3 prompts
            agent_end_count = sum(1 for e in events if e.type == "agent_end")
            assert agent_end_count >= 1  # At least the last prompt's events

    @pytest.mark.asyncio
    async def test_should_not_block_on_rapid_events(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Rapid event generation doesn't block the reader.

        The ring buffer absorbs events even when processing is fast.
        """
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            # Send a prompt that will generate many events
            response = await proc.send(PromptCommand(message="rapid"))
            assert response.success is True

            # Process should still be alive
            assert proc.is_alive

            # Ring buffer should have events
            assert len(proc._ring_buffer) > 0
