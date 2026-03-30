"""API Push Sink block -- POSTs pipeline output to a configurable HTTP endpoint."""

from typing import Any

from blocks.base import SinkBase
from blocks.integration import IntegrationMixin
from schemas.data_objects import DATA_TYPES


class ApiPushSink(SinkBase, IntegrationMixin):
    """Terminal block that pushes pipeline output to an external HTTP endpoint.

    Accepts any data type from the edge vocabulary and forwards it as a JSON
    payload to a user-configured URL via POST or PUT. Supports optional
    authentication (bearer token or API key) and custom headers.
    """

    @property
    def service_name(self) -> str:
        return "External API"

    @property
    def estimated_latency(self) -> str:
        return "moderate"

    @property
    def input_schemas(self) -> list[str]:
        return sorted(DATA_TYPES)

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "endpoint_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "Target HTTP URL to push data to (required)",
                },
                "method": {
                    "type": "string",
                    "enum": ["POST", "PUT"],
                    "default": "POST",
                    "description": "HTTP method to use (POST or PUT)",
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Additional HTTP headers to include in the request",
                },
                "auth_type": {
                    "type": "string",
                    "enum": ["none", "bearer", "api_key"],
                    "default": "none",
                    "description": "Authentication method: none, bearer (Authorization: Bearer <token>), or api_key (X-API-Key header)",
                },
                "auth_value": {
                    "type": "string",
                    "description": "Authentication credential value (bearer token or API key). Required when auth_type is not 'none'.",
                },
            },
            "required": ["endpoint_url"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Pushes pipeline output to an external HTTP endpoint. Use this sink "
            "when you need to forward research results to webhooks, REST APIs, "
            "or any HTTP-based downstream system. Supports POST and PUT methods "
            "with optional bearer token or API key authentication."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Assumes the target endpoint accepts JSON payloads and returns a "
            "success status code (2xx). The entire input data object is forwarded "
            "as the request body. For large payloads, ensure the target service "
            "can handle the request size. Network failures are retried with "
            "exponential backoff (up to 3 retries by default). Consider endpoint "
            "idempotency when using PUT -- repeated pipeline runs will send "
            "identical payloads. Sensitive auth values should be supplied via "
            "environment variables or a secrets manager, not hardcoded in "
            "pipeline configs."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "sink",
            "export",
            "webhook",
            "http",
            "api",
            "integration",
            "push",
            "external",
        ]

    def validate_config(self, config: dict) -> bool:
        endpoint_url = config.get("endpoint_url")
        if not isinstance(endpoint_url, str) or not endpoint_url.strip():
            return False

        method = config.get("method", "POST")
        if method not in ("POST", "PUT"):
            return False

        auth_type = config.get("auth_type", "none")
        if auth_type not in ("none", "bearer", "api_key"):
            return False

        if auth_type != "none":
            auth_value = config.get("auth_value")
            if not isinstance(auth_value, str) or not auth_value.strip():
                return False

        headers = config.get("headers")
        if headers is not None:
            if not isinstance(headers, dict):
                return False
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
                return False

        return True

    def _build_headers(self, config: dict) -> dict[str, str]:
        """Build the HTTP headers dict from config."""
        headers: dict[str, str] = {}

        # Custom headers first
        custom = config.get("headers")
        if isinstance(custom, dict):
            headers.update(custom)

        # Auth headers
        auth_type = config.get("auth_type", "none")
        auth_value = config.get("auth_value", "")
        if auth_type == "bearer" and auth_value:
            headers["Authorization"] = f"Bearer {auth_value}"
        elif auth_type == "api_key" and auth_value:
            headers["X-API-Key"] = auth_value

        return headers

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Find the actual data key (skip internal keys that start with "_")
        data_key = next((k for k in inputs if not k.startswith("_")), None)
        if data_key is None:
            return {}

        payload = inputs[data_key]
        endpoint_url = config["endpoint_url"]
        method = config.get("method", "POST")
        headers = self._build_headers(config)

        await self.call_external(
            endpoint=endpoint_url,
            method=method,
            payload=payload if isinstance(payload, dict) else {"data": payload},
            headers=headers,
        )

        # Sinks have no output schemas
        return {}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "endpoint_url": "https://example.com/api/results",
                "method": "POST",
                "headers": {"X-Custom-Header": "test-value"},
                "auth_type": "none",
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {"subject": "Concept A", "scores": {"clarity": 4, "novelty": 3}},
                    ],
                },
            },
            "expected_output": {},
        }
