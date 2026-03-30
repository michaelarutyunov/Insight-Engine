"""Contract tests for all block implementations.

Verifies that each block:
  1. Implements BlockBase with valid schemas
  2. Passes validate_config with its own test fixture config
  3. Returns all declared output ports from execute()
  4. Provides test_fixtures()
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks._llm_client import BlockExecutionError  # noqa: E402
from blocks.base import (  # noqa: E402
    BlockBase,
    ComparatorBase,
    EvaluationBase,
    GenerationBase,
    HITLBase,
    LLMFlexBase,
    ReportingBase,
    RouterBase,
    SinkBase,
    SourceBase,
    TransformBase,
)
from blocks.comparison.side_by_side_comparator import SideBySideComparator
from blocks.evaluation.rubric_evaluation import RubricEvaluation
from blocks.generation.llm_generation import LLMGeneration
from blocks.hitl.approval_gate import ApprovalGate
from blocks.llm_flex.prompt_flex import PromptFlex
from blocks.reporting.markdown_report import MarkdownReport
from blocks.routing.conditional_router import ConditionalRouter
from blocks.sinks.api_push_sink import ApiPushSink
from blocks.sinks.json_sink import JSONSink
from blocks.sinks.notification_sink import NotificationSink
from blocks.sources.csv_source import CSVSource
from blocks.sources.db_source import DBSource
from blocks.sources.sample_provider_source import SampleProviderSource
from blocks.transforms.column_recoding import ColumnRecoding
from blocks.transforms.data_cleaning import DataCleaning
from blocks.transforms.filter_transform import FilterTransform

ALL_BLOCKS: list[type[BlockBase]] = [
    CSVSource,
    DBSource,
    SampleProviderSource,
    FilterTransform,
    ColumnRecoding,
    DataCleaning,
    LLMGeneration,
    RubricEvaluation,
    SideBySideComparator,
    PromptFlex,
    ConditionalRouter,
    ApprovalGate,
    MarkdownReport,
    ApiPushSink,
    JSONSink,
    NotificationSink,
]

BASE_TYPE_MAP: dict[type, str] = {
    SourceBase: "source",
    TransformBase: "transform",
    GenerationBase: "generation",
    EvaluationBase: "evaluation",
    ComparatorBase: "comparator",
    LLMFlexBase: "llm_flex",
    RouterBase: "router",
    HITLBase: "hitl",
    ReportingBase: "reporting",
    SinkBase: "sink",
}


def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Parameterised contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("block_cls", ALL_BLOCKS, ids=lambda c: c.__name__)
class TestBlockContracts:
    def test_has_test_fixtures(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        fixtures = block.test_fixtures()
        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

    def test_block_type_matches_base(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        expected_type = None
        for base_cls, type_str in BASE_TYPE_MAP.items():
            if isinstance(block, base_cls):
                expected_type = type_str
                break
        assert expected_type is not None, f"{block_cls.__name__} does not match any known base"
        assert block.block_type == expected_type

    def test_schemas_are_lists_of_strings(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        assert isinstance(block.input_schemas, list)
        assert isinstance(block.output_schemas, list)
        assert all(isinstance(s, str) for s in block.input_schemas)
        assert all(isinstance(s, str) for s in block.output_schemas)

    def test_config_schema_is_dict(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        assert isinstance(block.config_schema, dict)

    def test_validate_config_accepts_fixture(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        config = block.test_fixtures()["config"]
        assert block.validate_config(config) is True

    def test_description_is_nonempty_string(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_execute_returns_declared_outputs(self, block_cls: type[BlockBase]) -> None:
        from blocks._llm_client import HITLSuspendSignal
        from blocks.integration import IntegrationMixin

        block = block_cls()
        fixtures = block.test_fixtures()

        # HITL blocks raise HITLSuspendSignal instead of returning output
        if isinstance(block, HITLBase):
            with pytest.raises(HITLSuspendSignal) as exc_info:
                _run(block.execute(fixtures["inputs"], fixtures["config"]))
            # Verify checkpoint data is present
            assert hasattr(exc_info.value, "checkpoint_data")
            assert isinstance(exc_info.value.checkpoint_data, dict)
        elif isinstance(block, IntegrationMixin):
            # IntegrationMixin blocks call external services -- mock call_external
            from unittest.mock import AsyncMock

            block.call_external = AsyncMock(return_value={"status": "ok"})  # type: ignore[assignment]
            result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
            assert isinstance(result, dict)
            for port in block.output_schemas:
                assert port in result, f"Missing output port: {port}"
        else:
            result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
            assert isinstance(result, dict)
            for port in block.output_schemas:
                assert port in result, f"Missing output port: {port}"

    def test_validate_config_rejects_empty(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        # ApprovalGate accepts empty config because all fields have defaults
        if block_cls.__name__ == "ApprovalGate":
            assert block.validate_config({}) is True
        else:
            assert block.validate_config({}) is False


# ---------------------------------------------------------------------------
# Block-specific tests
# ---------------------------------------------------------------------------


class TestCSVSource:
    def test_execute_output(self) -> None:
        block = CSVSource()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_source_has_no_inputs(self) -> None:
        assert CSVSource().input_schemas == []


class TestFilterTransform:
    def test_execute_output(self) -> None:
        block = FilterTransform()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestLLMGeneration:
    def test_execute_output(self) -> None:
        block = LLMGeneration()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestRubricEvaluation:
    def test_execute_output(self) -> None:
        block = RubricEvaluation()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestSideBySideComparator:
    def test_execute_output(self) -> None:
        block = SideBySideComparator()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestPromptFlex:
    def test_execute_output(self) -> None:
        block = PromptFlex()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestConditionalRouter:
    def test_execute_output(self) -> None:
        block = ConditionalRouter()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_resolve_route(self) -> None:
        block = ConditionalRouter()
        fixtures = block.test_fixtures()
        # Pass config directly to resolve_route
        routes = block.resolve_route(fixtures["inputs"], fixtures["config"])
        assert routes == fixtures["expected_routes"]


class TestApprovalGate:
    def test_render_checkpoint(self) -> None:
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        inputs_with_config = {**fixtures["inputs"], "_config": fixtures["config"]}
        checkpoint = block.render_checkpoint(inputs_with_config)
        assert checkpoint == fixtures["expected_checkpoint"]

    def test_process_response_approve(self) -> None:
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        human_input = fixtures["test_approve_response"]
        result = block.process_response(human_input, fixtures["inputs"], fixtures["config"])
        assert result == fixtures["expected_output"]

    def test_process_response_reject(self) -> None:
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        human_input = fixtures["test_reject_response"]
        with pytest.raises(BlockExecutionError):
            block.process_response(human_input, fixtures["inputs"], fixtures["config"])


class TestMarkdownReport:
    def test_execute_output(self) -> None:
        block = MarkdownReport()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_declare_pipeline_inputs(self) -> None:
        block = MarkdownReport()
        assert block.declare_pipeline_inputs() == ["evaluation_set", "text_corpus"]

    def test_fixtures(self) -> None:
        block = MarkdownReport()
        fixtures = block.test_fixtures()
        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures


class TestJSONSink:
    def test_execute_returns_empty(self) -> None:
        block = JSONSink()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == {}

    def test_sink_has_no_outputs(self) -> None:
        assert JSONSink().output_schemas == []


class TestApiPushSink:
    def test_execute_returns_empty(self) -> None:
        from unittest.mock import AsyncMock

        block = ApiPushSink()
        fixtures = block.test_fixtures()
        block.call_external = AsyncMock(return_value={"status": "ok"})  # type: ignore[assignment]
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == {}

    def test_sink_has_no_outputs(self) -> None:
        assert ApiPushSink().output_schemas == []

    def test_service_name(self) -> None:
        assert ApiPushSink().service_name == "External API"

    def test_is_external_service(self) -> None:
        assert ApiPushSink().is_external_service is True

    def test_validate_config_rejects_missing_url(self) -> None:
        block = ApiPushSink()
        assert block.validate_config({}) is False
        assert block.validate_config({"method": "POST"}) is False

    def test_validate_config_rejects_bad_method(self) -> None:
        block = ApiPushSink()
        assert block.validate_config({"endpoint_url": "https://x.com", "method": "DELETE"}) is False

    def test_validate_config_accepts_minimal(self) -> None:
        block = ApiPushSink()
        assert block.validate_config({"endpoint_url": "https://example.com/hook"}) is True

    def test_validate_config_accepts_bearer_auth(self) -> None:
        block = ApiPushSink()
        assert (
            block.validate_config(
                {"endpoint_url": "https://x.com", "auth_type": "bearer", "auth_value": "tok123"}
            )
            is True
        )

    def test_validate_config_rejects_auth_without_value(self) -> None:
        block = ApiPushSink()
        assert (
            block.validate_config({"endpoint_url": "https://x.com", "auth_type": "bearer"}) is False
        )

    def test_build_headers_bearer(self) -> None:
        block = ApiPushSink()
        headers = block._build_headers(
            {"auth_type": "bearer", "auth_value": "mytoken", "headers": None}
        )
        assert headers["Authorization"] == "Bearer mytoken"

    def test_build_headers_api_key(self) -> None:
        block = ApiPushSink()
        headers = block._build_headers(
            {"auth_type": "api_key", "auth_value": "key123", "headers": None}
        )
        assert headers["X-API-Key"] == "key123"

    def test_build_headers_custom(self) -> None:
        block = ApiPushSink()
        headers = block._build_headers({"auth_type": "none", "headers": {"X-Custom": "val"}})
        assert headers["X-Custom"] == "val"
        assert "Authorization" not in headers

    def test_call_external_called_with_correct_args(self) -> None:
        from unittest.mock import AsyncMock

        block = ApiPushSink()
        fixtures = block.test_fixtures()
        block.call_external = AsyncMock(return_value={"status": "ok"})  # type: ignore[assignment]
        _run(block.execute(fixtures["inputs"], fixtures["config"]))

        block.call_external.assert_awaited_once()
        call_kwargs = block.call_external.call_args
        assert call_kwargs.kwargs["endpoint"] == "https://example.com/api/results"
        assert call_kwargs.kwargs["method"] == "POST"
        assert call_kwargs.kwargs["headers"]["X-Custom-Header"] == "test-value"


class TestNotificationSink:
    def test_execute_returns_empty(self) -> None:
        block = NotificationSink()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == {}

    def test_sink_has_no_outputs(self) -> None:
        assert NotificationSink().output_schemas == []

    def test_log_mode_writes_file(self, tmp_path) -> None:
        block = NotificationSink()
        log_file = str(tmp_path / "notifications.log")
        config = {"mode": "log", "log_path": log_file}
        inputs = {"evaluation_set": {"evaluations": [{"subject": "X"}]}}
        _run(block.execute(inputs, config))
        content = Path(log_file).read_text()
        assert "completed" in content
        assert "dict with keys" in content

    def test_validate_config_rejects_log_mode_without_path(self) -> None:
        block = NotificationSink()
        assert block.validate_config({"mode": "log"}) is False
        assert block.validate_config({"mode": "log", "log_path": ""}) is False

    def test_validate_config_rejects_webhook_mode_without_url(self) -> None:
        block = NotificationSink()
        assert block.validate_config({"mode": "webhook"}) is False
        assert block.validate_config({"mode": "webhook", "webhook_url": ""}) is False

    def test_validate_config_rejects_invalid_mode(self) -> None:
        block = NotificationSink()
        assert block.validate_config({"mode": "email"}) is False

    def test_message_template_rendering(self, tmp_path) -> None:
        block = NotificationSink()
        log_file = str(tmp_path / "template.log")
        config = {
            "mode": "log",
            "log_path": log_file,
            "message_template": "Status: {status} | Summary: {output_summary}",
        }
        inputs = {"segment_profile_set": {"segments": [{"id": 1}]}}
        _run(block.execute(inputs, config))
        content = Path(log_file).read_text()
        assert "Status: completed" in content
        assert "Summary: dict with keys" in content


class TestSampleProviderSource:
    def test_execute_output(self) -> None:
        block = SampleProviderSource()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_source_has_no_inputs(self) -> None:
        assert SampleProviderSource().input_schemas == []

    def test_service_name_cint(self) -> None:
        block = SampleProviderSource()
        block._provider_name = "cint"
        assert block.service_name == "Cint Sample Exchange"

    def test_service_name_lucid(self) -> None:
        block = SampleProviderSource()
        block._provider_name = "lucid"
        assert block.service_name == "Lucid Marketplace"

    def test_estimated_latency(self) -> None:
        block = SampleProviderSource()
        assert block.estimated_latency == "moderate"

    def test_cost_per_call(self) -> None:
        block = SampleProviderSource()
        cost = block.cost_per_call
        assert cost is not None
        assert cost["unit"] == "USD"

    def test_validate_config_rejects_bad_provider(self) -> None:
        block = SampleProviderSource()
        config = {"provider": "invalid", "project_id": "P1", "sample_size": 10}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_missing_project(self) -> None:
        block = SampleProviderSource()
        config = {"provider": "cint", "sample_size": 10}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_zero_sample(self) -> None:
        block = SampleProviderSource()
        config = {"provider": "cint", "project_id": "P1", "sample_size": 0}
        assert block.validate_config(config) is False

    def test_stub_returns_respondent_collection(self) -> None:
        block = SampleProviderSource()
        config = {
            "provider": "lucid",
            "project_id": "TEST-001",
            "sample_size": 5,
            "stub_mode": True,
        }
        result = _run(block.execute({}, config))
        assert "respondent_collection" in result
        rows = result["respondent_collection"]["rows"]
        assert len(rows) == 5
        for row in rows:
            assert "respondent_id" in row
            assert row["provider"] == "lucid"

    def test_is_external_service(self) -> None:
        block = SampleProviderSource()
        assert block.is_external_service is True


class TestColumnRecoding:
    def test_execute_output(self) -> None:
        block = ColumnRecoding()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_value_mapping_overwrite(self) -> None:
        """Map mode overwrites the source column when output_column is not specified."""
        block = ColumnRecoding()
        result = _run(
            block.execute(
                inputs={
                    "respondent_collection": {
                        "rows": [
                            {"color": "R"},
                            {"color": "G"},
                            {"color": "B"},
                        ]
                    }
                },
                config={
                    "recodings": [
                        {
                            "column": "color",
                            "type": "map",
                            "mapping": {"R": "Red", "G": "Green", "B": "Blue"},
                        }
                    ]
                },
            )
        )
        rows = result["respondent_collection"]["rows"]
        assert rows[0]["color"] == "Red"
        assert rows[1]["color"] == "Green"
        assert rows[2]["color"] == "Blue"

    def test_value_mapping_unmapped_left_unchanged(self) -> None:
        """Values not in the mapping dict are left as-is."""
        block = ColumnRecoding()
        result = _run(
            block.execute(
                inputs={
                    "respondent_collection": {"rows": [{"status": "active"}, {"status": "pending"}]}
                },
                config={
                    "recodings": [
                        {
                            "column": "status",
                            "type": "map",
                            "mapping": {"active": "A"},
                        }
                    ]
                },
            )
        )
        rows = result["respondent_collection"]["rows"]
        assert rows[0]["status"] == "A"
        assert rows[1]["status"] == "pending"

    def test_binning_to_new_column(self) -> None:
        """Bin mode writes to output_column without modifying the source."""
        block = ColumnRecoding()
        result = _run(
            block.execute(
                inputs={
                    "respondent_collection": {
                        "rows": [{"score": 15}, {"score": 85}, {"score": 100}]
                    }
                },
                config={
                    "recodings": [
                        {
                            "column": "score",
                            "type": "bin",
                            "bins": [
                                {"min": 0, "max": 50, "label": "Low"},
                                {"min": 50, "max": 100, "label": "High"},
                            ],
                            "output_column": "grade",
                        }
                    ]
                },
            )
        )
        rows = result["respondent_collection"]["rows"]
        assert rows[0]["score"] == 15  # original preserved
        assert rows[0]["grade"] == "Low"
        assert rows[1]["score"] == 85
        assert rows[1]["grade"] == "High"
        # 100 falls into "High" (last bin is inclusive on both ends)
        assert rows[2]["score"] == 100
        assert rows[2]["grade"] == "High"

    def test_binning_non_numeric_left_unchanged(self) -> None:
        """Non-numeric values in a binned column are left unchanged."""
        block = ColumnRecoding()
        result = _run(
            block.execute(
                inputs={"respondent_collection": {"rows": [{"val": "N/A"}, {"val": 42}]}},
                config={
                    "recodings": [
                        {
                            "column": "val",
                            "type": "bin",
                            "bins": [
                                {"min": 0, "max": 100, "label": "all"},
                            ],
                        }
                    ]
                },
            )
        )
        rows = result["respondent_collection"]["rows"]
        assert rows[0]["val"] == "N/A"  # non-numeric, untouched
        assert rows[1]["val"] == "all"

    def test_validate_config_rejects_missing_mapping(self) -> None:
        block = ColumnRecoding()
        assert block.validate_config({"recodings": [{"column": "x", "type": "map"}]}) is False

    def test_validate_config_rejects_empty_bins(self) -> None:
        block = ColumnRecoding()
        assert (
            block.validate_config({"recodings": [{"column": "x", "type": "bin", "bins": []}]})
            is False
        )

    def test_validate_config_rejects_bad_type(self) -> None:
        block = ColumnRecoding()
        assert block.validate_config({"recodings": [{"column": "x", "type": "unknown"}]}) is False
