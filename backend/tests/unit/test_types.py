"""Tests for app.rpc.types — Pydantic models for RPC commands and events."""

import json

from app.rpc.types import (
    AbortCommand,
    AgentEndEvent,
    AgentStartEvent,
    Event,
    GetMessagesCommand,
    GetStateCommand,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    PromptCommand,
    ResponseEvent,
    SteerCommand,
    parse_event,
)


class TestCommandParsing:
    """Commands can be serialized to JSONL for sending to pi."""

    def test_should_serialize_prompt_command(self) -> None:
        """PromptCommand serializes with type and message."""
        cmd = PromptCommand(message="Hello, world!")
        data = json.loads(cmd.to_jsonl())
        assert data["type"] == "prompt"
        assert data["message"] == "Hello, world!"

    def test_should_serialize_prompt_with_id(self) -> None:
        """PromptCommand includes id when provided."""
        cmd = PromptCommand(message="test", id="req-1")
        data = json.loads(cmd.to_jsonl())
        assert data["id"] == "req-1"

    def test_should_serialize_steer_command(self) -> None:
        """SteerCommand serializes with type and message."""
        cmd = SteerCommand(message="Do this instead")
        data = json.loads(cmd.to_jsonl())
        assert data["type"] == "steer"
        assert data["message"] == "Do this instead"

    def test_should_serialize_abort_command(self) -> None:
        """AbortCommand serializes with type only."""
        cmd = AbortCommand()
        data = json.loads(cmd.to_jsonl())
        assert data == {"type": "abort"}

    def test_should_serialize_get_state_command(self) -> None:
        """GetStateCommand serializes with type only."""
        cmd = GetStateCommand(id="req-2")
        data = json.loads(cmd.to_jsonl())
        assert data == {"type": "get_state", "id": "req-2"}

    def test_should_serialize_get_messages_command(self) -> None:
        """GetMessagesCommand serializes with type only."""
        cmd = GetMessagesCommand()
        data = json.loads(cmd.to_jsonl())
        assert data == {"type": "get_messages"}


class TestEventParsing:
    """Events can be parsed from JSONL received from pi."""

    def test_should_parse_agent_start_event(self) -> None:
        """agent_start event parses correctly."""
        raw = {"type": "agent_start"}
        event = parse_event(raw)
        assert isinstance(event, AgentStartEvent)

    def test_should_parse_agent_end_event(self) -> None:
        """agent_end event parses with messages list."""
        raw = {"type": "agent_end", "messages": []}
        event = parse_event(raw)
        assert isinstance(event, AgentEndEvent)
        assert event.messages == []

    def test_should_parse_response_event(self) -> None:
        """Response event parses with command and success fields."""
        raw = {
            "type": "response",
            "id": "req-1",
            "command": "get_state",
            "success": True,
            "data": {"sessionId": "abc"},
        }
        event = parse_event(raw)
        assert isinstance(event, ResponseEvent)
        assert event.id == "req-1"
        assert event.command == "get_state"
        assert event.success is True
        assert event.data == {"sessionId": "abc"}

    def test_should_parse_message_start_event(self) -> None:
        """message_start event parses with message field."""
        raw = {
            "type": "message_start",
            "message": {"role": "assistant", "content": []},
        }
        event = parse_event(raw)
        assert isinstance(event, MessageStartEvent)
        assert event.message["role"] == "assistant"

    def test_should_parse_message_update_event(self) -> None:
        """message_update event parses with message and assistantMessageEvent."""
        raw = {
            "type": "message_update",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Hel"}]},
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 0,
                "delta": "lo",
            },
        }
        event = parse_event(raw)
        assert isinstance(event, MessageUpdateEvent)
        assert event.assistant_message_event["type"] == "text_delta"
        assert event.assistant_message_event["delta"] == "lo"

    def test_should_parse_message_end_event(self) -> None:
        """message_end event parses with message field."""
        raw = {
            "type": "message_end",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
        }
        event = parse_event(raw)
        assert isinstance(event, MessageEndEvent)

    def test_should_parse_unknown_event_as_generic(self) -> None:
        """Unknown event types are parsed as generic Event."""
        raw = {"type": "some_new_event", "data": 42}
        event = parse_event(raw)
        assert isinstance(event, Event)
        assert event.type == "some_new_event"

    def test_should_preserve_raw_data_on_all_events(self) -> None:
        """All parsed events preserve the raw dict for forward compatibility."""
        raw = {"type": "agent_start"}
        event = parse_event(raw)
        assert event.raw == raw


class TestEventRoundTrip:
    """Events round-trip through JSON without data loss."""

    def test_should_round_trip_response_event(self) -> None:
        """ResponseEvent survives JSON serialization."""
        raw = {
            "type": "response",
            "id": "req-1",
            "command": "prompt",
            "success": True,
        }
        event = parse_event(raw)
        serialized = json.loads(event.model_dump_json())
        assert serialized["type"] == "response"
        assert serialized["id"] == "req-1"
