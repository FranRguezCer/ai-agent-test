"""
SQL Query Validator Tool with Security Guardrails.

This tool validates SQL queries before execution, enforcing security
and complexity constraints. It performs dry-run validation without
actually connecting to a database.

Validation layers:
1. Statement type check (only SELECT allowed)
2. Keyword blocklist (destructive operations blocked)
3. Syntax validation (well-formed SQL)
4. Complexity limits (JOINs, subqueries)
"""

import sqlparse
from sqlparse.sql import Parenthesis
from sqlparse.tokens import Keyword
from langchain_core.tools import tool
from src.config.settings import get_settings


# Blocked SQL keywords (destructive operations)
BLOCKED_KEYWORDS = {
    'INSERT', 'UPDATE', 'DELETE', 'DROP',
    'ALTER', 'CREATE', 'TRUNCATE', 'REPLACE',
    'MERGE', 'UPSERT', 'GRANT', 'REVOKE',
    'EXEC', 'EXECUTE'
}


class SQLValidationResult:
    """
    Structured result from SQL validation.

    Attributes:
        valid: Whether the query passed all checks
        errors: List of error messages
        warnings: List of warning messages
        metadata: Additional information (formatted query, counts, etc.)
    """

    def __init__(self):
        self.valid = True
        self.errors = []
        self.warnings = []
        self.metadata = {}


def count_joins(statement) -> int:
    """
    Count JOIN keywords in a SQL statement.

    Recursively traverses the token tree to find all JOIN keywords
    (INNER JOIN, LEFT JOIN, RIGHT JOIN, OUTER JOIN, CROSS JOIN, etc.)

    Args:
        statement: Parsed SQL statement

    Returns:
        int: Number of JOINs found
    """
    count = 0
    for token in statement.tokens:
        if token.ttype is Keyword and 'JOIN' in token.value.upper():
            count += 1
        elif hasattr(token, 'tokens'):
            # Recursively count in nested tokens
            count += count_joins(token)
    return count


def count_subqueries(statement) -> int:
    """
    Count subqueries (nested SELECT statements) in a SQL statement.

    A subquery is a SELECT statement wrapped in parentheses.
    This function recursively counts them.

    Args:
        statement: Parsed SQL statement

    Returns:
        int: Number of subqueries found
    """
    count = 0
    for token in statement.tokens:
        if isinstance(token, Parenthesis):
            # Check if parenthesis contains a SELECT statement
            inner_sql = str(token).strip('()')
            try:
                inner_parsed = sqlparse.parse(inner_sql)
                if inner_parsed and inner_parsed[0].get_type() == 'SELECT':
                    count += 1
                    # Recursively count nested subqueries
                    count += count_subqueries(inner_parsed[0])
            except Exception:
                # If parsing fails, skip this parenthesis
                pass
        elif hasattr(token, 'tokens'):
            # Recursively check nested tokens
            count += count_subqueries(token)
    return count


def validate_sql_query(query: str) -> SQLValidationResult:
    """
    Validate a SQL query against security and complexity constraints.

    Validation layers:
    1. Parse the query (syntax check)
    2. Check statement type (only SELECT allowed)
    3. Scan for blocked keywords (INSERT, UPDATE, DELETE, etc.)
    4. Count JOINs and enforce limit
    5. Count subqueries and enforce limit

    Args:
        query: SQL query string to validate

    Returns:
        SQLValidationResult: Validation result with errors and metadata
    """
    settings = get_settings()
    result = SQLValidationResult()

    # Layer 1: Parse the query
    try:
        parsed = sqlparse.parse(query)
        if not parsed:
            result.valid = False
            result.errors.append("Empty or invalid SQL query")
            return result

        statement = parsed[0]
    except Exception as e:
        result.valid = False
        result.errors.append(f"SQL parsing failed: {str(e)}")
        return result

    # Layer 2: Check statement type (only SELECT allowed)
    stmt_type = statement.get_type()
    if stmt_type != 'SELECT':
        result.valid = False
        result.errors.append(
            f"Only SELECT statements allowed, got: {stmt_type}"
        )
        return result

    # Layer 3: Blocklist check - scan all tokens for forbidden keywords
    tokens = list(statement.flatten())
    for token in tokens:
        if token.ttype is Keyword:
            keyword = token.value.upper()
            if keyword in BLOCKED_KEYWORDS:
                result.valid = False
                result.errors.append(f"Blocked keyword found: {keyword}")

    # Layer 4: Count JOINs and enforce limit
    join_count = count_joins(statement)
    result.metadata['join_count'] = join_count
    if join_count > settings.sql_max_joins:
        result.valid = False
        result.errors.append(
            f"Too many JOINs: {join_count} (max: {settings.sql_max_joins})"
        )

    # Layer 5: Count subqueries and enforce limit
    subquery_count = count_subqueries(statement)
    result.metadata['subquery_count'] = subquery_count
    if subquery_count > settings.sql_max_subqueries:
        result.valid = False
        result.errors.append(
            f"Too many subqueries: {subquery_count} "
            f"(max: {settings.sql_max_subqueries})"
        )

    # Add formatted query to metadata (pretty-printed)
    result.metadata['formatted_query'] = sqlparse.format(
        query,
        reindent=True,
        keyword_case='upper'
    )

    return result


@tool
def sql_query_constructor(query: str) -> str:
    """
    SQL Query Constructor Tool with validation guardrails.

    This tool validates and analyzes SQL SELECT queries without executing them.
    It enforces security and complexity constraints to prevent dangerous queries.

    Constraints:
    - Only SELECT statements allowed
    - No INSERT, UPDATE, DELETE, DROP, or other destructive operations
    - Maximum 3 JOINs
    - Maximum 5 subqueries

    Args:
        query: The SQL query string to validate

    Returns:
        A detailed validation report including errors, warnings, and analysis

    Example:
        >>> sql_query_constructor("SELECT * FROM users WHERE age > 18")
        "✓ SQL Query Valid!

        Formatted Query:
        SELECT *
        FROM users
        WHERE age > 18

        Analysis:
        - JOINs: 0/3
        - Subqueries: 0/5

        This query is safe and ready for execution (dry-run mode)."
    """
    result = validate_sql_query(query)

    if result.valid:
        return f"""✓ SQL Query Valid!

Formatted Query:
{result.metadata['formatted_query']}

Analysis:
- JOINs: {result.metadata['join_count']}/{get_settings().sql_max_joins}
- Subqueries: {result.metadata['subquery_count']}/{get_settings().sql_max_subqueries}

This query is safe and ready for execution (dry-run mode).
"""
    else:
        error_msg = "\n".join(f"  - {err}" for err in result.errors)
        return f"""✗ SQL Query Validation Failed!

Errors:
{error_msg}

Please fix these issues before proceeding.
"""


# Register the tool in the global registry
from src.tools.registry import register_tool
register_tool(sql_query_constructor)
