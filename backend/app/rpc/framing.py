"""JSONL framing for the pi RPC protocol.

Protocol rules (from pi docs):
- Split records on LF (\\n) only
- Accept optional \\r\\n input by stripping a trailing \\r
- Do NOT use generic line readers that treat Unicode separators (U+2028, U+2029) as newlines

This module uses asyncio.StreamReader.readline() which splits on \\n only,
making it protocol-compliant.
"""

import asyncio
from collections.abc import AsyncGenerator

# Default buffer limit: 1MB. pi can send large tool results.
DEFAULT_LIMIT = 1_048_576


async def read_jsonl_lines(
    reader: asyncio.StreamReader, limit: int = DEFAULT_LIMIT
) -> AsyncGenerator[str]:
    """Async generator that yields complete JSONL lines from a stream.

    Reads from the stream line-by-line, stripping trailing \\r and skipping
    empty lines. The stream is consumed until EOF.

    Args:
        reader: An asyncio.StreamReader (typically from subprocess stdout).
        limit: Maximum line length in bytes (default 1MB).

    Yields:
        Non-empty lines with trailing whitespace stripped.

    Note:
        Uses readline() which splits on \\n only — compliant with pi RPC spec.
        Does NOT use generic line readers that split on Unicode separators.
    """
    while True:
        line = await reader.readline()
        if not line:
            # EOF reached
            break

        # Decode bytes to string, strip trailing whitespace
        decoded = line.decode("utf-8").rstrip("\r\n")

        # Skip empty lines
        if not decoded:
            continue

        yield decoded
