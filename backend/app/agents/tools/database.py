"""Database Query Tool.

Provides a SQL query execution tool with read-only enforcement,
parameterized queries, and result formatting.
"""

import json
import os
import re

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum rows to return
MAX_ROWS = 100

# Maximum column width for display
MAX_COLUMN_WIDTH = 100

# Query timeout in seconds
QUERY_TIMEOUT = 30

# SQL statements that modify data
WRITE_STATEMENTS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _is_write_query(query: str) -> bool:
    """Check if a SQL query is a write/modification statement."""
    # Strip comments
    stripped = re.sub(r"--[^\n]*", "", query)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    return bool(WRITE_STATEMENTS.match(stripped.strip()))


def _format_as_markdown_table(columns: list[str], rows: list[tuple]) -> str:
    """Format query results as a markdown table."""
    if not columns:
        return "No columns returned."

    if not rows:
        return f"Columns: {', '.join(columns)}\n\n(0 rows)"

    # Truncate column values for display
    str_rows = []
    for row in rows:
        str_row = []
        for val in row:
            s = str(val) if val is not None else "NULL"
            if len(s) > MAX_COLUMN_WIDTH:
                s = s[: MAX_COLUMN_WIDTH - 3] + "..."
            str_row.append(s)
        str_rows.append(str_row)

    # Calculate column widths
    widths = [len(c) for c in columns]
    for row in str_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Build header
    header = "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns)) + " |"
    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"

    # Build rows
    data_lines = []
    for row in str_rows:
        line = "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(columns))) + " |"
        data_lines.append(line)

    return "\n".join([header, separator, *data_lines])


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class ExecuteSqlInput(BaseModel):
    """Input schema for execute_sql tool."""

    query: str = Field(
        ...,
        description="SQL query to execute",
    )
    database_url: str | None = Field(
        default=None,
        description="Database connection URL (postgresql://user:pass@host/db). Uses DATABASE_URL env var if not provided.",
    )
    params: dict | None = Field(
        default=None,
        description="Query parameters for parameterized queries (e.g., {'name': 'Alice'}). Use $1, $2, etc. in query.",
    )
    read_only: bool = Field(
        default=True,
        description="If True (default), only SELECT queries are allowed. Set to False for INSERT/UPDATE/DELETE.",
    )


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool(args_schema=ExecuteSqlInput)
async def execute_sql(
    query: str,
    database_url: str | None = None,
    params: dict | None = None,
    read_only: bool = True,
) -> str:
    """Execute a SQL query against a PostgreSQL database.

    Use this tool to query databases for data analysis, reporting, or
    data retrieval. By default, only SELECT queries are allowed (read-only mode).

    For parameterized queries, use $1, $2, etc. as placeholders and pass
    values in the params dict.

    Args:
        query: SQL query to execute
        database_url: Database connection URL (uses DATABASE_URL env var if not provided)
        params: Optional query parameters for parameterized queries
        read_only: If True (default), only SELECT queries are allowed

    Returns:
        Query results as formatted markdown table or affected row count
    """
    logger.info("execute_sql_invoked", query=query[:200], read_only=read_only)

    # Resolve database URL
    db_url = database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        return json.dumps({
            "success": False,
            "error": "No database URL provided. Set DATABASE_URL environment variable or pass database_url parameter.",
        })

    # Enforce read-only mode
    if read_only and _is_write_query(query):
        return json.dumps({
            "success": False,
            "error": "Write operations (INSERT, UPDATE, DELETE, DROP, etc.) are not allowed in read-only mode. Set read_only=False to enable.",
        })

    try:
        import asyncpg
    except ImportError:
        return json.dumps({
            "success": False,
            "error": "asyncpg is not installed. Install it with: pip install asyncpg",
        })

    conn = None
    try:
        conn = await asyncpg.connect(db_url, timeout=QUERY_TIMEOUT)

        # Convert dict params to positional args for asyncpg
        query_args = []
        if params:
            # asyncpg uses $1, $2, ... positional parameters
            # Convert dict to ordered list based on $N references in query
            for i in range(1, len(params) + 1):
                key = f"${i}"
                # Find the dict key that maps to this position
                # Support both numeric keys and named keys in order
                if str(i) in params:
                    query_args.append(params[str(i)])
                elif i - 1 < len(params):
                    query_args.append(list(params.values())[i - 1])

        # Check if it's a SELECT-like query that returns rows
        stripped = query.strip().upper()
        is_select = stripped.startswith("SELECT") or stripped.startswith("WITH") or stripped.startswith("EXPLAIN")

        if is_select:
            rows = await conn.fetch(query, *query_args, timeout=QUERY_TIMEOUT)

            if not rows:
                return json.dumps({
                    "success": True,
                    "table": "No rows returned.",
                    "row_count": 0,
                    "query": query,
                })

            # Get column names
            columns = list(rows[0].keys())

            # Limit rows
            truncated = len(rows) > MAX_ROWS
            limited_rows = rows[:MAX_ROWS]

            # Convert to tuples
            tuple_rows = [tuple(row[c] for c in columns) for row in limited_rows]

            table = _format_as_markdown_table(columns, tuple_rows)

            result = {
                "success": True,
                "table": table,
                "row_count": len(rows),
                "columns": columns,
                "query": query,
            }

            if truncated:
                result["truncated"] = True
                result["message"] = f"Showing first {MAX_ROWS} of {len(rows)} rows"

            logger.info("execute_sql_completed", row_count=len(rows), columns=len(columns))
            return json.dumps(result, default=str)

        else:
            # Execute non-SELECT statement
            status = await conn.execute(query, *query_args, timeout=QUERY_TIMEOUT)

            logger.info("execute_sql_completed", status=status)
            return json.dumps({
                "success": True,
                "status": status,
                "query": query,
            })

    except asyncpg.PostgresError as e:
        logger.error("execute_sql_postgres_error", error=str(e))
        return json.dumps({
            "success": False,
            "error": f"Database error: {e}",
            "query": query,
        })
    except TimeoutError:
        logger.error("execute_sql_timeout", query=query[:200])
        return json.dumps({
            "success": False,
            "error": f"Query timed out after {QUERY_TIMEOUT} seconds",
            "query": query,
        })
    except Exception as e:
        logger.error("execute_sql_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": f"Query execution failed: {e}",
            "query": query,
        })
    finally:
        if conn:
            await conn.close()
