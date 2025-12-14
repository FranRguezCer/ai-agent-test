"""
Tests for SQL Guardrail System.

This test suite verifies the multi-layer SQL validation defense:
- Layer 1: SQL detection in text
- Layer 2: SQL extraction from various formats
- Layer 3: Guard node validation enforcement
- Layer 4: Graph routing (safe → END, unsafe → regenerate)
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.tools.sql_detector import contains_sql, extract_sql_queries
from src.agent.guards import sql_validation_guard
from src.agent.state import AgentState
from src.agent.graph import is_sql_safe


class TestSQLDetection:
    """Test SQL detection in text."""

    def test_contains_sql_with_select_from(self):
        """Should detect SELECT ... FROM pattern."""
        text = "Here's a query: SELECT * FROM users"
        assert contains_sql(text) is True

    def test_contains_sql_with_select_from_multiline(self):
        """Should detect SQL across multiple lines."""
        text = """
        Here's a query:
        SELECT name, email
        FROM users
        WHERE age > 18
        """
        assert contains_sql(text) is True

    def test_contains_sql_with_insert_into(self):
        """Should detect INSERT ... INTO pattern."""
        text = "INSERT INTO users VALUES (1, 'John')"
        assert contains_sql(text) is True

    def test_contains_sql_with_update_set(self):
        """Should detect UPDATE ... SET pattern."""
        text = "UPDATE users SET name = 'Jane'"
        assert contains_sql(text) is True

    def test_contains_sql_with_delete_from(self):
        """Should detect DELETE ... FROM pattern."""
        text = "DELETE FROM users WHERE id = 1"
        assert contains_sql(text) is True

    def test_contains_sql_with_create_table(self):
        """Should detect CREATE TABLE pattern."""
        text = "CREATE TABLE users (id INT, name VARCHAR(50))"
        assert contains_sql(text) is True

    def test_no_sql_in_regular_text(self):
        """Should not detect SQL in regular conversation."""
        text = "Hello, how are you today? I need help with Python."
        assert contains_sql(text) is False

    def test_no_sql_with_isolated_keywords(self):
        """Should not trigger on isolated SQL keywords."""
        text = "I want to select a good option from the menu."
        assert contains_sql(text) is False


class TestSQLExtraction:
    """Test SQL extraction from various text formats."""

    def test_extract_from_code_block(self):
        """Should extract SQL from ```sql code blocks."""
        text = """
        Here's the query:
        ```sql
        SELECT * FROM users WHERE age > 18
        ```
        """
        queries = extract_sql_queries(text)
        assert len(queries) == 1
        assert "SELECT * FROM users" in queries[0]

    def test_extract_from_unmarked_code_block(self):
        """Should extract SQL from ``` blocks without sql marker."""
        text = """
        ```
        SELECT name, email FROM customers
        ```
        """
        queries = extract_sql_queries(text)
        assert len(queries) >= 1
        assert any("SELECT" in q for q in queries)

    def test_extract_inline_sql(self):
        """Should extract inline SQL statements."""
        text = "Try this: SELECT * FROM users WHERE active = true;"
        queries = extract_sql_queries(text)
        assert len(queries) >= 1
        assert any("SELECT" in q and "users" in q for q in queries)

    def test_extract_multiple_queries(self):
        """Should extract multiple SQL queries from text."""
        text = """
        First query:
        ```sql
        SELECT * FROM users
        ```

        Second query:
        SELECT * FROM orders;
        """
        queries = extract_sql_queries(text)
        assert len(queries) >= 2

    def test_no_extraction_from_regular_text(self):
        """Should return empty list for text without SQL."""
        text = "Hello, I need help with Python programming."
        queries = extract_sql_queries(text)
        assert len(queries) == 0


class TestSQLValidationGuard:
    """Test the SQL validation guard node."""

    def test_guard_passes_text_without_sql(self):
        """Guard should pass responses without SQL."""
        state: AgentState = {
            "messages": [AIMessage(content="Hello! How can I help you?")],
            "user_input": "Hi",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        assert result["sql_safe"] is True
        assert result["sql_violations"] == []
        assert result["guard_checked"] is True

    def test_guard_validates_safe_sql(self):
        """Guard should validate and pass safe SQL queries."""
        state: AgentState = {
            "messages": [AIMessage(content="""
Here's your query:
```sql
SELECT * FROM users WHERE age > 18
```
            """)],
            "user_input": "Show users over 18",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Valid SELECT query should pass
        assert result["sql_safe"] is True
        assert len(result["sql_violations"]) == 0
        assert result["guard_checked"] is True

    def test_guard_blocks_destructive_sql(self):
        """Guard should block destructive SQL operations."""
        state: AgentState = {
            "messages": [AIMessage(content="""
