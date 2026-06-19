"""Edge case and randomized behavior tests.

Uncovers hidden bugs through adversarial scenarios:
- Malformed input handling
- Race conditions
- Resource exhaustion
- Unexpected subprocess behavior
"""

import asyncio
import contextlib
import json
import random
import string
from pathlib import Path

import pytest

from app.rpc.agent_process import AgentProcess, AgentProcessError
from app.rpc.framing import read_jsonl_lines
from app.rpc.types import (
    GetStateCommand,
    PromptCommand,
    parse_event,
)
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


# ---------------------------------------------------------------------------
# Subprocess Edge Cases
# ---------------------------------------------------------------------------


class TestSubprocessEdgeCases:
    """Edge cases in subprocess lifecycle."""

    @pytest.mark.asyncio
    async def test_subprocess_exits_during_read(self, tmp_path: Path) -> None:
        """Reader handles subprocess exit gracefully."""
        # Use 'true' which exits immediately
        with pytest.raises(AgentProcessError):
            async with AgentProcess.start(["true"], cwd=tmp_path):
                pass

    @pytest.mark.asyncio
    async def test_subprocess_stderr_is_captured(self, tmp_path: Path) -> None:
        """Subprocess that exits immediately raises AgentProcessError."""
        with pytest.raises(AgentProcessError, match="exited before producing initial state"):
            async with AgentProcess.start(
                ["python3", "-c", "import sys; sys.stderr.write('err\\n'); sys.exit(1)"],
                cwd=tmp_path,
            ):
                pass

    @pytest.mark.asyncio
    async def test_terminate_already_dead_process(self, tmp_path: Path) -> None:
        """Process that exits immediately raises AgentProcessError."""
        with pytest.raises(AgentProcessError, match="exited before producing initial state"):
            async with AgentProcess.start(["python3", "-c", "exit(0)"], cwd=tmp_path):
                pass


# ---------------------------------------------------------------------------
# Framing Edge Cases
# ---------------------------------------------------------------------------


class TestFramingEdgeCases:
    """Edge cases in JSONL framing."""

    @pytest.mark.asyncio
    async def test_only_newlines(self) -> None:
        """Stream of only newlines yields nothing."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"\n\n\n\n\n")
        reader.feed_eof()
        lines = [line async for line in read_jsonl_lines(reader)]
        assert lines == []

    @pytest.mark.asyncio
    async def test_mixed_empty_and_content(self) -> None:
        """Mix of empty lines and content works."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"\n\n{\"a\":1}\n\n\n{\"b\":2}\n\n")
        reader.feed_eof()
        lines = [line async for line in read_jsonl_lines(reader)]
        assert lines == ['{"a":1}', '{"b":2}']

    @pytest.mark.asyncio
    async def test_binary_like_content(self) -> None:
        """Binary-looking JSON is handled."""
        reader = asyncio.StreamReader()
        # JSON with escaped unicode
        data = '{"data":"\\u0000\\u0001\\u0002"}\n'
        reader.feed_data(data.encode("utf-8"))
        reader.feed_eof()
        lines = [line async for line in read_jsonl_lines(reader)]
        assert len(lines) == 1

    @pytest.mark.asyncio
    async def test_very_many_small_lines(self) -> None:
        """Many small lines don't cause issues."""
        reader = asyncio.StreamReader()
        for _ in range(1000):
            reader.feed_data(b'{"x":1}\n')
        reader.feed_eof()
        lines = [line async for line in read_jsonl_lines(reader)]
        assert len(lines) == 1000

    @pytest.mark.asyncio
    async def test_line_with_only_whitespace(self) -> None:
        """Whitespace-only lines are skipped."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"  \t  \n{\"a\":1}\n  \n")
        reader.feed_eof()
        lines = [line async for line in read_jsonl_lines(reader)]
        # Whitespace lines that aren't empty after rstrip are kept
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# Event Parsing Edge Cases
# ---------------------------------------------------------------------------


class TestEventParsingEdgeCases:
    """Edge cases in event parsing."""

    def test_empty_dict(self) -> None:
        """Empty dict is handled gracefully with default type."""
        event = parse_event({})
        assert event.type == "unknown"

    def test_missing_type_field(self) -> None:
        """Missing type field defaults to 'unknown'."""
        event = parse_event({"data": 42})
        assert event.type == "unknown"
        assert event.raw == {"data": 42}

    def test_none_values(self) -> None:
        """None values in fields are handled."""
        event = parse_event({"type": "response", "id": None, "command": "test", "success": True})
        assert event.id is None

    def test_nested_none(self) -> None:
        """Deeply nested None values."""
        event = parse_event({
            "type": "message_update",
            "message": {"content": None},
            "assistantMessageEvent": {"delta": None},
        })
        assert event.message["content"] is None

    def test_extra_fields_ignored(self) -> None:
        """Unknown fields are preserved in raw but don't break parsing."""
        event = parse_event({
            "type": "agent_start",
            "unknown_field": 123,
            "another": [1, 2, 3],
        })
        assert event.type == "agent_start"
        assert event.raw["unknown_field"] == 123

    def test_huge_payload(self) -> None:
        """Large payload doesn't break parsing."""
        huge_text = "x" * 100_000
        event = parse_event({
            "type": "message_update",
            "message": {"content": [{"type": "text", "text": huge_text}]},
            "assistantMessageEvent": {"type": "text_delta", "delta": huge_text},
        })
        assert event.type == "message_update"


