"""Tests for IntegrationMixin (Step 4 of block taxonomy refactor).

Covers acceptance criteria:
1. IntegrationMixin and 3 exception classes exist in blocks/integration.py.
2. call_external uses httpx with exponential backoff.
3. MRO: SourceBase + IntegrationMixin has no conflicts.
4. ruff check passes.
5. All existing tests pass.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blocks.base import SourceBase
from blocks.integration import (
    IntegrationError,
    IntegrationMixin,
    IntegrationRateLimitError,
    IntegrationTimeoutError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeIntegrationSource(SourceBase, IntegrationMixin):
    """Minimal Source block that uses IntegrationMixin for testing."""

    @property
    def block_type(self) -> str:
        return "source"

    @property
    def input_schemas(self) -> list[str]:
        return []

    @property
    def output_schemas(self) -> list[str]:
        return ["generic_blob"]

    @property
    def config_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def description(self) -> str:
        return "Fake integration source for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    @property
    def service_name(self) -> str:
        return "Fake External Service"

    @property
    def estimated_latency(self) -> str:
        return "fast"

    @property
    def cost_per_call(self) -> dict:
        return {"unit": "USD", "estimate": 0.01, "basis": "per_call"}

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        return {"data": []}

    def test_fixtures(self) -> dict:
        return {
            "inputs": {},
            "config": {},
            "outputs": {"data": []},
        }


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Test IntegrationError exception hierarchy."""

    def test_error_is_exception(self):
        assert issubclass(IntegrationError, Exception)

    def test_timeout_is_integration_error(self):
        assert issubclass(IntegrationTimeoutError, IntegrationError)

    def test_rate_limit_is_integration_error(self):
        assert issubclass(IntegrationRateLimitError, IntegrationError)

    def test_rate_limit_carries_retry_after(self):
        err = IntegrationRateLimitError("rate limited", retry_after=3.0)
        assert err.retry_after == 3.0

    def test_rate_limit_default_retry_after_is_none(self):
        err = IntegrationRateLimitError("rate limited")
        assert err.retry_after is None


# ---------------------------------------------------------------------------
# Mixin properties
# ---------------------------------------------------------------------------


class TestMixinProperties:
    """Test IntegrationMixin properties on a concrete subclass."""

    def test_is_external_service(self):
        source = _FakeIntegrationSource()
        assert source.is_external_service is True

    def test_service_name(self):
        source = _FakeIntegrationSource()
        assert source.service_name == "Fake External Service"

    def test_estimated_latency(self):
        source = _FakeIntegrationSource()
        assert source.estimated_latency == "fast"

    def test_cost_per_call(self):
        source = _FakeIntegrationSource()
        assert source.cost_per_call == {
            "unit": "USD",
            "estimate": 0.01,
            "basis": "per_call",
        }

    def test_defaults_on_bare_mixin(self):
        mixin = IntegrationMixin()
        assert mixin.is_external_service is True
        assert mixin.estimated_latency is None
        assert mixin.cost_per_call is None

    def test_service_name_not_implemented_on_bare_mixin(self):
        mixin = IntegrationMixin()
        with pytest.raises(NotImplementedError):
            _ = mixin.service_name


# ---------------------------------------------------------------------------
# get_credentials
# ---------------------------------------------------------------------------


class TestGetCredentials:
    """Test credential extraction from config."""

    def test_extracts_credential_prefixed_keys(self):
        source = _FakeIntegrationSource()
        creds = source.get_credentials(
            {
                "credential_api_key": "secret123",
                "credential_api_secret": "super_secret",
                "other_setting": "not_a_credential",
            }
        )
        assert creds == {"api_key": "secret123", "api_secret": "super_secret"}

    def test_empty_config_returns_empty(self):
        source = _FakeIntegrationSource()
        assert source.get_credentials({}) == {}

    def test_no_credential_keys_returns_empty(self):
        source = _FakeIntegrationSource()
        assert source.get_credentials({"foo": "bar"}) == {}


# ---------------------------------------------------------------------------
# MRO compatibility
# ---------------------------------------------------------------------------


class TestMROCompatibility:
    """Test that SourceBase + IntegrationMixin has no MRO conflicts."""

    def test_instance_creation(self):
        source = _FakeIntegrationSource()
        assert source.block_type == "source"
        assert source.is_external_service is True

    def test_mro_order(self):
        mro = _FakeIntegrationSource.__mro__
        source_idx = mro.index(SourceBase)
        mixin_idx = mro.index(IntegrationMixin)
        assert source_idx < mixin_idx

    def test_source_methods_available(self):
        source = _FakeIntegrationSource()
        assert hasattr(source, "block_type")
        assert hasattr(source, "input_schemas")
        assert hasattr(source, "output_schemas")
        assert hasattr(source, "validate_config")
        assert hasattr(source, "execute")

    def test_mixin_methods_available(self):
        source = _FakeIntegrationSource()
        assert hasattr(source, "call_external")
        assert hasattr(source, "poll_for_result")
        assert hasattr(source, "get_credentials")
        assert hasattr(source, "service_name")
        assert hasattr(source, "is_external_service")
        assert hasattr(source, "estimated_latency")
        assert hasattr(source, "cost_per_call")


# ---------------------------------------------------------------------------
# call_external — success
# ---------------------------------------------------------------------------


