"""Tests for app.rpc.framing — JSONL line splitting."""

import asyncio

import pytest

from app.rpc.framing import read_jsonl_lines


async def _make_stream(data: bytes, limit: int = 2**20) -> asyncio.StreamReader:
    """Create a StreamReader from bytes with specified buffer limit."""
    reader = asyncio.StreamReader(limit=limit)
    reader.feed_data(data)
    reader.feed_eof()
    return reader


async def _collect_lines(data: bytes) -> list[str]:
    """Helper: feed data through framing and collect all lines."""
    reader = await _make_stream(data)
    return [line async for line in read_jsonl_lines(reader)]


class TestReadJsonlLines:
    """read_jsonl_lines splits on LF only, strips trailing CR."""

    @pytest.mark.asyncio
    async def test_should_split_on_newline(self) -> None:
        """Lines separated by \\n are yielded individually."""
        data = b'{"a":1}\n{"b":2}\n'
        lines = await _collect_lines(data)
        assert lines == ['{"a":1}', '{"b":2}']

    @pytest.mark.asyncio
    async def test_should_strip_trailing_cr(self) -> None:
        """Lines with \\r\\n are yielded without the trailing \\r."""
        data = b'{"a":1}\r\n{"b":2}\r\n'
        lines = await _collect_lines(data)
        assert lines == ['{"a":1}', '{"b":2}']

    @pytest.mark.asyncio
    async def test_should_handle_empty_input(self) -> None:
        """Empty input yields no lines."""
        data = b""
        lines = await _collect_lines(data)
        assert lines == []

    @pytest.mark.asyncio
    async def test_should_skip_empty_lines(self) -> None:
        """Empty lines between records are skipped."""
        data = b'{"a":1}\n\n{"b":2}\n'
        lines = await _collect_lines(data)
        assert lines == ['{"a":1}', '{"b":2}']

    @pytest.mark.asyncio
    async def test_should_handle_line_without_trailing_newline(self) -> None:
        """Last line without trailing newline is still yielded."""
        data = b'{"a":1}\n{"b":2}'
        lines = await _collect_lines(data)
        assert lines == ['{"a":1}', '{"b":2}']

    @pytest.mark.asyncio
    async def test_should_not_split_on_unicode_line_separator(self) -> None:
        """U+2028 inside JSON string is NOT treated as a line break."""
        # {"text":"line1\u2028line2"} should be one line
        inner = '{"text":"line1\u2028line2"}'
        data = inner.encode("utf-8") + b"\n"
        lines = await _collect_lines(data)
        assert len(lines) == 1
        assert "\u2028" in lines[0]

    @pytest.mark.asyncio
    async def test_should_handle_partial_reads(self) -> None:
        """Framing works when data arrives in chunks."""
        reader = asyncio.StreamReader()
        # Feed partial line
        reader.feed_data(b'{"par')
        reader.feed_data(b'tial":1}\n')
        reader.feed_eof()
        lines = [line async for line in read_jsonl_lines(reader)]
        assert lines == ['{"partial":1}']

    @pytest.mark.asyncio
    async def test_should_handle_large_payload(self) -> None:
        """Framing handles lines larger than typical buffer sizes."""
        large_obj = '{"data":"' + "x" * 100_000 + '"}'
        data = large_obj.encode("utf-8") + b"\n"
        lines = await _collect_lines(data)
        assert len(lines) == 1
        assert len(lines[0]) == len(large_obj)