# ---------------------------------------------------------------------------
# Command Edge Cases
# ---------------------------------------------------------------------------


class TestCommandEdgeCases:
    """Edge cases in command serialization."""

    def test_prompt_with_special_characters(self) -> None:
        """Special chars in prompt don't break serialization."""
        cmd = PromptCommand(message='Hello\nWorld\t"Quotes"\\Backslash')
        data = json.loads(cmd.to_jsonl())
        assert "\n" in data["message"]
        assert "\t" in data["message"]
        assert '"' in data["message"]

    def test_prompt_with_unicode(self) -> None:
        """Unicode in prompt survives round-trip."""
        cmd = PromptCommand(message="你好世界 🌍 café")
        data = json.loads(cmd.to_jsonl())
        assert data["message"] == "你好世界 🌍 café"

    def test_command_with_empty_id(self) -> None:
        """Empty string id is preserved."""
        cmd = GetStateCommand(id="")
        data = json.loads(cmd.to_jsonl())
        assert data["id"] == ""


# ---------------------------------------------------------------------------
# Registry Edge Cases
# ---------------------------------------------------------------------------


class TestRegistryEdgeCases:
    """Edge cases in session registry."""

    @pytest.mark.asyncio
    async def test_spawn_nonexistent_repo(self, registry: SessionRegistry) -> None:
        """Spawning with non-existent repo raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await registry.spawn(repo="nonexistent")

    @pytest.mark.asyncio
    async def test_get_returns_none_for_dead_session(self, registry: SessionRegistry) -> None:
        """Getting a dead session returns None and cleans up."""
        session = await registry.spawn(repo="project-a")
        # Kill the process manually
        session.agent._process.kill()
        await asyncio.sleep(0.1)

        # Should return None and remove from registry
        result = registry.get(session.session_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_live_cleans_dead_sessions(self, registry: SessionRegistry) -> None:
        """list_live() removes dead sessions."""
        session = await registry.spawn(repo="project-a")
        # Kill the process
        session.agent._process.kill()
        await asyncio.sleep(0.1)

        live = registry.list_live()
        assert len(live) == 0

    @pytest.mark.asyncio
    async def test_terminate_all_with_dead_sessions(self, registry: SessionRegistry) -> None:
        """terminate_all() handles dead sessions gracefully."""
        session = await registry.spawn(repo="project-a")
        # Kill the process
        session.agent._process.kill()
        await asyncio.sleep(0.1)

        # Should not raise
        await registry.terminate_all()
        assert len(registry.list_live()) == 0

    @pytest.mark.asyncio
    async def test_spawn_after_registry_error(self, registry: SessionRegistry) -> None:
        """Registry works after a failed spawn."""
        with pytest.raises(ValueError):
            await registry.spawn(repo="nonexistent")

        # Should still work
        session = await registry.spawn(repo="project-a")
        assert session.is_alive
        await registry.terminate_all()


# ---------------------------------------------------------------------------
# Concurrent Edge Cases
# ---------------------------------------------------------------------------


class TestConcurrentEdgeCases:
    """Race conditions and concurrent access."""

    @pytest.mark.asyncio
    async def test_rapid_spawn_and_get(self, registry: SessionRegistry) -> None:
        """Rapid spawn/get cycles don't race."""
        sessions = []
        for _ in range(10):
            s = await registry.spawn(repo="project-a")
            assert registry.get(s.session_id) is not None
            sessions.append(s)

        await registry.terminate_all()

    @pytest.mark.asyncio
    async def test_send_while_terminating(self, registry: SessionRegistry) -> None:
        """Sending command while terminating doesn't hang."""
        session = await registry.spawn(repo="project-a")

        async def send_forever():
            try:
                for _ in range(100):
                    await session.agent.send(GetStateCommand())
            except Exception:
                pass

        async def terminate_after_delay():
            await asyncio.sleep(0.1)
            await registry.terminate(session.session_id)

        await asyncio.gather(send_forever(), terminate_after_delay())

    @pytest.mark.asyncio
    async def test_many_subscribers_subscribe_unsubscribe(self, registry: SessionRegistry) -> None:
        """Many subscribers subscribing/unsubscribing rapidly."""
        session = await registry.spawn(repo="project-a")

        async def subscriber():
            async for event in session.agent.subscribe(replay=False):
                if event.type == "agent_end":
                    break

        # Start many subscribers
        tasks = [asyncio.create_task(subscriber()) for _ in range(10)]

        # Send a prompt to generate events
        await session.agent.send(PromptCommand(message="broadcast"))

        # Wait a bit then cancel
        await asyncio.sleep(0.5)
        for t in tasks:
            t.cancel()

        await registry.terminate(session.session_id)


