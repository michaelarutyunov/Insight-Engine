"""Tests for CSVLoader block."""

import tempfile

import pytest

from blocks.sources.csv_loader import CSVLoader


class TestCSVLoader:
    """Test suite for CSVLoader source block."""

    @pytest.fixture
    def block(self):
        """Return a CSVLoader instance."""
        return CSVLoader()

    def test_block_type(self, block):
        """Source blocks must declare themselves as 'source'."""
        assert block.block_type == "source"

    def test_input_schemas_empty(self, block):
        """Source blocks have no input schemas."""
        assert block.input_schemas == []

    def test_output_schemas(self, block):
        """Must produce respondent_collection."""
        assert block.output_schemas == ["respondent_collection"]

    def test_config_schema_structure(self, block):
        """Config schema must be valid JSON Schema."""
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "file_path" in schema["properties"]
        assert schema["required"] == ["file_path"]

    def test_validate_config_valid(self, block):
        """Valid config passes validation."""
        config = {"file_path": "/tmp/test.csv"}
        assert block.validate_config(config) is True

    def test_validate_config_missing_file_path(self, block):
        """Missing file_path fails validation."""
        config = {}
        assert block.validate_config(config) is False

    def test_validate_config_empty_file_path(self, block):
        """Empty file_path fails validation."""
        config = {"file_path": "   "}
        assert block.validate_config(config) is False

    def test_validate_config_invalid_delimiter(self, block):
        """Delimiter must be a single character."""
        config = {"file_path": "/tmp/test.csv", "delimiter": "||"}
        assert block.validate_config(config) is False

    def test_validate_config_with_all_options(self, block):
        """All valid config options pass validation."""
        config = {
            "file_path": "/tmp/test.csv",
            "delimiter": ";",
            "encoding": "latin-1",
            "has_header": False,
        }
        assert block.validate_config(config) is True

    @pytest.mark.asyncio
    async def test_execute_with_header(self, block):
        """Read CSV with header row."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("name,age,city\n")
            f.write("Alice,30,NYC\n")
            f.write("Bob,25,LA\n")
            temp_path = f.name

        try:
            config = {"file_path": temp_path}
            result = await block.execute({}, config)
            assert "respondent_collection" in result
            rows = result["respondent_collection"]["rows"]
            assert len(rows) == 2
            assert rows[0]["name"] == "Alice"
            assert rows[0]["age"] == "30"
            assert rows[1]["city"] == "LA"
        finally:
            import os

            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_without_header(self, block):
        """Read CSV without header row generates column names."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Alice,30,NYC\n")
            f.write("Bob,25,LA\n")
            temp_path = f.name

        try:
            config = {"file_path": temp_path, "has_header": False}
            result = await block.execute({}, config)
            rows = result["respondent_collection"]["rows"]
            assert len(rows) == 2
            assert rows[0]["col0"] == "Alice"
            assert rows[1]["col2"] == "LA"
        finally:
            import os

            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_custom_delimiter(self, block):
        """Read CSV with semicolon delimiter."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("name;age;city\n")
            f.write("Alice;30;NYC\n")
            temp_path = f.name

        try:
            config = {"file_path": temp_path, "delimiter": ";"}
            result = await block.execute({}, config)
            rows = result["respondent_collection"]["rows"]
            assert rows[0]["name"] == "Alice"
        finally:
            import os

            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_custom_encoding(self, block):
        """Read CSV with latin-1 encoding."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="latin-1"
        ) as f:
            # Use a character that differs between encodings
            f.write("name,city\n")
            f.write("José,São Paulo\n")
            temp_path = f.name

        try:
            config = {"file_path": temp_path, "encoding": "latin-1"}
            result = await block.execute({}, config)
            rows = result["respondent_collection"]["rows"]
            assert rows[0]["name"] == "José"
        finally:
            import os

            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_file_not_found(self, block):
        """Missing file raises FileNotFoundError."""
        config = {"file_path": "/nonexistent/path/to/file.csv"}
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            await block.execute({}, config)

    def test_test_fixtures(self, block):
        """test_fixtures must return expected structure."""
        fixtures = block.test_fixtures()
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures
        assert "respondent_collection" in fixtures["expected_output"]
        assert fixtures["config"]["file_path"]
        assert fixtures["config"]["delimiter"] == ","

    def test_description(self, block):
        """Block should have a description."""
        description = block.description
        assert isinstance(description, str)
        assert len(description) > 0
        assert "CSV" in description or "csv" in description
