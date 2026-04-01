"""Tests for the chat assistant and chat API endpoint.

Tests:
1. Unit tests for stream_chat function in chat/assistant.py
2. Integration tests for POST /api/v1/chat with mocked Anthropic client.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from chat.assistant import stream_chat
from main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect the database to a temp file so tests are isolated."""
    import storage.sqlite as mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(mod, "_DB_PATH", tmp_db)


@pytest.fixture
def client():
    """Provide an async httpx client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


def _make_stream_response(text_chunks: list[str]):
    """Create a mock Anthropic stream that yields text chunks."""

    class FakeStream:
        def __init__(self, chunks):
            self._chunks = chunks

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def text_stream(self):
            return self._async_iter()

        async def _async_iter(self):
            for chunk in self._chunks:
                yield chunk

    return FakeStream(text_chunks)


# ---------------------------------------------------------------------------
# Unit tests for stream_chat
# ---------------------------------------------------------------------------
class TestStreamChat:
    @pytest.mark.asyncio
    async def test_yields_token_chunks(self):
        """stream_chat yields JSON-encoded token chunks."""
        fake_stream = _make_stream_response(["Hello", " world"])
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = fake_stream
        with patch("chat.assistant._get_client", return_value=mock_client):
            chunks = []
            async for chunk in stream_chat("test message"):
                chunks.append(chunk)
        assert len(chunks) == 3  # 2 tokens + 1 done
        token1 = json.loads(chunks[0])
        assert token1["type"] == "token"
        assert token1["content"] == "Hello"
        token2 = json.loads(chunks[1])
        assert token2["type"] == "token"
        assert token2["content"] == " world"
        done = json.loads(chunks[2])
        assert done["type"] == "done"

    @pytest.mark.asyncio
    async def test_yields_error_on_api_failure(self):
        """stream_chat yields an error chunk when the Anthropic API fails."""
        import anthropic

        from chat.assistant import stream_chat

        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = anthropic.APIError(
            message="Rate limited",
            request=MagicMock(),
            body=None,
        )
        with patch("chat.assistant._get_client", return_value=mock_client):
            chunks = []
            async for chunk in stream_chat("test message"):
                chunks.append(chunk)
        assert len(chunks) == 1
        error = json.loads(chunks[0])
        assert error["type"] == "error"

    @pytest.mark.asyncio
    async def test_yields_error_on_unexpected_exception(self):
        """stream_chat yields an error chunk on unexpected exceptions."""
        from chat.assistant import stream_chat

        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = RuntimeError("Unexpected")
        with patch("chat.assistant._get_client", return_value=mock_client):
            chunks = []
            async for chunk in stream_chat("test message"):
                chunks.append(chunk)
        assert len(chunks) == 1
        error = json.loads(chunks[0])
        assert error["type"] == "error"
        assert "Unexpected" in error["content"]


# ---------------------------------------------------------------------------
# Integration tests for POST /api/v1/chat
# ---------------------------------------------------------------------------
class TestChatEndpoint:
    @pytest.mark.asyncio
    async def test_chat_endpoint_returns_sse(self, client):
        """POST /api/v1/chat returns a streaming response with SSE chunks."""
        fake_stream = _make_stream_response(["Test response"])
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = fake_stream
        with patch("chat.assistant._get_client", return_value=mock_client):
            response = await client.post(
                "/api/v1/chat",
                json={"message": "Hello"},
            )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        body = response.text
        assert "token" in body
        assert "done" in body

    @pytest.mark.asyncio
    async def test_chat_endpoint_rejects_empty_message(self, client):
        """POST /api/v1/chat rejects an empty message."""
        response = await client.post(
            "/api/v1/chat",
            json={"message": ""},
        )
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_chat_endpoint_rejects_missing_message(self, client):
        """POST /api/v1/chat rejects missing message field."""
        response = await client.post(
            "/api/v1/chat",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_endpoint_with_pipeline_id(self, client):
        """POST /api/v1/chat accepts pipeline_id and includes context."""
        fake_stream = _make_stream_response(["Response with pipeline context"])
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = fake_stream
        with (
            patch("chat.assistant._get_client", return_value=mock_client),
            patch("chat.assistant.get_pipeline", new=AsyncMock(return_value=None)),
        ):
            response = await client.post(
                "/api/v1/chat",
                json={"message": "Test", "pipeline_id": "nonexistent-id"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_sse_chunks_are_valid_json(self, client):
        """Each SSE chunk from the chat endpoint is valid JSON with required fields."""
        fake_stream = _make_stream_response(["chunk1", "chunk2"])
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = fake_stream
        with patch("chat.assistant._get_client", return_value=mock_client):
            response = await client.post(
                "/api/v1/chat",
                json={"message": "Hello"},
            )
        body = response.text
        # Split by newlines (SSE format) and parse each non-empty line
        lines = [line.strip() for line in body.split("\n") if line.strip()]
        for line in lines:
            data = json.loads(line)
            assert "type" in data
            assert "content" in data
            assert data["type"] in ("token", "done", "error")
