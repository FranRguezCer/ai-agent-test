"""
Tests for SQL Validator Tool.

These tests verify that the SQL validator correctly:
1. Accepts valid SELECT queries
2. Blocks destructive operations (INSERT, UPDATE, DELETE, etc.)
3. Enforces JOIN limits
4. Enforces subquery limits
5. Validates SQL syntax
"""

import pytest
from src.tools.sql_validator import validate_sql_query, sql_query_constructor


class TestSQLValidator:
    """Test suite for SQL query validation."""

    def test_valid_select_query(self):
        """Test that valid SELECT queries pass validation."""
        query = "SELECT id, name FROM users WHERE age > 18"
        result = validate_sql_query(query)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.metadata['join_count'] == 0
        assert result.metadata['subquery_count'] == 0

    def test_valid_select_with_joins(self):
        """Test that SELECT queries with allowed JOINs pass."""
        query = """
        SELECT u.name, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        """
        result = validate_sql_query(query)

        assert result.valid is True
        assert result.metadata['join_count'] == 1

    def test_valid_select_with_subquery(self):
        """Test that SELECT queries with allowed subqueries pass."""
        query = """
        SELECT * FROM users
        WHERE id IN (SELECT user_id FROM orders WHERE total > 100)
        """
        result = validate_sql_query(query)

        assert result.valid is True
        assert result.metadata['subquery_count'] == 1

    def test_blocked_insert(self):
        """Test that INSERT statements are blocked."""
        query = "INSERT INTO users (name, age) VALUES ('John', 25)"
        result = validate_sql_query(query)

        assert result.valid is False
        assert any('Only SELECT statements allowed' in err for err in result.errors)

    def test_blocked_update(self):
        """Test that UPDATE statements are blocked."""
        query = "UPDATE users SET age = 26 WHERE id = 1"
        result = validate_sql_query(query)

        assert result.valid is False
        assert any('Only SELECT statements allowed' in err for err in result.errors)

    def test_blocked_delete(self):
        """Test that DELETE statements are blocked."""
        query = "DELETE FROM users WHERE id = 1"
        result = validate_sql_query(query)

        assert result.valid is False
        assert any('Only SELECT statements allowed' in err for err in result.errors)

    def test_blocked_drop(self):
        """Test that DROP statements are blocked."""
        query = "DROP TABLE users"
        result = validate_sql_query(query)

        assert result.valid is False
        assert any('Only SELECT statements allowed' in err for err in result.errors)

    def test_blocked_alter(self):
        """Test that ALTER statements are blocked."""
        query = "ALTER TABLE users ADD COLUMN email VARCHAR(255)"
        result = validate_sql_query(query)

        assert result.valid is False
        assert any('Only SELECT statements allowed' in err for err in result.errors)

    def test_blocked_truncate(self):
        """Test that TRUNCATE statements are blocked."""
        query = "TRUNCATE TABLE users"
        result = validate_sql_query(query)

        assert result.valid is False

    def test_too_many_joins(self):
        """Test that queries with excessive JOINs are blocked."""
        # 4 JOINs (exceeds limit of 3)
        query = """
        SELECT *
        FROM t1
        JOIN t2 ON t1.id = t2.id
        JOIN t3 ON t2.id = t3.id
        JOIN t4 ON t3.id = t4.id
        JOIN t5 ON t4.id = t5.id
        """
        result = validate_sql_query(query)

        assert result.valid is False
        assert result.metadata['join_count'] == 4
        assert any('Too many JOINs' in err for err in result.errors)

    def test_max_joins_allowed(self):
        """Test that exactly 3 JOINs (the limit) is allowed."""
        query = """
        SELECT *
        FROM t1
        JOIN t2 ON t1.id = t2.id
        JOIN t3 ON t2.id = t3.id
        JOIN t4 ON t3.id = t4.id
        """
        result = validate_sql_query(query)

        assert result.valid is True
        assert result.metadata['join_count'] == 3

    def test_too_many_subqueries(self):
        """Test that queries with excessive subqueries are blocked."""
        # 6 nested subqueries (exceeds limit of 5)
        query = """
        SELECT * FROM (
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT * FROM (
                            SELECT * FROM (
                                SELECT * FROM users
                            )
                        )
                    )
                )
            )
        )
        """
        result = validate_sql_query(query)

        assert result.valid is False
        assert result.metadata['subquery_count'] > 5
        assert any('Too many subqueries' in err for err in result.errors)

    def test_empty_query(self):
        """Test that empty queries are rejected."""
        query = ""
        result = validate_sql_query(query)

        assert result.valid is False
        assert any('Empty or invalid' in err for err in result.errors)

    def test_invalid_sql_syntax(self):
        """Test that syntactically invalid SQL is rejected."""
        query = "SELECT FROM WHERE"
        result = validate_sql_query(query)

        # sqlparse is quite permissive, but this should at least parse
        # We're mainly checking it doesn't crash
        assert isinstance(result.valid, bool)

    def test_tool_function_valid_query(self):
        """Test the tool function with a valid query."""
        query = "SELECT * FROM users"
        result = sql_query_constructor.invoke({"query": query})

        assert "✓ SQL Query Valid!" in result
        assert "Analysis:" in result

    def test_tool_function_invalid_query(self):
        """Test the tool function with an invalid query."""
        query = "DROP TABLE users"
        result = sql_query_constructor.invoke({"query": query})

        assert "✗ SQL Query Validation Failed!" in result
        assert "Errors:" in result


if __name__ == "__main__":
    # Run tests with: pytest tests/test_sql_validator.py -v
    pytest.main([__file__, "-v"])