class TestCallExternalSuccess:
    """Test call_external with a successful HTTP response."""

    @pytest.mark.asyncio
    async def test_success(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "ok", "result": [1, 2, 3]}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("blocks.integration.httpx.AsyncClient", return_value=mock_client):
            result = await source.call_external("https://api.example.com/data")

        assert result == {"status": "ok", "result": [1, 2, 3]}
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_method_and_payload(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 42}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("blocks.integration.httpx.AsyncClient", return_value=mock_client):
            result = await source.call_external(
                "https://api.example.com/data",
                method="PUT",
                payload={"key": "value"},
                headers={"X-Custom": "yes"},
            )

        assert result == {"id": 42}
        mock_client.request.assert_called_once_with(
            method="PUT",
            url="https://api.example.com/data",
            json={"key": "value"},
            headers={"Content-Type": "application/json", "X-Custom": "yes"},
        )


# ---------------------------------------------------------------------------
# call_external — retry on timeout
# ---------------------------------------------------------------------------


class TestCallExternalRetryOnTimeout:
    """Test call_external retries on timeout with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                mock_response,
            ]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
            patch("blocks.integration.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await source.call_external("https://api.example.com/data", retries=3)

        assert result == {"status": "ok"}
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        source = _FakeIntegrationSource()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
            patch("blocks.integration.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(IntegrationTimeoutError, match="timed out"),
        ):
            await source.call_external("https://api.example.com/data", retries=2)

        assert mock_client.request.call_count == 2


# ---------------------------------------------------------------------------
# call_external — retry on server error (5xx)
# ---------------------------------------------------------------------------


class TestCallExternalRetryOnServerError:
    """Test call_external retries on 500 errors with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retries_on_500(self):
        source = _FakeIntegrationSource()
        error_response = MagicMock()
        error_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=error_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
            patch("blocks.integration.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(IntegrationError, match="server error"):
                await source.call_external("https://api.example.com/data", retries=3)

        assert mock_client.request.call_count == 3


# ---------------------------------------------------------------------------
# call_external — retry on rate limit (429)
# ---------------------------------------------------------------------------


class TestCallExternalRetryOnRateLimit:
    """Test call_external retries on 429 with Retry-After header."""

    @pytest.mark.asyncio
    async def test_retries_on_429_with_retry_after(self):
        source = _FakeIntegrationSource()
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {"retry-after": "0.1"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Too Many Requests",
                request=MagicMock(),
                response=error_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
            patch("blocks.integration.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(IntegrationRateLimitError, match="Rate limited by") as exc_info,
        ):
            await source.call_external("https://api.example.com/data", retries=3)

        assert exc_info.value.retry_after == 0.1
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_429_without_retry_after(self):
        source = _FakeIntegrationSource()
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Too Many Requests",
                request=MagicMock(),
                response=error_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
            patch("blocks.integration.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(IntegrationRateLimitError):
                await source.call_external("https://api.example.com/data", retries=2)


# ---------------------------------------------------------------------------
# call_external — non-retryable client error (4xx, not 429)
# ---------------------------------------------------------------------------


class TestCallExternalNonRetryableClientError:
    """Test call_external raises IntegrationError immediately on 4xx."""

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self):
        source = _FakeIntegrationSource()
        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=error_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("blocks.integration.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(IntegrationError, match="client error"):
                await source.call_external("https://api.example.com/data")

        # Should fail immediately — only one attempt
        assert mock_client.request.call_count == 1


# ---------------------------------------------------------------------------
# poll_for_result
# ---------------------------------------------------------------------------


class TestPollForResultCompleted:
    """Test poll_for_result returns when job completes."""

    @pytest.mark.asyncio
    async def test_completed_status(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "completed", "result": "done"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("blocks.integration.httpx.AsyncClient", return_value=mock_client):
            result = await source.poll_for_result(
                "https://api.example.com/jobs/1",
                poll_interval=0,
                max_wait=10,
            )

        assert result == {"status": "completed", "result": "done"}

    @pytest.mark.asyncio
    async def test_succeeded_status(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "succeeded", "data": [1]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("blocks.integration.httpx.AsyncClient", return_value=mock_client):
            result = await source.poll_for_result(
                "https://api.example.com/jobs/1",
                poll_interval=0,
                max_wait=10,
            )

        assert result == {"status": "succeeded", "data": [1]}


class TestPollForResultFailed:
    """Test poll_for_result raises IntegrationError on job failure."""

    @pytest.mark.asyncio
    async def test_failed_status(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "failed", "error": "oops"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
        ):
            with pytest.raises(IntegrationError, match="failure status"):
                await source.poll_for_result(
                    "https://api.example.com/jobs/1",
                    poll_interval=0,
                    max_wait=10,
                )


class TestPollForResultTimeout:
    """Test poll_for_result raises IntegrationTimeoutError on timeout."""

    @pytest.mark.asyncio
    async def test_timeout(self):
        source = _FakeIntegrationSource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "pending"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("blocks.integration.httpx.AsyncClient", return_value=mock_client),
            patch("blocks.integration.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(IntegrationTimeoutError, match="did not complete"):
                await source.poll_for_result(
                    "https://api.example.com/jobs/1",
                    poll_interval=1,
                    max_wait=2,
                )
