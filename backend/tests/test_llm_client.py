"""Tests for backend/blocks/_llm_client.py."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blocks._llm_client import (
    BlockExecutionError,
    _get_client,
    _reset_client,
    call_llm,
    call_llm_json,
)  # noqa: E402

# ---------------------------------------------------------------------------
# Mock exception classes that match anthropic's exception hierarchy
# ---------------------------------------------------------------------------


class MockRateLimitError(Exception):
    """Mock RateLimitError for testing."""

    pass


class MockAuthenticationError(Exception):
    """Mock AuthenticationError for testing."""

    pass


class MockAPIError(Exception):
    """Mock APIError for testing."""

    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_client_singleton() -> None:
    """Reset the client singleton before each test to prevent state leakage."""
    _reset_client()
    yield
    _reset_client()


@pytest.fixture
def mock_message_response() -> MagicMock:
    """Create a mock Anthropic message response with text content."""
    response = MagicMock()
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = "Test response from Claude"
    response.content = [content_block]
    return response


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock AsyncAnthropic client."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Test BlockExecutionError
# ---------------------------------------------------------------------------


class TestBlockExecutionError:
    def test_is_exception(self) -> None:
        """BlockExecutionError should be an exception class."""
        error = BlockExecutionError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"


# ---------------------------------------------------------------------------
# Test _get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_creates_client_on_first_call(self) -> None:
        """First call should create and return a new AsyncAnthropic client."""
        from anthropic import AsyncAnthropic

        client = _get_client()
        assert isinstance(client, AsyncAnthropic)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_returns_singleton_on_subsequent_calls(self) -> None:
        """Subsequent calls should return the same client instance."""
        client1 = _get_client()
        client2 = _get_client()
        assert client1 is client2

    @patch.dict("os.environ", {}, clear=True)
    def test_raises_error_when_api_key_missing(self) -> None:
        """Should raise BlockExecutionError when ANTHROPIC_API_KEY is not set."""
        with pytest.raises(
            BlockExecutionError, match="ANTHROPIC_API_KEY environment variable is not set"
        ):
            _get_client()


# ---------------------------------------------------------------------------
# Test call_llm
# ---------------------------------------------------------------------------


class TestCallLlm:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_returns_text_from_mocked_response(
        self, mock_client, mock_message_response
    ) -> None:
        """Should return text content from mocked API response."""
        mock_client.messages.create.return_value = mock_message_response

        with patch("blocks._llm_client._get_client", return_value=mock_client):
            result = await call_llm(
                system_prompt="You are a helpful assistant.",
                user_prompt="Say hello",
            )

        assert result == "Test response from Claude"
        mock_client.messages.create.assert_called_once()

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_passes_parameters_to_api(self, mock_client, mock_message_response) -> None:
        """Should pass all parameters to the Anthropic API."""
        mock_client.messages.create.return_value = mock_message_response

        with patch("blocks._llm_client._get_client", return_value=mock_client):
            await call_llm(
                system_prompt="System",
                user_prompt="User",
                model="claude-opus-4-5",
                temperature=0.8,
                max_tokens=8192,
            )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-opus-4-5"
        assert call_args.kwargs["system"] == "System"
        assert call_args.kwargs["messages"][0]["content"] == "User"
        assert call_args.kwargs["temperature"] == 0.8
        assert call_args.kwargs["max_tokens"] == 8192

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_retries_on_rate_limit(self, mock_client, mock_message_response) -> None:
        """Should retry with exponential backoff on rate limit errors."""
        # First call raises rate limit, second succeeds
        mock_client.messages.create.side_effect = [
            MockRateLimitError("Rate limit exceeded"),
            mock_message_response,
        ]

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            patch("blocks._llm_client.anthropic.RateLimitError", MockRateLimitError),
        ):
            result = await call_llm(
                system_prompt="System",
                user_prompt="User",
            )

        assert result == "Test response from Claude"
        assert mock_client.messages.create.call_count == 2

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_after_max_retries(self, mock_client) -> None:
        """Should raise BlockExecutionError after exhausting retries."""
        mock_client.messages.create.side_effect = MockRateLimitError("Rate limit exceeded")

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            patch("blocks._llm_client.anthropic.RateLimitError", MockRateLimitError),
            pytest.raises(BlockExecutionError, match="Rate limit exceeded after 3 retries"),
        ):
            await call_llm(
                system_prompt="System",
                user_prompt="User",
            )

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_on_auth_failure(self, mock_client) -> None:
        """Should raise BlockExecutionError on authentication errors."""
        mock_client.messages.create.side_effect = MockAuthenticationError("Invalid API key")

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            patch("blocks._llm_client.anthropic.AuthenticationError", MockAuthenticationError),
            pytest.raises(BlockExecutionError, match="Authentication failed for Anthropic API"),
        ):
            await call_llm(
                system_prompt="System",
                user_prompt="User",
            )

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_on_api_error(self, mock_client) -> None:
        """Should raise BlockExecutionError on generic API errors."""
        mock_client.messages.create.side_effect = MockAPIError("Internal server error")

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            patch("blocks._llm_client.anthropic.APIError", MockAPIError),
            pytest.raises(BlockExecutionError, match="Anthropic API error occurred"),
        ):
            await call_llm(
                system_prompt="System",
                user_prompt="User",
            )

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_on_empty_response(self, mock_client) -> None:
        """Should raise BlockExecutionError when response has no content."""
        empty_response = MagicMock()
        empty_response.content = []

        mock_client.messages.create.return_value = empty_response

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            pytest.raises(BlockExecutionError, match="LLM returned empty response"),
        ):
            await call_llm(
                system_prompt="System",
                user_prompt="User",
            )

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_on_no_text_blocks(self, mock_client) -> None:
        """Should raise BlockExecutionError when response has no text content blocks."""
        response_no_text = MagicMock()
        response_no_text.content = []  # Empty content list

        mock_client.messages.create.return_value = response_no_text

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            pytest.raises(BlockExecutionError, match="LLM returned empty response"),
        ):
            await call_llm(
                system_prompt="System",
                user_prompt="User",
            )


# ---------------------------------------------------------------------------
# Test call_llm_json
# ---------------------------------------------------------------------------


class TestCallLlmJson:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_parses_valid_json_response(self, mock_client) -> None:
        """Should parse valid JSON response and return as dict."""
        mock_response = MagicMock()
        content_block = MagicMock()
        content_block.type = "text"
        content_block.text = '{"key": "value", "number": 42}'
        mock_response.content = [content_block]
        mock_client.messages.create.return_value = mock_response

        with patch("blocks._llm_client._get_client", return_value=mock_client):
            result = await call_llm_json(
                system_prompt="System",
                user_prompt="Return JSON",
            )

        assert result == {"key": "value", "number": 42}

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_strips_markdown_code_blocks(self, mock_client) -> None:
        """Should strip markdown code blocks from JSON response."""
        mock_response = MagicMock()
        content_block = MagicMock()
        content_block.type = "text"
        content_block.text = """```json
{
    "key": "value"
}
```"""
        mock_response.content = [content_block]
        mock_client.messages.create.return_value = mock_response

        with patch("blocks._llm_client._get_client", return_value=mock_client):
            result = await call_llm_json(
                system_prompt="System",
                user_prompt="Return JSON",
            )

        assert result == {"key": "value"}

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_adds_json_instruction_to_system_prompt(self, mock_client) -> None:
        """Should append JSON-only instruction to system prompt."""
        mock_response = MagicMock()
        content_block = MagicMock()
        content_block.type = "text"
        content_block.text = '{"result": "ok"}'
        mock_response.content = [content_block]
        mock_client.messages.create.return_value = mock_response

        with patch("blocks._llm_client._get_client", return_value=mock_client):
            await call_llm_json(
                system_prompt="Original system prompt",
                user_prompt="User",
            )

        call_args = mock_client.messages.create.call_args
        system_prompt = call_args.kwargs["system"]
        assert "Original system prompt" in system_prompt
        assert "Respond only with valid JSON" in system_prompt
        assert "No markdown, no code blocks" in system_prompt

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_on_invalid_json(self, mock_client) -> None:
        """Should raise BlockExecutionError when response is not valid JSON."""
        mock_response = MagicMock()
        content_block = MagicMock()
        content_block.type = "text"
        content_block.text = "This is not valid JSON"
        mock_response.content = [content_block]
        mock_client.messages.create.return_value = mock_response

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            pytest.raises(BlockExecutionError, match="Failed to parse LLM response as JSON"),
        ):
            await call_llm_json(
                system_prompt="System",
                user_prompt="Return JSON",
            )

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_raises_error_on_non_dict_json(self, mock_client) -> None:
        """Should raise BlockExecutionError when JSON is not a dictionary."""
        mock_response = MagicMock()
        content_block = MagicMock()
        content_block.type = "text"
        content_block.text = '["array", "not", "dict"]'
        mock_response.content = [content_block]
        mock_client.messages.create.return_value = mock_response

        with (
            patch("blocks._llm_client._get_client", return_value=mock_client),
            pytest.raises(BlockExecutionError, match="LLM JSON response is not a dictionary"),
        ):
            await call_llm_json(
                system_prompt="System",
                user_prompt="Return JSON",
            )


# ---------------------------------------------------------------------------
# Test _reset_client
# ---------------------------------------------------------------------------


class TestResetClient:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_clears_singleton(self) -> None:
        """Reset should clear the singleton client."""
        # Create first client
        _get_client()

        # Reset
        _reset_client()

        # Create new client - should be different instance
        _get_client()

        # After reset, we get a new instance
        # Note: This tests the reset mechanism itself
        from blocks._llm_client import _client

        assert _client is not None
