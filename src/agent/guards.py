"""
Security Guard Nodes.

This module implements security guardrails that enforce validation
of sensitive operations. Guards run after the LLM generates responses
to ensure security policies are enforced.

Key Concept:
-----------
Guards are nodes that validate LLM output and can force regeneration
if security violations are detected. This provides defense-in-depth
beyond just instructing the LLM to follow rules.
"""

from src.agent.state import AgentState
from src.tools.sql_detector import contains_sql, extract_sql_queries
from src.tools.sql_validator import validate_sql_query


def sql_validation_guard(state: AgentState) -> dict:
    """
    SQL Validation Guard Node.

    This guard ensures that any SQL in the LLM's response has been
    validated through the sql_query_constructor tool.

    Security Guarantee:
    ------------------
    - Scans LLM response for SQL content
    - Validates any SQL found against security rules
    - If invalid SQL detected, marks response as unsafe
    - Forces response regeneration on unsafe SQL

    This prevents prompt injection attacks where users try to trick
    the LLM into outputting dangerous SQL without validation.

    Args:
        state: Current agent state

    Returns:
        dict: State updates with SQL safety information
            - sql_safe: bool indicating if response is safe
            - sql_violations: list of validation errors found
            - guard_checked: bool flag that guard ran

    Examples:
        Safe response:
            LLM: "I'll validate that query for you..."
            Guard: sql_safe=True (no SQL in response)

        Unsafe response:
            LLM: "Here's your query: DELETE FROM users"
            Guard: sql_safe=False (destructive SQL detected)
    """
    # Get the last message (should be from think_node or respond_node)
    messages = state["messages"]
    if not messages:
        return {
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": True
        }

    last_message = messages[-1]

    # Only check AI messages (not tool messages or user messages)
    if not hasattr(last_message, 'content'):
        return {
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": True
        }

    content = last_message.content

    # Check if SQL is present in the response
    if not contains_sql(content):
        # No SQL detected - response is safe
        return {
            "sql_safe": True,
            "sql_violations": [],
            "guard_checked": True
        }

    # SQL detected - extract and validate all queries
    queries = extract_sql_queries(content)
    violations = []

    for query in queries:
        # Validate each query
        result = validate_sql_query(query)

        if not result.valid:
            # This query violates security rules
            violations.append({
                "query": query,
                "errors": result.errors,
                "metadata": result.metadata
            })

    # Response is safe only if all SQL queries are valid
    is_safe = len(violations) == 0

    return {
        "sql_safe": is_safe,
        "sql_violations": violations,
        "guard_checked": True
    }
