"""Sample Provider Source block — stub for Cint/Lucid-style sample providers.

Models the API shape of panel providers like Cint and Lucid as a stub.
Uses IntegrationMixin.call_external() for HTTP calls. In stub mode,
returns realistic mock respondent_collection data without making real
network requests.
"""

from typing import Any

from blocks.base import SourceBase
from blocks.integration import IntegrationMixin


class SampleProviderSource(SourceBase, IntegrationMixin):
    """Source block that fetches sample respondents from a panel provider.

    Models Cint/Lucid API shape as a stub. When ``stub_mode`` is enabled
    in config (default True), returns realistic mock data shaped like a
    real provider response without making network calls. When disabled,
    calls the provider endpoint via ``call_external()``.
    """

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["cint", "lucid"],
                    "description": "Panel provider to use (cint or lucid)",
                },
                "project_id": {
                    "type": "string",
                    "description": "Provider project/survey identifier",
                },
                "sample_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "description": "Number of respondents to request",
                },
                "target_criteria": {
                    "type": "object",
                    "description": "Quota targeting criteria (age range, gender, region, etc.)",
                    "properties": {
                        "age_min": {"type": "integer"},
                        "age_max": {"type": "integer"},
                        "gender": {
                            "type": "string",
                            "enum": ["any", "male", "female"],
                        },
                        "country": {"type": "string"},
                    },
                },
                "stub_mode": {
                    "type": "boolean",
                    "default": True,
                    "description": "When True, returns mock data without calling the provider API",
                },
                "credential_api_key": {
                    "type": "string",
                    "description": "API key for the panel provider (prefixed with credential_ for IntegrationMixin)",
                },
            },
            "required": ["provider", "project_id", "sample_size"],
        }

    @property
    def description(self) -> str:
        return """Fetch sample respondents from a panel provider (Cint or Lucid).

Use this block as a pipeline entry point when you need to source survey respondents
through a panel marketplace. Supports quota-based targeting by demographics such as
age, gender, and region. In stub mode (default), returns realistic mock data for
development and testing without making live API calls."""

    @property
    def methodological_notes(self) -> str:
        return """Panel-sourced respondents come with inherent biases depending on the
provider's panel composition. Cint and Lucid aggregate from multiple panel partners,
which can reduce single-panel bias but introduce variability in data quality.

When using targeted sampling (target_criteria), ensure quota cells are large enough
to support downstream segmentation analysis. Minimum recommended cell size is n=30
for meaningful statistical analysis.

For production use, disable stub_mode and provide valid credential_api_key.
Monitor incidence rates and completion times as data quality indicators.
Consider adding a data quality screening step (e.g., attention checks) downstream."""

    @property
    def tags(self) -> list[str]:
        return [
            "data_ingestion",
            "panel_provider",
            "sample",
            "survey",
            "cint",
            "lucid",
            "respondent_data",
            "external_service",
        ]

    @property
    def service_name(self) -> str:
        provider = getattr(self, "_provider_name", "cint")
        names = {"cint": "Cint Sample Exchange", "lucid": "Lucid Marketplace"}
        return names.get(provider, "Sample Provider")

    @property
    def estimated_latency(self) -> str:
        return "moderate"

    @property
    def cost_per_call(self) -> dict[str, Any] | None:
        return {"unit": "USD", "estimate": 1.50, "basis": "per_complete"}

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("provider"), str):
            return False
        if config["provider"] not in ("cint", "lucid"):
            return False
        if not isinstance(config.get("project_id"), str) or not config["project_id"].strip():
            return False
        if not isinstance(config.get("sample_size"), int) or config["sample_size"] < 1:
            return False
        criteria = config.get("target_criteria")
        return not (criteria is not None and not isinstance(criteria, dict))

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        _ = inputs  # noqa: F841 -- base contract requires inputs param

        # Store provider name for service_name property
        self._provider_name = config["provider"]

        stub_mode = config.get("stub_mode", True)

        if stub_mode:
            return self._generate_stub_response(config)

        # Live mode: call the provider API
        credentials = self.get_credentials(config)
        endpoint = self._build_endpoint(config)

        payload = {
            "project_id": config["project_id"],
            "sample_size": config["sample_size"],
            "target_criteria": config.get("target_criteria", {}),
        }
        headers = {}
        if "api_key" in credentials:
            headers["Authorization"] = f"Bearer {credentials['api_key']}"

        response = await self.call_external(
            endpoint=endpoint,
            method="POST",
            payload=payload,
            headers=headers,
        )
        return self._parse_provider_response(response, config)

    def _build_endpoint(self, config: dict) -> str:
        provider = config["provider"]
        if provider == "cint":
            return "https://api.cint.com/v2/projects/{project_id}/sample".format(
                project_id=config["project_id"]
            )
        return "https://api.lucid.market/v1/surveys/{project_id}/respondents".format(
            project_id=config["project_id"]
        )

    def _parse_provider_response(self, response: dict, config: dict) -> dict[str, Any]:
        respondents = response.get("respondents", response.get("data", []))
        return {"respondent_collection": {"rows": respondents}}

    def _generate_stub_response(self, config: dict) -> dict[str, Any]:
        sample_size = min(config["sample_size"], 10)  # Cap stub output
        criteria = config.get("target_criteria", {})
        country = criteria.get("country", "US")
        gender_options = (
            ["male", "female"] if criteria.get("gender", "any") == "any" else [criteria["gender"]]
        )
        age_min = criteria.get("age_min", 18)
        age_max = criteria.get("age_max", 65)

        import random

        seed = 42  # Fixed seed for deterministic stub output
        rng = random.Random(seed)

        rows = []
        for i in range(sample_size):
            rows.append(
                {
                    "respondent_id": f"{config['provider']}-{config['project_id']}-{i + 1:04d}",
                    "provider": config["provider"],
                    "status": "complete",
                    "age": str(rng.randint(age_min, age_max)),
                    "gender": rng.choice(gender_options),
                    "country": country,
                    "completion_seconds": str(rng.randint(180, 900)),
                    "quality_score": str(round(rng.uniform(0.7, 1.0), 2)),
                }
            )

        return {"respondent_collection": {"rows": rows}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "provider": "cint",
                "project_id": "PRJ-2024-001",
                "sample_size": 3,
                "target_criteria": {
                    "age_min": 25,
                    "age_max": 55,
                    "gender": "any",
                    "country": "US",
                },
                "stub_mode": True,
            },
            "inputs": {},
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {
                            "respondent_id": "cint-PRJ-2024-001-0001",
                            "provider": "cint",
                            "status": "complete",
                            "age": "45",
                            "gender": "male",
                            "country": "US",
                            "completion_seconds": "205",
                            "quality_score": "0.92",
                        },
                        {
                            "respondent_id": "cint-PRJ-2024-001-0002",
                            "provider": "cint",
                            "status": "complete",
                            "age": "32",
                            "gender": "male",
                            "country": "US",
                            "completion_seconds": "322",
                            "quality_score": "0.92",
                        },
                        {
                            "respondent_id": "cint-PRJ-2024-001-0003",
                            "provider": "cint",
                            "status": "complete",
                            "age": "46",
                            "gender": "male",
                            "country": "US",
                            "completion_seconds": "784",
                            "quality_score": "0.83",
                        },
                    ],
                },
            },
        }
