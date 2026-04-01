"""Tests for PdfReport block."""

import base64

import pytest

from blocks.reporting.pdf_report import PdfReport


class TestPdfReportContract:
    """Generic contract tests for PdfReport block."""

    @pytest.fixture
    def block(self) -> PdfReport:
        """Return block instance."""
        return PdfReport()

    def test_block_type(self, block: PdfReport) -> None:
        """Test block type is 'reporting'."""
        assert block.block_type == "reporting"

    def test_input_schemas(self, block: PdfReport) -> None:
        """Test input schemas."""
        assert "evaluation_set" in block.input_schemas
        assert "text_corpus" in block.input_schemas

    def test_output_schemas(self, block: PdfReport) -> None:
        """Test output schemas."""
        assert block.output_schemas == ["generic_blob"]

    def test_config_schema_valid(self, block: PdfReport) -> None:
        """Test config schema is valid JSON Schema."""
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert "output_format" in schema["required"]
        assert "title" in schema["required"]

    def test_config_schema_has_sections(self, block: PdfReport) -> None:
        """Test config schema includes sections property."""
        schema = block.config_schema
        assert "sections" in schema["properties"]
        assert schema["properties"]["sections"]["type"] == "array"

    def test_config_schema_has_include_charts(self, block: PdfReport) -> None:
        """Test config schema includes include_charts property."""
        schema = block.config_schema
        assert "include_charts" in schema["properties"]
        assert schema["properties"]["include_charts"]["type"] == "boolean"
        assert schema["properties"]["include_charts"]["default"] is False

    def test_config_schema_has_pipeline_input_nodes(self, block: PdfReport) -> None:
        """Test config schema includes pipeline_input_nodes property."""
        schema = block.config_schema
        assert "pipeline_input_nodes" in schema["properties"]
        assert schema["properties"]["pipeline_input_nodes"]["type"] == "array"

    def test_config_schema_page_size_enum(self, block: PdfReport) -> None:
        """Test page_size enum only includes A4 and Letter."""
        schema = block.config_schema
        assert set(schema["properties"]["page_size"]["enum"]) == {"A4", "Letter"}

    def test_tags(self, block: PdfReport) -> None:
        """Test tags are present and contain expected values."""
        tags = block.tags
        assert isinstance(tags, list)
        assert "reporting" in tags
        assert "pdf" in tags
        assert "markdown" in tags
        assert "evaluation" in tags

    def test_description_present(self, block: PdfReport) -> None:
        """Test description is present and non-empty."""
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes_present(self, block: PdfReport) -> None:
        """Test methodological notes are present and non-empty."""
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_declare_pipeline_inputs(self, block: PdfReport) -> None:
        """Test declare_pipeline_inputs returns list."""
        inputs = block.declare_pipeline_inputs()
        assert isinstance(inputs, list)

    def test_validate_config_valid(self, block: PdfReport) -> None:
        """Test validate_config accepts valid config."""
        fixtures = block.test_fixtures()
        config = fixtures["config"]
        assert block.validate_config(config) is True

    def test_validate_config_missing_output_format(self, block: PdfReport) -> None:
        """Test validate_config rejects missing output_format."""
        config = {
            "title": "Test",
        }
        assert block.validate_config(config) is False

    def test_validate_config_invalid_output_format(self, block: PdfReport) -> None:
        """Test validate_config rejects invalid output_format."""
        config = {
            "output_format": "html",
            "title": "Test",
        }
        assert block.validate_config(config) is False

    def test_validate_config_missing_title(self, block: PdfReport) -> None:
        """Test validate_config rejects missing title."""
        config = {
            "output_format": "pdf",
        }
        assert block.validate_config(config) is False

    def test_validate_config_empty_title(self, block: PdfReport) -> None:
        """Test validate_config rejects empty title."""
        config = {
            "output_format": "pdf",
            "title": "   ",
        }
        assert block.validate_config(config) is False

    def test_validate_config_invalid_page_size(self, block: PdfReport) -> None:
        """Test validate_config rejects invalid page_size."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "page_size": "A3",  # Not allowed, only A4 and Letter
        }
        assert block.validate_config(config) is False

    def test_validate_config_valid_page_sizes(self, block: PdfReport) -> None:
        """Test validate_config accepts A4 and Letter."""
        for page_size in ["A4", "Letter"]:
            config = {
                "output_format": "pdf",
                "title": "Test",
                "page_size": page_size,
            }
            assert block.validate_config(config) is True

    def test_validate_config_sections(self, block: PdfReport) -> None:
        """Test validate_config handles sections parameter."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "sections": ["executive_summary", "evaluations"],
        }
        assert block.validate_config(config) is True

    def test_validate_config_invalid_sections(self, block: PdfReport) -> None:
        """Test validate_config rejects invalid sections."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "sections": "not-a-list",
        }
        assert block.validate_config(config) is False

    def test_validate_config_include_charts(self, block: PdfReport) -> None:
        """Test validate_config handles include_charts parameter."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "include_charts": True,
        }
        assert block.validate_config(config) is True

    def test_validate_config_invalid_include_charts(self, block: PdfReport) -> None:
        """Test validate_config rejects invalid include_charts."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "include_charts": "yes",
        }
        assert block.validate_config(config) is False

    def test_validate_config_pipeline_input_nodes(self, block: PdfReport) -> None:
        """Test validate_config handles pipeline_input_nodes parameter."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "pipeline_input_nodes": ["node1", "node2"],
        }
        assert block.validate_config(config) is True

    def test_validate_config_invalid_pipeline_input_nodes(self, block: PdfReport) -> None:
        """Test validate_config rejects invalid pipeline_input_nodes."""
        config = {
            "output_format": "pdf",
            "title": "Test",
            "pipeline_input_nodes": "not-a-list",
        }
        assert block.validate_config(config) is False

    def test_test_fixtures_structure(self, block: PdfReport) -> None:
        """Test test_fixtures returns valid structure."""
        fixtures = block.test_fixtures()
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures
        assert block.validate_config(fixtures["config"]) is True

    def test_test_fixtures_has_both_inputs(self, block: PdfReport) -> None:
        """Test test_fixtures includes both evaluation_set and text_corpus."""
        fixtures = block.test_fixtures()
        inputs = fixtures["inputs"]
        assert "evaluation_set" in inputs
        assert "text_corpus" in inputs

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self, block: PdfReport) -> None:
        """Test execute returns dict with output port."""
        fixtures = block.test_fixtures()
        result = await block.execute(fixtures["inputs"], fixtures["config"])
        assert isinstance(result, dict)
        assert "generic_blob" in result

    @pytest.mark.asyncio
    async def test_execute_output_structure(self, block: PdfReport) -> None:
        """Test execute returns properly structured output."""
        fixtures = block.test_fixtures()
        result = await block.execute(fixtures["inputs"], fixtures["config"])

        assert "generic_blob" in result
        output = result["generic_blob"]
        assert "data" in output

        data = output["data"]
        assert "format" in data
        assert "encoding" in data
        assert "bytes" in data
        assert "title" in data

        # Verify format and encoding
        assert data["format"] == "pdf"
        assert data["encoding"] == "base64"

        # Verify bytes is valid base64
        try:
            pdf_bytes = base64.b64decode(data["bytes"])
            assert len(pdf_bytes) > 0
            # PDF files start with %PDF
            assert pdf_bytes.startswith(b"%PDF")
        except Exception as e:
            pytest.fail(f"Failed to decode base64 PDF: {e}")

    @pytest.mark.asyncio
    async def test_execute_with_empty_evaluations(self, block: PdfReport) -> None:
        """Test execute handles empty evaluation_set gracefully."""
        config = {
            "output_format": "pdf",
            "title": "Empty Report",
        }
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {"documents": ["Some content"]},
        }
        result = await block.execute(inputs, config)

        assert "generic_blob" in result
        data = result["generic_blob"]["data"]
        pdf_bytes = base64.b64decode(data["bytes"])
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 0

    @pytest.mark.asyncio
    async def test_execute_with_empty_documents(self, block: PdfReport) -> None:
        """Test execute handles empty text_corpus gracefully."""
        config = {
            "output_format": "pdf",
            "title": "No Content Report",
        }
        inputs = {
            "evaluation_set": {
                "evaluations": [
                    {
                        "subject": "Test",
                        "criteria": ["quality"],
                        "scores": {"quality": 8},
                        "notes": "Good",
                    }
                ]
            },
            "text_corpus": {"documents": []},
        }
        result = await block.execute(inputs, config)

        assert "generic_blob" in result
        data = result["generic_blob"]["data"]
        pdf_bytes = base64.b64decode(data["bytes"])
        assert pdf_bytes.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_execute_with_include_charts(self, block: PdfReport) -> None:
        """Test execute includes charts placeholder when enabled."""
        fixtures = block.test_fixtures()
        config = fixtures["config"].copy()
        config["include_charts"] = True

        result = await block.execute(fixtures["inputs"], config)

        assert "generic_blob" in result
        data = result["generic_blob"]["data"]
        pdf_bytes = base64.b64decode(data["bytes"])
        assert pdf_bytes.startswith(b"%PDF")
        # With charts, PDF should be larger
        assert len(pdf_bytes) > 1000

    @pytest.mark.asyncio
    async def test_execute_with_custom_sections(self, block: PdfReport) -> None:
        """Test execute respects custom sections order."""
        fixtures = block.test_fixtures()
        config = fixtures["config"].copy()
        config["sections"] = ["evaluations"]  # Only include evaluations

        result = await block.execute(fixtures["inputs"], config)

        assert "generic_blob" in result
        data = result["generic_blob"]["data"]
        pdf_bytes = base64.b64decode(data["bytes"])
        assert pdf_bytes.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_execute_with_different_page_sizes(self, block: PdfReport) -> None:
        """Test execute handles different page sizes."""
        fixtures = block.test_fixtures()

        for page_size in ["A4", "Letter"]:
            config = fixtures["config"].copy()
            config["page_size"] = page_size
            config["title"] = f"Test {page_size}"

            result = await block.execute(fixtures["inputs"], config)
            assert "generic_blob" in result
            data = result["generic_blob"]["data"]
            pdf_bytes = base64.b64decode(data["bytes"])
            assert pdf_bytes.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_execute_evaluation_table_rendering(self, block: PdfReport) -> None:
        """Test that evaluations are rendered as a table."""
        config = {
            "output_format": "pdf",
            "title": "Evaluation Test",
            "sections": ["evaluations"],
        }
        inputs = {
            "evaluation_set": {
                "evaluations": [
                    {
                        "subject": "Concept A",
                        "criteria": ["appeal", "relevance"],
                        "scores": {"appeal": 8, "relevance": 7},
                        "notes": "Good overall",
                    },
                    {
                        "subject": "Concept B",
                        "criteria": ["appeal", "relevance"],
                        "scores": {"appeal": 6, "relevance": 9},
                        "notes": "Highly relevant",
                    },
                ]
            },
            "text_corpus": {"documents": []},
        }

        result = await block.execute(inputs, config)
        assert "generic_blob" in result
        data = result["generic_blob"]["data"]
        pdf_bytes = base64.b64decode(data["bytes"])
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 500  # Should contain table content

    @pytest.mark.asyncio
    async def test_execute_multiple_documents_combined(self, block: PdfReport) -> None:
        """Test that multiple documents are combined in findings section."""
        config = {
            "output_format": "pdf",
            "title": "Multi-Doc Test",
            "sections": ["executive_summary", "findings"],
        }
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {
                "documents": [
                    "# Executive Summary\n\nBrief overview.",
                    "## Detailed Analysis\n\nFull analysis here.",
                    "## Conclusion\n\nFinal thoughts.",
                ]
            },
        }

        result = await block.execute(inputs, config)
        assert "generic_blob" in result
        data = result["generic_blob"]["data"]
        pdf_bytes = base64.b64decode(data["bytes"])
        assert pdf_bytes.startswith(b"%PDF")
        # Multiple docs should produce larger PDF
        assert len(pdf_bytes) > 1000
