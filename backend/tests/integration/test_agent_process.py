"""Integration tests for AgentProcess — the core RPC state machine.

Tests use the fake_pi.py binary to verify:
- Starting a subprocess and establishing RPC channel
- Sending commands and receiving correlated responses
- Subscribing to event streams
- Ring buffer replay for late subscribers
- Clean termination
"""

import asyncio
from pathlib import Path

import pytest

from app.rpc.agent_process import AgentProcess, AgentProcessError
from app.rpc.types import (
    GetStateCommand,
    PromptCommand,
    ResponseEvent,
)

# Path to fake pi binary
FAKE_PI = str(Path(__file__).parent.parent / "fake_pi.py")


@pytest.fixture
def fake_pi_cmd() -> list[str]:
    """Command to launch fake pi."""
    return ["python3", FAKE_PI]


class TestAgentProcessStart:
    """AgentProcess.start() establishes the RPC channel."""

    @pytest.mark.asyncio
    async def test_should_start_subprocess_and_get_initial_state(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Starting AgentProcess spawns pi and receives initial state event."""
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            assert proc.session_id is not None
            assert proc.session_id.startswith("fake-session-")
            assert proc.is_alive

    @pytest.mark.asyncio
    async def test_should_fail_gracefully_on_bad_command(self, tmp_path: Path) -> None:
        """AgentProcess raises on invalid command."""
        with pytest.raises(AgentProcessError):
            async with AgentProcess.start(["false"], cwd=tmp_path):
                pass


class TestAgentProcessSend:
    """AgentProcess.send() sends commands and returns correlated responses."""

    @pytest.mark.asyncio
    async def test_should_send_command_and_get_response(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Sending get_state returns a correlated response."""
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            response = await proc.send(GetStateCommand())
            assert isinstance(response, ResponseEvent)
            assert response.success is True
            assert response.command == "get_state"

    @pytest.mark.asyncio
    async def test_should_correlate_response_by_id(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Response includes the same id as the command."""
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            response = await proc.send(GetStateCommand(id="my-req-1"))
            assert response.id == "my-req-1"


class TestAgentProcessSubscribe:
    """AgentProcess.subscribe() yields events in order."""

    @pytest.mark.asyncio
    async def test_should_receive_events_in_order(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Events arrive in the order pi emits them."""
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            # Send prompt first, events will be buffered
            await proc.send(PromptCommand(message="hello"))

            # Small delay to let all events arrive
            await asyncio.sleep(0.1)

            # Subscribe with replay to get buffered events
            events = []
            async for event in proc.subscribe(replay=True):
                events.append(event)
                if event.type == "agent_end":
                    break

            # Verify order: agent_start, turn_start, message_start, ..., agent_end
            event_types = [e.type for e in events]
            assert event_types[0] == "agent_start"
            assert event_types[-1] == "agent_end"
            assert "turn_start" in event_types
            assert "message_start" in event_types

    @pytest.mark.asyncio
    async def test_should_replay_ring_buffer_for_late_subscriber(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Late subscriber receives buffered events from ring buffer."""
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            # Send prompt and let it complete
            await proc.send(PromptCommand(message="buffered"))

            # Wait for agent to finish
            await asyncio.sleep(0.1)

            # New subscriber should get replay
            events = []
            async for event in proc.subscribe(replay=True):
                events.append(event)
                if event.type == "agent_end":
                    break

            # Should have received replayed events
            assert len(events) > 0
            event_types = [e.type for e in events]
            assert "agent_start" in event_types


class TestAgentProcessTerminate:
    """AgentProcess.terminate() cleanly shuts down the subprocess."""

    @pytest.mark.asyncio
    async def test_should_terminate_cleanly(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Terminate exits within timeout."""
        proc = await AgentProcess.start(fake_pi_cmd, cwd=tmp_path).__aenter__()
        assert proc.is_alive

        await proc.terminate()
        assert not proc.is_alive

    @pytest.mark.asyncio
    async def test_should_exit_context_manager_cleanly(
        self, fake_pi_cmd: list[str], tmp_path: Path
    ) -> None:
        """Context manager terminates on exit."""
        async with AgentProcess.start(fake_pi_cmd, cwd=tmp_path) as proc:
            assert proc.is_alive
        # After exiting context, process should be terminated
        assert not proc.is_alive
