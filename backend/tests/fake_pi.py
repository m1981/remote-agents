#!/usr/bin/env python3
"""Fake pi binary for testing AgentProcess.

Simulates pi --mode rpc behavior:
- Reads JSONL commands from stdin
- Emits canned event sequences on stdout
- Supports get_state, get_messages, prompt, abort commands

Usage:
    echo '{"type":"get_state"}' | python fake_pi.py
"""

import json
import os
import sys
import time
import uuid

# Session metadata for this fake instance
SESSION_ID = os.environ.get("FAKE_SESSION_ID", f"fake-session-{uuid.uuid4().hex[:8]}")
SESSION_NAME = "test-session"


def write_event(event: dict) -> None:
    """Write a JSONL event to stdout and flush."""
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def handle_get_state(request_id: str | None) -> None:
    """Respond with current session state."""
    write_event({
        "type": "response",
        "id": request_id,
        "command": "get_state",
        "success": True,
        "data": {
            "sessionId": SESSION_ID,
            "sessionName": SESSION_NAME,
            "isStreaming": False,
            "messageCount": 0,
            "pendingMessageCount": 0,
        },
    })


def handle_get_messages(request_id: str | None) -> None:
    """Respond with empty message list."""
    write_event({
        "type": "response",
        "id": request_id,
        "command": "get_messages",
        "success": True,
        "data": {"messages": []},
    })


def handle_prompt(request_id: str | None, message: str) -> None:
    """Simulate processing a prompt with streaming events."""
    # Acknowledge the prompt
    write_event({
        "type": "response",
        "id": request_id,
        "command": "prompt",
        "success": True,
    })

    # Simulate agent start
    write_event({"type": "agent_start"})

    # Simulate turn start
    write_event({"type": "turn_start"})

    # Simulate message start
    write_event({
        "type": "message_start",
        "message": {
            "role": "assistant",
            "content": [],
            "timestamp": int(time.time() * 1000),
        },
    })

    # Simulate text streaming
    write_event({
        "type": "message_update",
        "message": {"role": "assistant", "content": [{"type": "text", "text": ""}]},
        "assistantMessageEvent": {"type": "text_start", "contentIndex": 0},
    })

    # Stream response tokens
    response_text = f"Echo: {message}"
    for i in range(0, len(response_text), 5):
        chunk = response_text[i : i + 5]
        write_event({
            "type": "message_update",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": response_text[: i + len(chunk)]}],
            },
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 0,
                "delta": chunk,
            },
        })

    write_event({
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": response_text}],
        },
        "assistantMessageEvent": {"type": "text_end", "contentIndex": 0, "content": response_text},
    })

    # Message done
    write_event({
        "type": "message_update",
        "message": {"role": "assistant", "content": [{"type": "text", "text": response_text}]},
        "assistantMessageEvent": {"type": "done", "reason": "stop"},
    })

    # Simulate message end
    write_event({
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": response_text}],
            "timestamp": int(time.time() * 1000),
        },
    })

    # Simulate turn end
    write_event({
        "type": "turn_end",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": response_text}],
        },
        "toolResults": [],
    })

    # Simulate agent end
    write_event({
        "type": "agent_end",
        "messages": [
            {
                "role": "assistant",
                "content": [{"type": "text", "text": response_text}],
                "timestamp": int(time.time() * 1000),
            }
        ],
    })


def handle_abort(request_id: str | None) -> None:
    """Respond to abort command."""
    write_event({
        "type": "response",
        "id": request_id,
        "command": "abort",
        "success": True,
    })


def handle_unknown(request_id: str | None, command_type: str) -> None:
    """Respond to unknown command."""
    write_event({
        "type": "response",
        "id": request_id,
        "command": command_type,
        "success": True,
    })


def main() -> None:
    """Main loop: read commands from stdin, emit events to stdout."""
    # Emit initial state event (pi does this on startup)
    write_event({
        "type": "state",
        "sessionId": SESSION_ID,
        "sessionName": SESSION_NAME,
    })

    for line in sys.stdin:
        line = line.rstrip("\r\n")
        if not line:
            continue

        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            write_event({
                "type": "response",
                "command": "parse",
                "success": False,
                "error": f"Failed to parse command: {line}",
            })
            continue

        cmd_type = cmd.get("type", "")
        request_id = cmd.get("id")

        if cmd_type == "get_state":
            handle_get_state(request_id)
        elif cmd_type == "get_messages":
            handle_get_messages(request_id)
        elif cmd_type == "prompt":
            handle_prompt(request_id, cmd.get("message", ""))
        elif cmd_type == "abort":
            handle_abort(request_id)
        else:
            handle_unknown(request_id, cmd_type)


if __name__ == "__main__":
    main()