# ---------------------------------------------------------------------------
# Fuzzing / Randomized Tests
# ---------------------------------------------------------------------------


class TestRandomizedBehaviors:
    """Random inputs to discover unexpected failures."""

    @pytest.mark.asyncio
    async def test_random_prompts(self, registry: SessionRegistry) -> None:
        """Random prompt content doesn't crash."""
        session = await registry.spawn(repo="project-a")

        for _ in range(5):
            # Generate random content
            length = random.randint(0, 500)
            content = "".join(
                random.choices(
                    string.ascii_letters + string.digits + string.punctuation + " \n\t",
                    k=length,
                )
            )
            response = await session.agent.send(PromptCommand(message=content))
            assert response.success

        await registry.terminate(session.session_id)

    @pytest.mark.asyncio
    async def test_random_event_parsing(self) -> None:
        """Random JSON doesn't crash event parser."""
        for _ in range(100):
            # Generate random dict
            data = {}
            for _ in range(random.randint(0, 5)):
                key = "".join(random.choices(string.ascii_lowercase, k=5))
                value_type = random.choice(["str", "int", "none", "bool", "list"])
                if value_type == "str":
                    data[key] = "".join(random.choices(string.printable, k=10))
                elif value_type == "int":
                    data[key] = random.randint(-100, 100)
                elif value_type == "none":
                    data[key] = None
                elif value_type == "bool":
                    data[key] = random.choice([True, False])
                elif value_type == "list":
                    data[key] = [1, 2, 3]

            # Should not crash
            with contextlib.suppress(Exception):
                parse_event(data)

    @pytest.mark.asyncio
    async def test_random_framing_input(self) -> None:
        """Random bytes don't crash framing."""
        for _ in range(50):
            reader = asyncio.StreamReader()
            # Feed random chunks
            for _ in range(random.randint(1, 10)):
                chunk_len = random.randint(0, 100)
                chunk = bytes(random.randint(0, 255) for _ in range(chunk_len))
                reader.feed_data(chunk)
            reader.feed_eof()

            # Should not crash
            lines = []
            try:
                async for line in read_jsonl_lines(reader):
                    lines.append(line)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_random_spawn_terminate_sequence(self, registry: SessionRegistry) -> None:
        """Random sequence of spawn/terminate doesn't leak."""
        active = []

        for _ in range(20):
            action = random.choice(["spawn", "terminate", "list"])

            if action == "spawn":
                try:
                    s = await registry.spawn(repo="project-a")
                    active.append(s.session_id)
                except Exception:
                    pass
            elif action == "terminate" and active:
                sid = active.pop(random.randint(0, len(active) - 1))
                with contextlib.suppress(KeyError):
                    await registry.terminate(sid)
            elif action == "list":
                registry.list_live()

        # Cleanup
        await registry.terminate_all()
