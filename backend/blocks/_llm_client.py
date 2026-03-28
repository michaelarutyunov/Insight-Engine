"""Shared LLM client utility for all LLM-powered blocks.

This module provides a singleton AsyncAnthropic client with retry logic,
error handling, and convenience functions for text and JSON responses.
"""

import asyncio
import json
import os
from typing import Any

import anthropic
from anthropic import AsyncAnthropic


class BlockExecutionError(Exception):
    """Raised when a block fails during execution."""

    pass


class HITLSuspendSignal(Exception):
    """Raised by HITL blocks to signal execution should suspend for human input."""

    def __init__(self, checkpoint_data: dict) -> None:
        """Initialize the suspension signal with checkpoint data.

        Args:
            checkpoint_data: Dict containing data to present to the human reviewer
        """
        self.checkpoint_data = checkpoint_data
        super().__init__("HITL checkpoint reached - execution suspended")


# Module-level client singleton (lazy-initialized)
_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    """Get or create the singleton AsyncAnthropic client.

    Reads ANTHROPIC_API_KEY from environment.
    Raises BlockExecutionError if API key is missing.
    """
    global _client

    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise BlockExecutionError("ANTHROPIC_API_KEY environment variable is not set")
        _client = AsyncAnthropic(api_key=api_key)

    return _client


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.5,
    max_tokens: int = 4096,
) -> str:
    """Call the Anthropic API with retry logic and error handling.

    Args:
        system_prompt: System prompt for the LLM
        user_prompt: User prompt for the LLM
        model: Model identifier (default: claude-sonnet-4-6)
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens in response

    Returns:
        Text content from the LLM response

    Raises:
        BlockExecutionError: On API errors, auth failures, or rate limit exhaustion
    """
    client = _get_client()

    # Retry configuration for rate limits
    max_retries = 3
    base_delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            response = await client.messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract text content from response
            if not response.content:
                raise BlockExecutionError(f"LLM returned empty response for model {model}")

            # Return the first text block's content
            for block in response.content:
                if block.type == "text":
                    return block.text

            raise BlockExecutionError(f"LLM response contained no text blocks for model {model}")

        except anthropic.RateLimitError as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                delay = base_delay * (2**attempt)
                await asyncio.sleep(delay)
                continue
            else:
                raise BlockExecutionError(
                    f"Rate limit exceeded after {max_retries} retries: {e}"
                ) from e

        except anthropic.AuthenticationError as e:
            raise BlockExecutionError(f"Authentication failed for Anthropic API: {e}") from e

        except anthropic.APIError as e:
            raise BlockExecutionError(f"Anthropic API error occurred: {e}") from e

        except Exception as e:
            raise BlockExecutionError(f"Unexpected error calling LLM: {e}") from e

    # Should never reach here, but mypy needs it
    raise BlockExecutionError("Unexpected error in retry loop")


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.5,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call the Anthropic API and parse the response as JSON.

    Adds instruction to respond only with valid JSON.
    Raises BlockExecutionError if JSON parsing fails.

    Args:
        system_prompt: System prompt for the LLM
        user_prompt: User prompt for the LLM
        model: Model identifier (default: claude-sonnet-4-6)
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens in response

    Returns:
        Parsed JSON response as a dictionary

    Raises:
        BlockExecutionError: On API errors, auth failures, or JSON parsing failures
    """
    # Add JSON-only instruction to system prompt
    json_system_prompt = f"{system_prompt}\n\nRespond only with valid JSON. No markdown, no code blocks, no additional text."

    response_text = await call_llm(
        system_prompt=json_system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Attempt to parse JSON
    try:
        # Remove markdown code blocks if present (LLMs sometimes wrap JSON in ```json ... ```)
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove opening ```json or ```
            lines = cleaned.split("\n", 1)
            if len(lines) > 1:
                cleaned = lines[1]
            # Remove closing ```
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)

        if not isinstance(parsed, dict):
            raise BlockExecutionError(
                f"LLM JSON response is not a dictionary: {type(parsed).__name__}"
            )

        return parsed

    except json.JSONDecodeError as e:
        raise BlockExecutionError(
            f"Failed to parse LLM response as JSON: {e}\nResponse was: {response_text[:500]}"
        ) from e


def _reset_client() -> None:
    """Reset the singleton client.

    Only used in tests to ensure no global state leaks between test runs.
    """
    global _client
    _client = None
