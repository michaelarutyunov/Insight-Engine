"""Tests for the DBSource block.

Verifies:
  - Full BlockBase contract compliance (via contract tests)
  - SQLite execution against in-memory database
  - Config validation
  - Timeout handling
  - PostgreSQL code path (smoke test, import only)
"""

import pytest

from blocks._llm_client import BlockExecutionError
from blocks.sources.db_source import DBSource


class TestDBSourceContract:
    """Contract tests that the DBSource block type."""

    def test_block_type(self):
        assert DBSource().block_type == "source"

    def test_input_schemas_empty(self):
        assert DBSource().input_schemas == []

    def test_output_schemas(self):
        assert DBSource().output_schemas == ["respondent_collection"]

    def test_config_schema_structure(self):
        schema = DBSource().config_schema
        assert schema["type"] == "object"
        assert "connection_string" in schema["properties"]
        assert "query" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert set(schema["required"]) == {"connection_string", "query"}

    def test_description_nonempty(self):
        assert isinstance(DBSource().description, str)
        assert len(DBSource().description) > 0

    def test_methodological_notes_nonempty(self):
        assert isinstance(DBSource().methodological_notes, str)
        assert len(DBSource().methodological_notes) > 0

    def test_tags(self):
        tags = DBSource().tags
        assert isinstance(tags, list)
        assert len(tags) > 0

    def test_test_fixtures_structure(self):
        fixtures = DBSource().test_fixtures()
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

    def test_validate_config_accepts_valid(self):
        config = {
            "connection_string": "sqlite:///test.db",
            "query": "SELECT * FROM users",
            "timeout": 30,
        }
        assert DBSource().validate_config(config) is True

    def test_validate_config_rejects_missing_connection_string(self):
        assert DBSource().validate_config({"query": "SELECT 1"}) is False

    def test_validate_config_rejects_missing_query(self):
        assert DBSource().validate_config({"connection_string": "sqlite:///test.db"}) is False

    def test_validate_config_rejects_empty_strings(self):
        assert (
            DBSource().validate_config({"connection_string": "sqlite:///test.db", "query": "  "})
            is False
        )

    def test_validate_config_rejects_bad_prefix(self):
        assert (
            DBSource().validate_config(
                {"connection_string": "mysql://localhost/db", "query": "SELECT 1"}
            )
            is False
        )

    def test_validate_config_rejects_bad_timeout(self):
        assert (
            DBSource().validate_config(
                {
                    "connection_string": "sqlite:///test.db",
                    "query": "SELECT 1",
                    "timeout": 0,
                }
            )
            is False
        )

    def test_validate_config_accepts_default_timeout(self):
        config = {
            "connection_string": "sqlite:///test.db",
            "query": "SELECT 1",
        }
        assert DBSource().validate_config(config) is True


class TestDBSourceSQLite:
    """Integration tests for DBSource using SQLite in-memory database."""

    @pytest.fixture
    async def setup_db(self):
        """Create an in-memory SQLite database with test data."""
        import aiosqlite

        db = await aiosqlite.connect(":memory:")
        await db.execute(
            "CREATE TABLE respondents (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, city TEXT)"
        )
        await db.executemany(
            "INSERT INTO respondents (id, name, age, city) VALUES (?, ?, ?, ?)",
            [(1, "Alice", 30, "NYC"), (2, "Bob", 25, "LA"), (3, "Carol", 35, "Chicago")],
        )
        await db.commit()
        yield db

    @pytest.mark.usefixtures("setup_db")
    async def test_execute_sqlite_basic(self, setup_db):
        """Execute a basic SELECT query against SQLite."""
        block = DBSource()
        result = await block.execute(
            inputs={},
            config={
                "connection_string": "sqlite://:memory:",
                "query": "SELECT id, name, age, city FROM respondents ORDER BY id",
            },
        )
        assert "respondent_collection" in result
        rows = result["respondent_collection"]["rows"]
        assert len(rows) == 3
        assert rows[0] == {"id": 1, "name": "Alice", "age": 30, "city": "NYC"}
        assert rows[1] == {"id": 2, "name": "Bob", "age": 25, "city": "LA"}
        assert rows[2] == {"id": 3, "name": "Carol", "age": 35, "city": "Chicago"}

    @pytest.mark.usefixtures("setup_db")
    async def test_execute_sqlite_with_custom_timeout(self, setup_db):
        """Verify custom timeout config is passed through."""
        block = DBSource()
        result = await block.execute(
            inputs={},
            config={
                "connection_string": "sqlite://:memory:",
                "query": "SELECT id, name FROM respondents WHERE age > 25",
                "timeout": 60,
            },
        )
        rows = result["respondent_collection"]["rows"]
        assert len(rows) == 2  # Alice (30) and Carol (35)

    @pytest.mark.usefixtures("setup_db")
    async def test_execute_sqlite_empty_result(self, setup_db):
        """Execute a query that returns no rows."""
        block = DBSource()
        result = await block.execute(
            inputs={},
            config={
                "connection_string": "sqlite://:memory:",
                "query": "SELECT * FROM respondents WHERE age > 100",
            },
        )
        rows = result["respondent_collection"]["rows"]
        assert rows == []

    async def test_execute_sqlite_bad_query(self):
        """Execute an invalid SQL query raises BlockExecutionError."""
        block = DBSource()
        with pytest.raises(BlockExecutionError, match="SQLite query failed"):
            await block.execute(
                inputs={},
                config={
                    "connection_string": "sqlite://:memory:",
                    "query": "SELECT * FROM nonexistent_table",
                },
            )

    async def test_execute_sqlite_timeout(self):
        """Verify that slow queries can time out."""
        block = DBSource()
        with pytest.raises(BlockExecutionError, match="timed out"):
            await block.execute(
                inputs={},
                config={
                    "connection_string": "sqlite://:memory:",
                    "query": "SELECT 1",
                    "timeout": 1,
                },
            )


class TestDBSourcePostgres:
    """Tests for the PostgreSQL code path (import-level smoke test).

    The PostgreSQL path is tested via mock to avoid requiring a running
    Postgres server in CI.
    """

    def test_postgres_import_available(self):
        """Verify psycopg can be imported within the block."""
        import psycopg

        assert hasattr(psycopg, "AsyncConnection")

    async def test_execute_postgres_delegates_correctly(self):
        """Verify that _execute_postgres is called for postgresql:// URLs."""
        from unittest.mock import AsyncMock

        block = DBSource()
        mock_rows = [{"id": 1, "name": "Test"}]
        block._execute_postgres = AsyncMock(return_value=mock_rows)

        result = await block.execute(
            inputs={},
            config={
                "connection_string": "postgresql://user:pass@localhost/testdb",
                "query": "SELECT * FROM users",
            },
        )
        assert result == {"respondent_collection": {"rows": mock_rows}}
        block._execute_postgres.assert_awaited_once()

    async def test_execute_unsupported_prefix(self):
        """Verify unsupported connection_string prefix raises error."""
        block = DBSource()
        with pytest.raises(BlockExecutionError, match="Unsupported"):
            await block.execute(
                inputs={},
                config={
                    "connection_string": "mysql://localhost/db",
                    "query": "SELECT 1",
                },
            )
