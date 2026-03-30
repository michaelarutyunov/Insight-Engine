"""Tests for backend/chat/context_builder.py."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from chat.context_builder import (  # noqa: E402
    build_advisor_context,
    build_block_catalog_context,
    build_pipeline_context,
)
from reasoning.profiles import ProfilePreferences, ReasoningProfile  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_pipeline() -> dict:
    """Minimal pipeline JSON matching PipelineSchema.model_dump() shape."""
    return {
        "pipeline_id": "00000000-0000-4000-8000-000000000001",
        "name": "Test Pipeline",
        "version": "1.0",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "nodes": [
            {
                "node_id": "a0000000-0000-4000-8000-000000000001",
                "block_type": "source",
                "block_implementation": "csv_loader",
                "label": "Load Survey",
                "position": {"x": 100, "y": 200},
                "config": {"file_path": "data.csv"},
                "input_schema": [],
                "output_schema": ["respondent_collection"],
            },
            {
                "node_id": "a0000000-0000-4000-8000-000000000002",
                "block_type": "analysis",
                "block_implementation": "segmentation_kmeans",
                "label": "K-Means Segmentation",
                "position": {"x": 300, "y": 200},
                "config": {"n_clusters": 4},
                "input_schema": ["respondent_collection"],
                "output_schema": ["segment_profile_set"],
            },
        ],
        "edges": [
            {
                "edge_id": "e0000000-0000-4000-8000-000000000001",
                "source_node": "a0000000-0000-4000-8000-000000000001",
                "target_node": "a0000000-0000-4000-8000-000000000002",
                "data_type": "respondent_collection",
                "validated": True,
            },
        ],
        "loop_definitions": [],
        "metadata": {
            "description": "A test pipeline for context builder tests",
            "tags": ["test", "segmentation"],
            "author": "Test Author",
        },
    }


def _sample_pipeline_with_loop() -> dict:
    """Pipeline JSON with a loop definition."""
    p = _sample_pipeline()
    p["loop_definitions"] = [
        {
            "loop_id": "l0000000-0000-4000-8000-000000000001",
            "entry_node": "a0000000-0000-4000-8000-000000000001",
            "exit_node": "a0000000-0000-4000-8000-000000000002",
            "termination": {
                "type": "max_iterations",
                "max_iterations": 10,
            },
        },
    ]
    return p


def _sample_profile() -> ReasoningProfile:
    return ReasoningProfile(
        name="Test Profile",
        version="1.0",
        description="Profile for unit tests",
        dimension_weights={
            "exploratory_confirmatory": 1.0,
            "assumption_weight": 0.8,
        },
        preferences=ProfilePreferences(
            default_stance="exploratory",
            transparency_threshold="medium",
            prefer_established=True,
        ),
        practitioner_workflows_dir="practitioner_workflows",
    )


def _sample_candidates() -> list[dict]:
    return [
        {
            "block_implementation": "segmentation_kmeans",
            "block_type": "analysis",
            "fit_score": 0.85,
            "fit_reasoning": "Strong match for exploratory segmentation",
            "tradeoffs": "Requires numeric features",
            "dimensions": {
                "exploratory_confirmatory": "exploratory",
                "assumption_weight": "medium",
            },
        },
        {
            "block_implementation": "placeholder_analysis",
            "block_type": "analysis",
            "fit_score": 0.5,
            "fit_reasoning": "Fallback option",
            "tradeoffs": "Less specific",
            "dimensions": {},
        },
    ]


# ---------------------------------------------------------------------------
# build_pipeline_context tests
# ---------------------------------------------------------------------------


class TestBuildPipelineContext:
    def test_returns_string(self) -> None:
        result = build_pipeline_context(_sample_pipeline())
        assert isinstance(result, str)

    def test_includes_pipeline_name_and_version(self) -> None:
        result = build_pipeline_context(_sample_pipeline())
        assert "Test Pipeline" in result
        assert "v1.0" in result

    def test_includes_metadata(self) -> None:
        result = build_pipeline_context(_sample_pipeline())
        assert "A test pipeline for context builder tests" in result
        assert "Test Author" in result
        assert "test, segmentation" in result

    def test_includes_nodes(self) -> None:
        result = build_pipeline_context(_sample_pipeline())
        assert "Load Survey" in result
        assert "csv_loader" in result
        assert "K-Means Segmentation" in result
        assert "segmentation_kmeans" in result

    def test_includes_node_config(self) -> None:
        result = build_pipeline_context(_sample_pipeline())
        assert "file_path" in result
        assert "n_clusters" in result

    def test_includes_edges(self) -> None:
        result = build_pipeline_context(_sample_pipeline())
        assert "respondent_collection" in result
        assert "validated" in result

    def test_handles_empty_pipeline(self) -> None:
        result = build_pipeline_context({"name": "Empty", "nodes": [], "edges": []})
        assert "Empty" in result
        assert "Nodes (0)" in result
        assert "Edges (0)" in result

    def test_handles_pipeline_with_loops(self) -> None:
        result = build_pipeline_context(_sample_pipeline_with_loop())
        assert "Loops (1)" in result
        assert "max_iterations" in result

    def test_handles_pipeline_without_metadata(self) -> None:
        p = _sample_pipeline()
        del p["metadata"]
        result = build_pipeline_context(p)
        assert isinstance(result, str)
        assert "Test Pipeline" in result


# ---------------------------------------------------------------------------
# build_block_catalog_context tests
# ---------------------------------------------------------------------------


class TestBuildBlockCatalogContext:
    @patch("chat.context_builder.registry.list_blocks")
    def test_returns_string(self, mock_list: pytest.MonkeyPatch) -> None:
        mock_list.return_value = []
        result = build_block_catalog_context()
        assert isinstance(result, str)

    @patch("chat.context_builder.registry.list_blocks")
    def test_empty_registry(self, mock_list: pytest.MonkeyPatch) -> None:
        mock_list.return_value = []
        result = build_block_catalog_context()
        assert "no blocks registered" in result

    @patch("chat.context_builder.registry.list_blocks")
    def test_formats_block_with_all_fields(self, mock_list: pytest.MonkeyPatch) -> None:
        mock_list.return_value = [
            {
                "block_type": "analysis",
                "block_implementation": "segmentation_kmeans",
                "description": "K-means clustering segmentation",
                "methodological_notes": "Use for numeric data",
                "tags": ["clustering", "segmentation"],
                "input_schemas": ["respondent_collection"],
                "output_schemas": ["segment_profile_set"],
                "dimensions": {
                    "exploratory_confirmatory": "exploratory",
                    "assumption_weight": "medium",
                },
                "practitioner_workflow": "segmentation.md",
            },
        ]
        result = build_block_catalog_context()

        assert "analysis/segmentation_kmeans" in result
        assert "K-means clustering segmentation" in result
        assert "Use for numeric data" in result
        assert "clustering, segmentation" in result
        assert "exploratory_confirmatory=exploratory" in result
        assert "Practitioner workflow: segmentation.md" in result

    @patch("chat.context_builder.registry.list_blocks")
    def test_filters_by_block_type(self, mock_list: pytest.MonkeyPatch) -> None:
        mock_list.return_value = [
            {
                "block_type": "source",
                "block_implementation": "csv_loader",
                "description": "Loads CSV",
                "methodological_notes": "n/a",
                "tags": [],
                "input_schemas": [],
                "output_schemas": ["respondent_collection"],
            },
            {
                "block_type": "analysis",
                "block_implementation": "kmeans",
                "description": "Clusters data",
                "methodological_notes": "n/a",
                "tags": [],
                "input_schemas": ["respondent_collection"],
                "output_schemas": ["segment_profile_set"],
                "dimensions": {"exploratory_confirmatory": "exploratory"},
            },
        ]
        result = build_block_catalog_context(block_type_filter="analysis")
        assert "analysis/kmeans" in result
        assert "csv_loader" not in result

    @patch("chat.context_builder.registry.list_blocks")
    def test_block_without_dimensions(self, mock_list: pytest.MonkeyPatch) -> None:
        mock_list.return_value = [
            {
                "block_type": "source",
                "block_implementation": "csv_loader",
                "description": "Loads CSV",
                "methodological_notes": "n/a",
                "tags": [],
                "input_schemas": [],
                "output_schemas": ["respondent_collection"],
            },
        ]
        result = build_block_catalog_context()
        assert "source/csv_loader" in result
        assert "Dimensions" not in result

    @patch("chat.context_builder.registry.list_blocks")
    def test_uses_engine_registry(self, mock_list: pytest.MonkeyPatch) -> None:
        """Verify the function calls engine.registry.list_blocks()."""
        mock_list.return_value = []
        build_block_catalog_context()
        mock_list.assert_called_once()


# ---------------------------------------------------------------------------
# build_advisor_context tests
# ---------------------------------------------------------------------------


class TestBuildAdvisorContext:
    def test_returns_string(self) -> None:
        profile = _sample_profile()
        result = build_advisor_context(profile)
        assert isinstance(result, str)

    def test_includes_profile_info(self) -> None:
        profile = _sample_profile()
        result = build_advisor_context(profile)
        assert "Test Profile" in result
        assert "1.0" in result
        assert "Profile for unit tests" in result

    def test_includes_dimension_weights(self) -> None:
        profile = _sample_profile()
        result = build_advisor_context(profile)
        assert "exploratory_confirmatory: 1.0" in result
        assert "assumption_weight: 0.8" in result

    def test_includes_preferences(self) -> None:
        profile = _sample_profile()
        result = build_advisor_context(profile)
        assert "exploratory" in result
        assert "medium" in result
        assert "True" in result

    def test_without_candidates(self) -> None:
        profile = _sample_profile()
        result = build_advisor_context(profile, candidates=None)
        assert "Method Candidates" not in result

    def test_with_candidates(self) -> None:
        profile = _sample_profile()
        candidates = _sample_candidates()
        result = build_advisor_context(
            profile, candidates=candidates, base_dir=Path("/nonexistent")
        )
        assert "Method Candidates (2)" in result
        assert "segmentation_kmeans" in result
        assert "0.85" in result
        assert "Strong match" in result

    @patch("chat.context_builder.get_workflow_for_block")
    def test_loads_workflow_for_top_candidate(self, mock_wf: pytest.MonkeyPatch) -> None:
        mock_wf.return_value = "# Segmentation Workflow\n\nStep 1: Check features"
        profile = _sample_profile()
        candidates = _sample_candidates()
        base = Path("/nonexistent")

        result = build_advisor_context(profile, candidates=candidates, base_dir=base)
        mock_wf.assert_called_once_with("segmentation_kmeans", profile, base)
        assert "Practitioner Workflow" in result
        assert "Segmentation Workflow" in result
        assert "Step 1: Check features" in result

    def test_no_workflow_section_when_none_returned(self) -> None:
        profile = _sample_profile()
        candidates = _sample_candidates()
        result = build_advisor_context(
            profile, candidates=candidates, base_dir=Path("/nonexistent")
        )
        assert "Practitioner Workflow" not in result

    def test_no_llm_imports(self) -> None:
        """Module must not import any LLM SDK."""
        import chat.context_builder as mod

        source = Path(mod.__file__).read_text()
        assert "anthropic" not in source
        assert "openai" not in source
        assert "AsyncAnthropic" not in source

    def test_does_not_import_from_research_advisor(self) -> None:
        """Module must not import from research_advisor.py."""
        import chat.context_builder as mod

        source = Path(mod.__file__).read_text()
        assert "research_advisor" not in source
