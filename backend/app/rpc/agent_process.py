"""AgentProcess — state machine wrapping a pi --mode rpc subprocess.

This is the core RPC plumbing that:
- Spawns and manages a pi subprocess
- Reads JSONL events from stdout
- Correlates responses by request id
- Broadcasts events to subscribers
- Maintains a ring buffer for late subscribers
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.rpc.framing import read_jsonl_lines
from app.rpc.types import (
    Command,
    Event,
    ResponseEvent,
    StateEvent,
    parse_event,
)

logger = logging.getLogger(__name__)

# Default ring buffer size
DEFAULT_BUFFER_SIZE = 200

# Default timeout for subprocess startup
STARTUP_TIMEOUT = 5.0

# Default timeout for graceful termination
TERMINATE_TIMEOUT = 3.0


class AgentProcessError(Exception):
    """Base exception for AgentProcess errors."""


class AgentProcess:
    """State machine wrapping a pi --mode rpc subprocess.

    Manages the lifecycle of a pi subprocess, providing:
    - Command sending with request/response correlation
    - Event streaming via async generators
    - Ring buffer for late subscriber replay
    """

    def __init__(
        self,
        process: asyncio.subprocess.Process,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
    ) -> None:
        """Initialize AgentProcess with a running subprocess.

        Args:
            process: The running asyncio subprocess.
            buffer_size: Number of events to keep in ring buffer.
        """
        self._process = process
        self._buffer_size = buffer_size

        # State
        self._session_id: str | None = None
        self._session_name: str | None = None

        # Request correlation
        self._next_id = 0
        self._pending: dict[str, asyncio.Future[ResponseEvent]] = {}

        # Event broadcasting
        self._subscribers: set[asyncio.Queue[Event | None]] = set()
        self._ring_buffer: deque[Event] = deque(maxlen=buffer_size)

        # Background task for reading stdout
        self._reader_task: asyncio.Task[None] | None = None

    @property
    def session_id(self) -> str | None:
        """The session ID assigned by pi."""
        return self._session_id

    @property
    def session_name(self) -> str | None:
        """The session name set via set_session_name."""
        return self._session_name

    @property
    def is_alive(self) -> bool:
        """Whether the subprocess is still running."""
        return self._process.returncode is None

    @classmethod
    async def start_detached(
        cls,
        cmd: list[str],
        cwd: str | None = None,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
    ) -> AgentProcess:
        """Start a pi subprocess without a context manager.

        Unlike start(), the caller is responsible for calling terminate().
        Use this when the process lifetime is managed by another object
        (e.g., SessionRegistry).

        Args:
            cmd: Command to execute (e.g., ["pi", "--mode", "rpc"]).
            cwd: Working directory for the subprocess.
            buffer_size: Number of events to keep in ring buffer.

        Returns:
            Initialized AgentProcess with RPC channel established.

        Raises:
            AgentProcessError: If subprocess fails to start or produce initial state.
        """
        logger.info("Starting agent process (detached): %s (cwd=%s)", cmd, cwd)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except Exception as e:
            raise AgentProcessError(f"Failed to start subprocess: {e}") from e

        proc = cls(process, buffer_size)

        # Start background reader
        proc._reader_task = asyncio.create_task(proc._read_stdout())

        # Wait for initial state event
        await asyncio.wait_for(proc._wait_for_initial_state(), STARTUP_TIMEOUT)

        return proc

    @classmethod
    @asynccontextmanager
    async def start(
        cls,
        cmd: list[str],
        cwd: str | None = None,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
    ) -> AsyncIterator[AgentProcess]:
        """Start a pi subprocess and yield an AgentProcess.

        The subprocess is automatically terminated when the context exits.

        Args:
            cmd: Command to execute (e.g., ["pi", "--mode", "rpc"]).
            cwd: Working directory for the subprocess.
            buffer_size: Number of events to keep in ring buffer.

        Yields:
            Initialized AgentProcess with RPC channel established.

        Raises:
            AgentProcessError: If subprocess fails to start or produce initial state.
        """
        proc = await cls.start_detached(cmd, cwd, buffer_size)
        try:
            yield proc
        finally:
            await proc.terminate()

    async def _wait_for_initial_state(self) -> None:
        """Wait until we receive the initial state event from pi."""
        while self._session_id is None:
            await asyncio.sleep(0.01)
            if not self.is_alive:
                raise AgentProcessError(
                    f"Subprocess exited before producing initial state "
                    f"(returncode={self._process.returncode})"
                )

    async def _read_stdout(self) -> None:
        """Background task: read JSONL events from stdout and process them."""
        assert self._process.stdout is not None

        try:
            async for line in read_jsonl_lines(self._process.stdout):
                try:
                    import json
                    raw = json.loads(line)
                    event = parse_event(raw)
                except Exception as e:
                    logger.warning("Failed to parse event: %s (line=%s)", e, line)
                    continue

                # Handle initial state event
                if isinstance(event, StateEvent):
                    self._session_id = event.session_id
                    self._session_name = event.session_name
                    logger.info(
                        "Session started: id=%s name=%s",
                        self._session_id,
                        self._session_name,
                    )
                    continue

                # Handle response events - correlate by id
                if isinstance(event, ResponseEvent) and event.id:
                    future = self._pending.pop(event.id, None)
                    if future and not future.done():
                        future.set_result(event)
                        continue

                # All other events go to ring buffer and subscribers
                self._ring_buffer.append(event)
                self._broadcast(event)

        except Exception as e:
            logger.error("stdout reader error: %s", e)
        finally:
            # Signal all subscribers that we're done
            for queue in self._subscribers:
                queue.put_nowait(None)

    def _broadcast(self, event: Event) -> None:
        """Send event to all active subscribers."""
        for queue in self._subscribers:
            queue.put_nowait(event)

    def _generate_id(self) -> str:
        """Generate a unique request ID."""
        self._next_id += 1
        return f"req-{self._next_id}"

    async def send(self, command: Command) -> ResponseEvent:
        """Send a command and wait for the correlated response.

        Args:
            command: The command to send. If command.id is not set, one is generated.

        Returns:
            The correlated ResponseEvent.

        Raises:
            AgentProcessError: If the subprocess is not running or write fails.
            asyncio.TimeoutError: If response is not received within timeout.
        """
        if not self.is_alive:
            raise AgentProcessError("Subprocess is not running")

        # Assign id if not set
        if command.id is None:
            command.id = self._generate_id()

        # Create future for response correlation
        future: asyncio.Future[ResponseEvent] = asyncio.get_event_loop().create_future()
        self._pending[command.id] = future

        # Send command
        assert self._process.stdin is not None
        try:
            data = command.to_jsonl() + "\n"
            self._process.stdin.write(data.encode("utf-8"))
            await self._process.stdin.drain()
        except Exception as e:
            self._pending.pop(command.id, None)
            raise AgentProcessError(f"Failed to write command: {e}") from e

        # Wait for response
        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except TimeoutError:
            self._pending.pop(command.id, None)
            raise

    async def subscribe(self, replay: bool = False) -> AsyncIterator[Event]:
        """Subscribe to the event stream.

        Args:
            replay: If True, replay ring buffer events first.

        Yields:
            Events as they arrive from pi. Yields None to signal stream end.
        """
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._subscribers.add(queue)

        try:
            # Replay ring buffer if requested
            if replay:
                for event in self._ring_buffer:
                    yield event

            # Stream new events
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self._subscribers.discard(queue)

    async def terminate(self) -> None:
        """Terminate the subprocess cleanly.

        Sends abort, closes stdin, waits for graceful exit, then force-kills.
        """
        if not self.is_alive:
            return

        logger.info("Terminating agent process (pid=%s)", self._process.pid)

        # Cancel reader task
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        # Try graceful shutdown
        try:
            # Send abort if stdin is still open
            if self._process.stdin and not self._process.stdin.is_closing():
                self._process.stdin.write(b'{"type":"abort"}\n')
                await self._process.stdin.drain()
                self._process.stdin.close()
        except Exception:
            pass

        # Wait for graceful exit
        try:
            await asyncio.wait_for(self._process.wait(), TERMINATE_TIMEOUT)
        except TimeoutError:
            logger.warning("Process did not exit gracefully, force-killing")
            self._process.kill()
            await self._process.wait()

        # Resolve any pending futures with cancellation
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        # Signal subscribers
        for queue in self._subscribers:
            queue.put_nowait(None)
        self._subscribers.clear()

        logger.info("Agent process terminated (returncode=%s)", self._process.returncode)

    async def __aenter__(self) -> AgentProcess:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit — terminates subprocess."""
        await self.terminate()