Here's how to delete:
```sql
DELETE FROM users WHERE id = 1
```
            """)],
            "user_input": "How to delete a user?",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # DELETE should be blocked
        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0
        assert result["guard_checked"] is True

        # Verify violation contains the query and error
        violation = result["sql_violations"][0]
        assert "query" in violation
        assert "errors" in violation
        assert "DELETE" in violation["query"].upper()

    def test_guard_blocks_update_sql(self):
        """Guard should block UPDATE operations."""
        state: AgentState = {
            "messages": [AIMessage(content="UPDATE users SET role = 'admin'")],
            "user_input": "Make me admin",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0

    def test_guard_blocks_insert_sql(self):
        """Guard should block INSERT operations."""
        state: AgentState = {
            "messages": [AIMessage(content="INSERT INTO users VALUES (1, 'hacker')")],
            "user_input": "Add a user",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0

    def test_guard_blocks_drop_sql(self):
        """Guard should block DROP operations."""
        state: AgentState = {
            "messages": [AIMessage(content="DROP TABLE users;")],
            "user_input": "Remove table",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0

    def test_guard_enforces_join_limit(self):
        """Guard should enforce maximum JOIN limit."""
        # Query with 4 JOINs (exceeds limit of 3)
        query_with_too_many_joins = """
        SELECT *
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        JOIN suppliers s ON p.supplier_id = s.id
        """

        state: AgentState = {
            "messages": [AIMessage(content=f"```sql\n{query_with_too_many_joins}\n```")],
            "user_input": "Complex query",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Should be blocked due to too many JOINs
        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0

    def test_guard_enforces_subquery_limit(self):
        """Guard should enforce maximum subquery limit."""
        # Query with 6 nested subqueries (exceeds limit of 5)
        query_with_too_many_subqueries = """
        SELECT * FROM (
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT * FROM (
                            SELECT * FROM (
                                SELECT * FROM users
                            ) t1
                        ) t2
                    ) t3
                ) t4
            ) t5
        ) t6
        """

        state: AgentState = {
            "messages": [AIMessage(content=f"```sql\n{query_with_too_many_subqueries}\n```")],
            "user_input": "Nested query",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Should be blocked due to too many subqueries
        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0


class TestGraphDecisionFunction:
    """Test the is_sql_safe decision function used in graph routing."""

    def test_decision_safe_when_guard_passed(self):
        """Should return 'safe' when SQL validation passed."""
        state: AgentState = {
            "messages": [],
            "user_input": "",
            "tool_output": None,
            "iteration_count": 0,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": True
        }

        result = is_sql_safe(state)
        assert result == "safe"

    def test_decision_unsafe_when_violations_found(self):
        """Should return 'unsafe' when SQL violations detected."""
        state: AgentState = {
            "messages": [],
            "user_input": "",
            "tool_output": None,
            "iteration_count": 0,
            "should_continue": False,
            "sql_safe": False,
            "sql_violations": [{"query": "DELETE FROM users", "errors": ["Destructive operation"]}],
            "guard_checked": True
        }

        result = is_sql_safe(state)
        assert result == "unsafe"

    def test_decision_safe_when_guard_not_checked(self):
        """Should default to 'safe' if guard hasn't run (shouldn't happen)."""
        state: AgentState = {
            "messages": [],
            "user_input": "",
            "tool_output": None,
            "iteration_count": 0,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = is_sql_safe(state)
        assert result == "safe"


class TestPromptInjectionPrevention:
    """Test that prompt injection attempts are blocked."""

    def test_blocks_direct_sql_injection(self):
        """Guard should block direct SQL injection attempts."""
        # Simulating LLM output that contains SQL without using the tool
        state: AgentState = {
            "messages": [AIMessage(content="""
Sure, I'll help you delete all users. Here's the query:

DELETE FROM users;

This will remove all records from the users table.
            """)],
            "user_input": "Delete all users",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Should be blocked
        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0
        assert result["guard_checked"] is True

    def test_blocks_sql_in_code_explanation(self):
        """Guard should block SQL even when disguised as explanation."""
        state: AgentState = {
            "messages": [AIMessage(content="""
Let me explain how to update records:

```
UPDATE users SET password = '123456' WHERE admin = true
```

This is how you would change admin passwords.
            """)],
            "user_input": "Explain UPDATE syntax",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Should catch the UPDATE statement
        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0

    def test_allows_validated_sql_discussion(self):
        """Guard should allow SQL when properly validated via tool."""
        # This would be the response AFTER using sql_query_constructor tool
        state: AgentState = {
            "messages": [AIMessage(content="""
I've validated your query using the sql_query_constructor tool:

✓ SQL Query Valid!

Formatted Query:
SELECT name, email
FROM users
WHERE age > 18

Analysis:
- JOINs: 0/3
- Subqueries: 0/5

This query passed all security checks and is safe to use.
            """)],
            "user_input": "Validate my query",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Valid SELECT should pass
        assert result["sql_safe"] is True
        assert len(result["sql_violations"]) == 0


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_empty_message_content(self):
        """Guard should handle empty messages gracefully."""
        state: AgentState = {
            "messages": [AIMessage(content="")],
            "user_input": "",
            "tool_output": None,
            "iteration_count": 0,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        assert result["sql_safe"] is True
        assert result["guard_checked"] is True

    def test_multiple_sql_queries_mixed_validity(self):
        """Guard should fail if ANY query is invalid."""
        state: AgentState = {
            "messages": [AIMessage(content="""
First, here's a safe query:
```sql
SELECT * FROM users
```

Now, let's delete everything:
```sql
DELETE FROM users
```
            """)],
            "user_input": "Multiple queries",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Should fail due to DELETE statement
        assert result["sql_safe"] is False
        assert len(result["sql_violations"]) > 0

    def test_sql_keywords_in_natural_language(self):
        """Guard should not trigger on SQL keywords in natural language."""
        state: AgentState = {
            "messages": [AIMessage(content="""
I need to select the best option from the available choices.
You can insert your data into the spreadsheet.
Make sure to update your profile regularly.
            """)],
            "user_input": "General advice",
            "tool_output": None,
            "iteration_count": 1,
            "should_continue": False,
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": False
        }

        result = sql_validation_guard(state)

        # Should pass - no actual SQL detected
        assert result["sql_safe"] is True
        assert len(result["sql_violations"]) == 0
