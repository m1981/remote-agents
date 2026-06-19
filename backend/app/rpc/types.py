"""Pydantic models for the pi RPC protocol.

Provides typed command and event models for the JSONL-based RPC channel.
Commands are sent to pi's stdin; events are received from pi's stdout.

Protocol reference: https://github.com/mariozechner/pi-coding-agent/docs/rpc.md
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Commands — sent to pi's stdin
# ---------------------------------------------------------------------------


class Command(BaseModel):
    """Base class for all RPC commands."""

    type: str
    id: str | None = None

    def to_jsonl(self) -> str:
        """Serialize to JSONL string (single line, no trailing newline)."""
        data = self.model_dump(exclude_none=True)
        return json.dumps(data)


class PromptCommand(Command):
    """Send a user prompt to the agent."""

    type: Literal["prompt"] = "prompt"
    message: str
    streaming_behavior: str | None = Field(default=None, alias="streamingBehavior")

    model_config = {"populate_by_name": True}


class SteerCommand(Command):
    """Queue a steering message while agent is running."""

    type: Literal["steer"] = "steer"
    message: str


class FollowUpCommand(Command):
    """Queue a follow-up message after agent finishes."""

    type: Literal["follow_up"] = "follow_up"
    message: str


class AbortCommand(Command):
    """Abort the current agent operation."""

    type: Literal["abort"] = "abort"


class GetStateCommand(Command):
    """Get current session state."""

    type: Literal["get_state"] = "get_state"


class GetMessagesCommand(Command):
    """Get all messages in the conversation."""

    type: Literal["get_messages"] = "get_messages"


class SetSessionNameCommand(Command):
    """Set a display name for the current session."""

    type: Literal["set_session_name"] = "set_session_name"
    name: str


# Union type for all commands
AnyCommand = (
    PromptCommand
    | SteerCommand
    | FollowUpCommand
    | AbortCommand
    | GetStateCommand
    | GetMessagesCommand
    | SetSessionNameCommand
)


# ---------------------------------------------------------------------------
# Events — received from pi's stdout
# ---------------------------------------------------------------------------


class Event(BaseModel):
    """Base class for all RPC events.

    Preserves the raw dict for forward compatibility with new event types.
    """

    type: str
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


class ResponseEvent(Event):
    """Response to a command sent to pi."""

    type: Literal["response"] = "response"
    id: str | None = None
    command: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class AgentStartEvent(Event):
    """Agent begins processing a prompt."""

    type: Literal["agent_start"] = "agent_start"


class AgentEndEvent(Event):
    """Agent completes. Contains all messages generated during this run."""

    type: Literal["agent_end"] = "agent_end"
    messages: list[dict[str, Any]] = Field(default_factory=list)


class TurnStartEvent(Event):
    """New turn begins."""

    type: Literal["turn_start"] = "turn_start"


class TurnEndEvent(Event):
    """Turn completes."""

    type: Literal["turn_end"] = "turn_end"
    message: dict[str, Any] | None = None
    tool_results: list[dict[str, Any]] = Field(default_factory=list, alias="toolResults")

    model_config = {"populate_by_name": True}


class MessageStartEvent(Event):
    """Message begins."""

    type: Literal["message_start"] = "message_start"
    message: dict[str, Any]


class MessageUpdateEvent(Event):
    """Streaming update with text/thinking/toolcall deltas."""

    type: Literal["message_update"] = "message_update"
    message: dict[str, Any]
    assistant_message_event: dict[str, Any] = Field(alias="assistantMessageEvent")

    model_config = {"populate_by_name": True}


class MessageEndEvent(Event):
    """Message completes."""

    type: Literal["message_end"] = "message_end"
    message: dict[str, Any]


class ToolExecutionStartEvent(Event):
    """Tool begins execution."""

    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str = Field(alias="toolCallId")
    tool_name: str = Field(alias="toolName")
    args: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ToolExecutionEndEvent(Event):
    """Tool completes execution."""

    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str = Field(alias="toolCallId")
    tool_name: str = Field(alias="toolName")
    result: dict[str, Any] | None = None
    is_error: bool = Field(default=False, alias="isError")

    model_config = {"populate_by_name": True}


class QueueUpdateEvent(Event):
    """Pending steering/follow-up queue changed."""

    type: Literal["queue_update"] = "queue_update"
    steering: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list, alias="followUp")

    model_config = {"populate_by_name": True}


class StateEvent(Event):
    """Initial state event emitted on startup."""

    type: Literal["state"] = "state"
    session_id: str | None = Field(default=None, alias="sessionId")
    session_name: str | None = Field(default=None, alias="sessionName")

    model_config = {"populate_by_name": True}


# Event type mapping for parsing
_EVENT_TYPES: dict[str, type[Event]] = {
    "response": ResponseEvent,
    "agent_start": AgentStartEvent,
    "agent_end": AgentEndEvent,
    "turn_start": TurnStartEvent,
    "turn_end": TurnEndEvent,
    "message_start": MessageStartEvent,
    "message_update": MessageUpdateEvent,
    "message_end": MessageEndEvent,
    "tool_execution_start": ToolExecutionStartEvent,
    "tool_execution_end": ToolExecutionEndEvent,
    "queue_update": QueueUpdateEvent,
    "state": StateEvent,
}


def parse_event(raw: dict[str, Any]) -> Event:
    """Parse a raw dict into a typed Event.

    Falls back to generic Event for unknown types (forward compatibility).
    Missing or empty type field is handled gracefully.

    Args:
        raw: Parsed JSON object from pi's stdout.

    Returns:
        Typed Event subclass instance.
    """
    event_type = raw.get("type", "")
    event_cls = _EVENT_TYPES.get(event_type, Event)

    # Always preserve raw data, pass all fields including type
    # Ensure type field exists for validation
    kwargs = {"raw": raw, **raw}
    if "type" not in kwargs:
        kwargs["type"] = "unknown"
    return event_cls(**kwargs)
