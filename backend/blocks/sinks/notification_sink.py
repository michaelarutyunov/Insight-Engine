"""Notification Sink block — logs pipeline completion to file or fires a webhook."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from blocks.base import SinkBase
from schemas.data_objects import DATA_TYPES

logger = logging.getLogger(__name__)


class NotificationSink(SinkBase):
    """Terminal block that logs pipeline completion or fires a webhook notification.

    Accepts any edge data type as input. Supports two modes controlled by the
    ``mode`` config field:

    * **log** — appends a timestamped message to a local file.
    * **webhook** — POSTs a JSON payload to a configurable URL.
    """

    @property
    def input_schemas(self) -> list[str]:
        return sorted(DATA_TYPES)

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["log", "webhook"],
                    "description": "Notification mode: 'log' writes to a file, 'webhook' POSTs to a URL",
                },
                "log_path": {
                    "type": "string",
                    "description": "File path for log mode output. Required when mode is 'log'",
                },
                "webhook_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "URL to POST notification to. Required when mode is 'webhook'",
                },
                "message_template": {
                    "type": "string",
                    "description": "Optional message template with {status} and {output_summary} placeholders",
                },
            },
            "required": ["mode"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Logs pipeline completion to a file or fires an HTTP webhook notification. "
            "Accepts any data type as input. Use this block to integrate pipeline runs "
            "with external monitoring, alerting, or logging systems."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Designed as a pipeline terminal for observability. In log mode, each run "
            "appends a timestamped entry to the configured file. In webhook mode, the "
            "block POSTs a JSON payload with run status and an output summary. "
            "Webhook calls use a 30-second timeout with 3 retries on failure. "
            "This block does not transform data; it consumes it for notification purposes only."
        )

    @property
    def tags(self) -> list[str]:
        return ["notification", "webhook", "logging", "terminal", "observability"]

    def validate_config(self, config: dict) -> bool:
        mode = config.get("mode")
        if mode not in ("log", "webhook"):
            return False

        if mode == "log":
            log_path = config.get("log_path")
            if not isinstance(log_path, str) or not log_path.strip():
                return False

        if mode == "webhook":
            url = config.get("webhook_url")
            if not isinstance(url, str) or not url.strip():
                return False

        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        mode = config["mode"]
        message_template = config.get("message_template")

        # Build a short summary of the input data
        data_key = next((k for k in inputs if not k.startswith("_")), None)
        output_summary = self._summarize(inputs.get(data_key)) if data_key else "No input data"
        status = "completed"

        message = self._render_message(message_template, status, output_summary)

        if mode == "log":
            self._write_log(config["log_path"], message)
        elif mode == "webhook":
            await self._post_webhook(
                config["webhook_url"],
                {"status": status, "message": message, "output_summary": output_summary},
            )

        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize(data: Any) -> str:
        """Produce a short human-readable summary of pipeline output data."""
        if isinstance(data, dict):
            keys = list(data.keys())
            return f"dict with keys: {keys}"
        if isinstance(data, list):
            return f"list with {len(data)} items"
        return str(data)[:200]

    @staticmethod
    def _render_message(template: str | None, status: str, output_summary: str) -> str:
        """Render the message template, falling back to a default format."""
        if template:
            return template.format(status=status, output_summary=output_summary)
        return f"Pipeline {status}. Output summary: {output_summary}"

    @staticmethod
    def _write_log(log_path: str, message: str) -> None:
        """Append a timestamped log entry to the given file path."""
        timestamp = datetime.now(tz=UTC).isoformat()
        entry = f"[{timestamp}] {message}\n"
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(entry)

    @staticmethod
    async def _post_webhook(url: str, payload: dict) -> None:
        """POST a JSON payload to the webhook URL with basic retry logic."""
        async with httpx.AsyncClient(timeout=30) as client:
            retries = 3
            base_delay = 1.0
            for attempt in range(retries):
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    return
                except httpx.TimeoutException:
                    if attempt < retries - 1:
                        await asyncio.sleep(base_delay * (2**attempt))
                        continue
                    logger.warning("Webhook to %s timed out after %d retries", url, retries)
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "Webhook to %s returned status %d", url, exc.response.status_code
                    )
                    return
                except httpx.RequestError as exc:
                    if attempt < retries - 1:
                        await asyncio.sleep(base_delay * (2**attempt))
                        continue
                    logger.warning("Webhook to %s failed: %s", url, exc)

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "mode": "log",
                "log_path": "/tmp/insight_engine_test_notification.log",
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {"subject": "Concept A", "scores": {"quality": 8}},
                    ],
                },
            },
            "expected_output": {},
        }
