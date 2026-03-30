"""Database Source block -- loads respondent data from SQL queries.

Supports SQLite (via aiosqlite) and PostgreSQL (via psycopg v3 async).
Connection type is detected from the connection_string prefix:
  - sqlite://      -> aiosqlite
  - postgresql://  -> psycopg AsyncConnection
"""

import asyncio
from typing import Any

import aiosqlite

from blocks._llm_client import BlockExecutionError
from blocks.base import SourceBase


class DBSource(SourceBase):
    """Entry point that runs a SQL query and returns a respondent_collection.

    Detects the database backend from the connection_string prefix and
    delegates to the appropriate async driver. Supports SQLite (aiosqlite)
    for local/file-based databases and PostgreSQL (psycopg v3) for
    server-based databases.
    """

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "connection_string": {
                    "type": "string",
                    "description": (
                        "Database connection URI. Use 'sqlite://' prefix for "
                        "SQLite or 'postgresql://' for PostgreSQL."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "SQL query to execute. Must be a SELECT statement.",
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 600,
                    "description": "Query execution timeout in seconds (default 30).",
                },
            },
            "required": ["connection_string", "query"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Load structured data from a database into your pipeline by executing "
            "a SQL query. Supports SQLite (via aiosqlite) and PostgreSQL (via "
            "psycopg v3). Connection type is auto-detected from the "
            "connection_string prefix. Each row in the result set becomes a "
            "record in a respondent_collection. Use as a pipeline entry point "
            "when your source data lives in a relational database."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Assumes the query returns a well-defined column structure. All "
            "values are returned as their native Python types (strings, integers, "
            "floats, dates as strings, etc.). For large result sets, consider "
            "adding a LIMIT clause or using a Transform block downstream for "
            "chunked processing. Connection credentials in the connection string "
            "should be provided via environment variables rather than hardcoded."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "data-import",
            "database",
            "sql",
            "sqlite",
            "postgresql",
            "structured-input",
        ]

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config, dict):
            return False
        conn = config.get("connection_string")
        query = config.get("query")
        if not isinstance(conn, str) or not conn.strip():
            return False
        if not isinstance(query, str) or not query.strip():
            return False
        if not (conn.startswith("sqlite://") or conn.startswith("postgresql://")):
            return False
        timeout = config.get("timeout", 30)
        if not isinstance(timeout, int) or timeout < 1 or timeout > 600:
            return False
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        _ = inputs  # source blocks take no inputs
        connection_string = config["connection_string"]
        query = config["query"]
        timeout = config.get("timeout", 30)

        if connection_string.startswith("sqlite://"):
            rows = await self._execute_sqlite(connection_string, query, timeout)
        elif connection_string.startswith("postgresql://"):
            rows = await self._execute_postgres(connection_string, query, timeout)
        else:
            raise BlockExecutionError(
                f"Unsupported connection_string prefix: {connection_string[:20]}..."
            )

        return {"respondent_collection": {"rows": rows}}

    async def _execute_sqlite(
        self, connection_string: str, query: str, timeout: int
    ) -> list[dict[str, Any]]:
        """Execute a query against a SQLite database via aiosqlite."""
        db_path = connection_string[len("sqlite://") :]
        try:
            async with asyncio.timeout(timeout):
                async with aiosqlite.connect(db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(query) as cursor:
                        columns = [desc[0] for desc in cursor.description]
                        return [
                            dict(zip(columns, row)) for row in await cursor.fetchall()
                        ]
        except TimeoutError as exc:
            raise BlockExecutionError(
                f"SQLite query timed out after {timeout}s"
            ) from exc
        except Exception as exc:
            raise BlockExecutionError(
                f"SQLite query failed: {exc}"
            ) from exc

    async def _execute_postgres(
        self, connection_string: str, query: str, timeout: int
    ) -> list[dict[str, Any]]:
        """Execute a query against a PostgreSQL database via psycopg v3."""
        import psycopg

        try:
            async with asyncio.timeout(timeout):
                async with await psycopg.AsyncConnection.connect(
                    connection_string
                ) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(query)
                        columns = [desc[0] for desc in cur.description]
                        return [
                            dict(zip(columns, row)) for row in await cur.fetchall()
                        ]
        except TimeoutError as exc:
            raise BlockExecutionError(
                f"PostgreSQL query timed out after {timeout}s"
            ) from exc
        except Exception as exc:
            raise BlockExecutionError(
                f"PostgreSQL query failed: {exc}"
            ) from exc

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "connection_string": "sqlite://:memory:",
                "query": "SELECT 1 AS id, 'Alice' AS name",
                "timeout": 10,
            },
            "inputs": {},
            "expected_output": {
                "respondent_collection": {
                    "rows": [{"id": 1, "name": "Alice"}],
                },
            },
        }
