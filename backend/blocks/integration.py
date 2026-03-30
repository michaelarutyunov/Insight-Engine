"""Integration mixin for blocks that call external services.

Provides common infrastructure for API-backed blocks: credential management,
HTTP calls with exponential backoff, and long-running job polling.

IntegrationMixin is a mixin class — it does NOT affect block_type. A block
using this mixin is still an Analysis, Transform, Source, etc. from the
engine's perspective.
"""

import asyncio
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class IntegrationError(Exception):
    """Raised when an external service call fails after exhausting retries."""

    pass


class IntegrationTimeoutError(IntegrationError):
    """Raised when an external service call times out after all retries."""

    pass


class IntegrationRateLimitError(IntegrationError):
    """Raised when an external service returns a rate-limit response (429).

    Carries the ``retry_after`` value (seconds) when the service provides one.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------


class IntegrationMixin:
    """Mixin for blocks that call external services.

    Provides common infrastructure for API-backed blocks. Inherit alongside
    a type-specific base class (e.g. ``SourceBase``, ``AnalysisBase``).

    Usage::

        class CintSampleSource(SourceBase, IntegrationMixin):
            @property
            def service_name(self) -> str:
                return "Cint Sample Exchange"
            ...
    """

    # -- Properties ----------------------------------------------------------

    @property
    def is_external_service(self) -> bool:
        """Always True for IntegrationMixin blocks.

        Exposed in block registry metadata for execution planning.
        """
        return True

    @property
    def service_name(self) -> str:
        """Human-readable name of the external service.

        Example: ``'Cint Sample Exchange'``, ``'Amazon Reviews API'``
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement service_name")

    @property
    def estimated_latency(self) -> str | None:
        """Expected response time category for execution planning.

        Returns one of: ``'fast'`` (<5s), ``'moderate'`` (5-60s),
        ``'slow'`` (1-10min), ``'async'`` (>10min, requires polling).
        Returns None when latency is not meaningfully estimable.
        """
        return None

    @property
    def cost_per_call(self) -> dict[str, Any] | None:
        """Optional cost metadata for execution planning.

        Example::

            {'unit': 'USD', 'estimate': 0.02, 'basis': 'per_row'}

        Returns None if free or cost is not meaningfully estimable.
        """
        return None

    # -- Credential helpers --------------------------------------------------

    def get_credentials(self, config: dict) -> dict[str, str]:
        """Retrieve credentials for the external service from block config.

        Default implementation reads config keys prefixed with ``credential_``.
        Override for custom credential resolution (env vars, vault, etc.).

        Args:
            config: Block configuration dict.

        Returns:
            Dict mapping credential names (without prefix) to their values.
        """
        return {
            k.removeprefix("credential_"): v
            for k, v in config.items()
            if k.startswith("credential_")
        }

    # -- HTTP client ---------------------------------------------------------

    async def call_external(
        self,
        endpoint: str,
        method: str = "POST",
        payload: dict | None = None,
        headers: dict | None = None,
        timeout: int = 30,
        retries: int = 3,
    ) -> dict[str, Any]:
        """HTTP call with exponential backoff, retry logic, and error normalization.

        Blocks should call this instead of using httpx directly.

        Args:
            endpoint: Full URL to call.
            method: HTTP method (default ``POST``).
            payload: JSON body for the request.
            headers: Additional HTTP headers.
            timeout: Per-request timeout in seconds.
            retries: Maximum number of retry attempts.

        Returns:
            Parsed JSON response body.

        Raises:
            IntegrationTimeoutError: On timeout after all retries exhausted.
            IntegrationRateLimitError: On persistent 429 responses.
            IntegrationError: On non-retryable HTTP failures.
        """
        base_delay: float = 1.0  # seconds

        merged_headers: dict[str, str] = {
            "Content-Type": "application/json",
            **(headers or {}),
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(retries):
                try:
                    response = await client.request(
                        method=method.upper(),
                        url=endpoint,
                        json=payload,
                        headers=merged_headers,
                    )
                    response.raise_for_status()
                    return response.json()

                except httpx.TimeoutException as exc:
                    # Timeouts are always retryable

                    if attempt < retries - 1:
                        delay = base_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    raise IntegrationTimeoutError(
                        f"External service {self.service_name!r} timed out "
                        f"after {retries} retries ({endpoint})"
                    ) from exc

                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code == 429:
                        # Parse Retry-After header if present
                        retry_after_raw = exc.response.headers.get("retry-after")
                        retry_after: float | None = None
                        if retry_after_raw is not None:
                            try:
                                retry_after = float(retry_after_raw)
                            except ValueError:
                                retry_after = None

                        if attempt < retries - 1:
                            wait = retry_after if retry_after else base_delay * (2**attempt)
                            await asyncio.sleep(wait)
                            continue

                        raise IntegrationRateLimitError(
                            f"Rate limited by {self.service_name!r} after "
                            f"{retries} retries ({endpoint})",
                            retry_after=retry_after,
                        ) from exc

                    if status_code >= 500:
                        # Server errors are retryable
                        if attempt < retries - 1:
                            delay = base_delay * (2**attempt)
                            await asyncio.sleep(delay)
                            continue
                        raise IntegrationError(
                            f"External service {self.service_name!r} returned "
                            f"server error {status_code} after {retries} "
                            f"retries ({endpoint})"
                        ) from exc

                    # Client errors (4xx except 429) are not retryable
                    raise IntegrationError(
                        f"External service {self.service_name!r} returned "
                        f"client error {status_code}: "
                        f"{exc.response.text[:500]} ({endpoint})"
                    ) from exc

                except httpx.RequestError as exc:
                    if attempt < retries - 1:
                        delay = base_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    raise IntegrationError(
                        f"Request to {self.service_name!r} failed: {exc} ({endpoint})"
                    ) from exc

        # Safety net — should not be reachable
        raise IntegrationError(f"Unexpected failure calling {self.service_name!r} ({endpoint})")

    # -- Polling -------------------------------------------------------------

    async def poll_for_result(
        self,
        job_url: str,
        poll_interval: int = 5,
        max_wait: int = 600,
        headers: dict | None = None,
    ) -> dict[str, Any]:
        """Poll a long-running external job until completion.

        Used for async API patterns where the service returns a job URL that
        must be polled until a terminal state is reached.

        Args:
            job_url: URL to poll for job status.
            poll_interval: Seconds between polls (default 5).
            max_wait: Maximum total wait time in seconds (default 600).
            headers: Additional HTTP headers for poll requests.

        Returns:
            Final job result as a parsed JSON dict.

        Raises:
            IntegrationTimeoutError: If the job does not complete within
                *max_wait* seconds.
            IntegrationError: If the job reports a failure status.
        """
        elapsed: float = 0.0

        async with httpx.AsyncClient(timeout=30) as client:
            while elapsed < max_wait:
                try:
                    response = await client.get(
                        job_url,
                        headers=headers or {},
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise IntegrationError(
                        f"Poll request to {self.service_name!r} failed: {exc}"
                    ) from exc

                data = response.json()
                status = data.get("status", "").lower()

                if status in ("complete", "completed", "done", "succeeded", "success"):
                    return data

                if status in ("failed", "error", "cancelled"):
                    raise IntegrationError(
                        f"External job at {self.service_name!r} reported "
                        f"failure status '{status}': {data}"
                    )

                # Job still pending/in-progress — wait and retry
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

        raise IntegrationTimeoutError(
            f"External job at {self.service_name!r} did not complete within {max_wait}s ({job_url})"
        )
