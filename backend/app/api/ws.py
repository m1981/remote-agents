"""/ws/sessions/{id} — WebSocket endpoint for live session interaction.

Protocol:
- Client sends: {"type": "prompt"|"steer"|"follow_up"|"abort", "message": "..."}
- Server sends: {"kind": "snapshot", "state": {...}, "messages": [...]}
- Server sends: {"kind": "event", "event": {...}}
- Server sends: {"kind": "error", "reason": "..."}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.sessions.registry import SessionRegistry

logger = logging.getLogger(__name__)


def get_registry_ws(websocket: WebSocket) -> SessionRegistry:
    """Dependency to get the SessionRegistry from app state for WebSocket."""
    registry = websocket.app.state.registry
    if registry is None:
        raise RuntimeError("Registry not initialized")
    return registry


def create_ws_router() -> APIRouter:
    """Create the WebSocket router."""
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/sessions/{session_id}")
    async def session_ws(
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        """WebSocket endpoint for live session interaction.

        On connect:
        1. Accept the connection
        2. Send current state snapshot (get_state + get_messages)
        3. Subscribe to event stream
        4. Forward client commands to agent

        Args:
            websocket: The WebSocket connection.
            session_id: The session ID to connect to.
        """
        registry = websocket.app.state.registry
        if registry is None:
            await websocket.close(code=1011, detail="Registry not initialized")
            return

        session = registry.get(session_id)
        if not session:
            await websocket.close(code=4004, detail="Session not found")
            return

        await websocket.accept()
        logger.info("WebSocket connected: session=%s", session_id)

        try:
            # Send initial snapshot
            await _send_snapshot(websocket, session)

            # Start event forwarder task
            import asyncio

            event_task = asyncio.create_task(
                _forward_events(websocket, session)
            )

            # Handle client messages
            while True:
                try:
                    data = await websocket.receive_text()
                    await _handle_client_message(websocket, session, data)
                except WebSocketDisconnect:
                    break

        except Exception as e:
            logger.error("WebSocket error: %s", e)
        finally:
            if 'event_task' in locals():
                event_task.cancel()
            logger.info("WebSocket disconnected: session=%s", session_id)

    return router


async def _send_snapshot(websocket: WebSocket, session: Any) -> None:
    """Send current state snapshot to the client.

    Gets current state and messages from the agent and sends them.
    """
    from app.rpc.types import GetMessagesCommand, GetStateCommand

    try:
        # Get current state
        state_response = await session.agent.send(GetStateCommand())

        # Get messages
        messages_response = await session.agent.send(GetMessagesCommand())

        snapshot = {
            "kind": "snapshot",
            "state": state_response.data if state_response.success else {},
            "messages": (
                messages_response.data.get("messages", [])
                if messages_response.success
                else []
            ),
        }

        await websocket.send_text(json.dumps(snapshot))
    except Exception as e:
        logger.error("Failed to send snapshot: %s", e)
        await websocket.send_text(json.dumps({
            "kind": "error",
            "reason": f"Failed to get snapshot: {e}",
        }))


async def _forward_events(websocket: WebSocket, session: Any) -> None:
    """Forward agent events to the WebSocket client."""
    import asyncio

    try:
        async for event in session.agent.subscribe(replay=False):
            if websocket.client_state != WebSocketState.CONNECTED:
                break

            message = {
                "kind": "event",
                "event": event.raw,
            }
            await websocket.send_text(json.dumps(message))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Event forwarder error: %s", e)


async def _handle_client_message(
    websocket: WebSocket,
    session: Any,
    data: str,
) -> None:
    """Handle a message from the client.

    Parses the message and forwards it to the agent as a command.
    """
    from app.rpc.types import (
        AbortCommand,
        FollowUpCommand,
        PromptCommand,
        SteerCommand,
    )

    try:
        msg = json.loads(data)
    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({
            "kind": "error",
            "reason": "Invalid JSON",
        }))
        return

    msg_type = msg.get("type")
    message = msg.get("message")

    try:
        if msg_type == "prompt":
            cmd = PromptCommand(message=message or "")
            await session.agent.send(cmd)
        elif msg_type == "steer":
            cmd = SteerCommand(message=message or "")
            await session.agent.send(cmd)
        elif msg_type == "follow_up":
            cmd = FollowUpCommand(message=message or "")
            await session.agent.send(cmd)
        elif msg_type == "abort":
            cmd = AbortCommand()
            await session.agent.send(cmd)
        else:
            await websocket.send_text(json.dumps({
                "kind": "error",
                "reason": f"Unknown message type: {msg_type}",
            }))
    except Exception as e:
        logger.error("Failed to handle client message: %s", e)
        await websocket.send_text(json.dumps({
            "kind": "error",
            "reason": f"Command failed: {e}",
        }))
