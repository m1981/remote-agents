"""WebSocket concurrency tests.

Tests that events are streamed in real-time while commands are processing.
This catches bugs where send() blocks the event loop.
"""

import asyncio
import json
from pathlib import Path

import pytest
import websockets
from httpx import ASGITransport

from app.config import Settings
from app.main import create_app
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


@pytest.fixture
def app(registry: SessionRegistry, workspace: Path):
    """Create a test app."""
    settings = Settings(workspace=str(workspace))
    return create_app(settings, registry=registry)


class TestWebSocketConcurrency:
    """Events should stream in real-time, not after command completes."""

    @pytest.mark.asyncio
    async def test_events_arrive_while_command_processing(
        self, app, registry
    ) -> None:
        """Events from pi should arrive while send() is waiting for response.

        This is the regression test for the blocking send() bug.
        If send() blocks the event loop, events won't arrive until
        after the command completes.
        """
        # Spawn a session
        session = await registry.spawn(repo="project-a")
        session_id = session.session_id

        try:
            # Connect to WebSocket using websockets library
            # We need to start the app in the background
            import uvicorn

            config = uvicorn.Config(app, host="127.0.0.1", port=18765)
            server = uvicorn.Server(config)

            # Start server in background
            server_task = asyncio.create_task(server.serve())
            await asyncio.sleep(0.5)  # Wait for server to start

            try:
                async with websockets.connect(
                    f"ws://127.0.0.1:18765/ws/sessions/{session_id}"
                ) as ws:
                    # Receive snapshot first
                    snapshot = json.loads(await ws.recv())
                    assert snapshot["kind"] == "snapshot"

                    # Send prompt
                    await ws.send(json.dumps({
                        "type": "prompt",
                        "message": "hello"
                    }))

                    # Collect events - should arrive in real-time
                    events = []
                    try:
                        async with asyncio.timeout(5):
                            while True:
                                msg = await ws.recv()
                                data = json.loads(msg)
                                events.append(data)
                                if data.get("kind") == "event":
                                    event = data.get("event", {})
                                    if event.get("type") == "agent_end":
                                        break
                    except asyncio.TimeoutError:
                        pass

                    # Verify we received events
                    assert len(events) > 0, "No events received!"

                    # Check event sequence
                    event_types = [
                        e.get("event", {}).get("type")
                        for e in events
                        if e.get("kind") == "event"
                    ]

                    # Should have agent_start before agent_end
                    assert "agent_start" in event_types
                    assert "agent_end" in event_types

            finally:
                server.should_exit = True
                await server_task

        finally:
            await registry.terminate_all()

    @pytest.mark.asyncio
    async def test_multiple_commands_dont_block_each_other(
        self, app, registry
    ) -> None:
        """Multiple commands should process concurrently, not sequentially."""
        session = await registry.spawn(repo="project-a")
        session_id = session.session_id

        try:
            import uvicorn

            config = uvicorn.Config(app, host="127.0.0.1", port=18766)
            server = uvicorn.Server(config)

            server_task = asyncio.create_task(server.serve())
            await asyncio.sleep(0.5)

            try:
                async with websockets.connect(
                    f"ws://127.0.0.1:18766/ws/sessions/{session_id}"
                ) as ws:
                    # Receive snapshot
                    await ws.recv()

                    # Send multiple commands rapidly
                    for i in range(3):
                        await ws.send(json.dumps({
                            "type": "prompt",
                            "message": f"message {i}"
                        }))

                    # Collect all events
                    events = []
                    agent_end_count = 0
                    try:
                        async with asyncio.timeout(10):
                            while agent_end_count < 3:
                                msg = await ws.recv()
                                data = json.loads(msg)
                                events.append(data)
                                if data.get("kind") == "event":
                                    event = data.get("event", {})
                                    if event.get("type") == "agent_end":
                                        agent_end_count += 1
                    except asyncio.TimeoutError:
                        pass

                    # Should have received events for all 3 commands
                    assert agent_end_count == 3, f"Expected 3 agent_end, got {agent_end_count}"

            finally:
                server.should_exit = True
                await server_task

        finally:
            await registry.terminate_all()


class TestWebSocketEventOrdering:
    """Events should arrive in correct order."""

    @pytest.mark.asyncio
    async def test_events_arrive_in_order(self, app, registry) -> None:
        """Events from pi arrive in the correct sequence."""
        session = await registry.spawn(repo="project-a")
        session_id = session.session_id

        try:
            import uvicorn

            config = uvicorn.Config(app, host="127.0.0.1", port=18767)
            server = uvicorn.Server(config)

            server_task = asyncio.create_task(server.serve())
            await asyncio.sleep(0.5)

            try:
                async with websockets.connect(
                    f"ws://127.0.0.1:18767/ws/sessions/{session_id}"
                ) as ws:
                    # Receive snapshot
                    await ws.recv()

                    # Send prompt
                    await ws.send(json.dumps({
                        "type": "prompt",
                        "message": "test order"
                    }))

                    # Collect events
                    events = []
                    try:
                        async with asyncio.timeout(5):
                            while True:
                                msg = await ws.recv()
                                data = json.loads(msg)
                                if data.get("kind") == "event":
                                    events.append(data["event"])
                                    if data["event"].get("type") == "agent_end":
                                        break
                    except asyncio.TimeoutError:
                        pass

                    # Verify order
                    event_types = [e.get("type") for e in events]

                    # agent_start should come before turn_start
                    if "agent_start" in event_types and "turn_start" in event_types:
                        assert event_types.index("agent_start") < event_types.index("turn_start")

                    # turn_start should come before agent_end
                    if "turn_start" in event_types and "agent_end" in event_types:
                        assert event_types.index("turn_start") < event_types.index("agent_end")

            finally:
                server.should_exit = True
                await server_task

        finally:
            await registry.terminate_all()
