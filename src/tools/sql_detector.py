"""
SQL Detection Utility.

This module provides utilities to detect and extract SQL queries from text.
Used by the SQL validation guardrail to ensure all SQL is validated.
"""

import re
from typing import List


# SQL keywords that indicate a query
SQL_KEYWORDS = {
    'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP',
    'ALTER', 'TRUNCATE', 'MERGE', 'UPSERT', 'REPLACE'
}


def contains_sql(text: str) -> bool:
    """
    Check if text contains SQL statements.

    Uses heuristic detection based on SQL keywords followed by
    typical SQL syntax patterns.

    Args:
        text: Text to check for SQL content

    Returns:
        bool: True if SQL detected, False otherwise

    Examples:
        >>> contains_sql("SELECT * FROM users")
        True
        >>> contains_sql("Hello, how are you?")
        False
        >>> contains_sql("I need to select a user from the database")
        False  # 'select' in conversational context
    """
    # First, check for SQL in code blocks (most reliable)
    if re.search(r'```(?:sql)?.*?```', text, re.DOTALL | re.IGNORECASE):
        code_content = re.search(r'```(?:sql)?\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
        if code_content:
            if contains_sql_patterns(code_content.group(1)):
                return True

    # Remove code blocks for inline detection to avoid double-counting
    text_no_blocks = re.sub(r'```(?:sql)?.*?```', '', text, flags=re.DOTALL | re.IGNORECASE)
    text_upper = text_no_blocks.upper()

    # Check for SQL keywords followed by typical SQL syntax
    # Use DOTALL to match across newlines
    for keyword in SQL_KEYWORDS:
        # Pattern: keyword followed by FROM, INTO, TABLE, etc.
        # More strict: require the keyword to be followed by SQL syntax within reasonable distance
        # Match: SELECT * FROM, SELECT column FROM, SELECT col1, col2 FROM
        if re.search(rf'\b{keyword}\b\s+(?:\*|\w+(?:\s*,\s*\w+)*)\s+FROM\b', text_upper, re.DOTALL):
            return True
        if re.search(rf'\b{keyword}\b\s+INTO\b', text_upper, re.DOTALL):
            return True
        if re.search(rf'\b{keyword}\b\s+TABLE\b', text_upper, re.DOTALL):
            return True
        if re.search(rf'\b{keyword}\b\s+\w+\s+SET\b', text_upper, re.DOTALL):
            return True
        # DELETE FROM pattern
        if re.search(rf'\b{keyword}\b\s+FROM\s+\w+', text_upper, re.DOTALL):
            return True

    return False


def contains_sql_patterns(text: str) -> bool:
    """
    Helper to detect SQL patterns in isolated text.

    Args:
        text: Text to check

    Returns:
        bool: True if SQL patterns detected
    """
    text_upper = text.upper()
    for keyword in SQL_KEYWORDS:
        if keyword in text_upper:
            return True
    return False


def extract_sql_queries(text: str) -> List[str]:
    """
    Extract SQL queries from text.

    Looks for:
    1. SQL in code blocks (```sql ... ``` or ``` ... ```)
    2. Inline SQL statements (keyword followed by SQL syntax)

    Args:
        text: Text to extract SQL from

    Returns:
        List[str]: List of SQL query strings found

    Examples:
        >>> extract_sql_queries("```sql\\nSELECT * FROM users\\n```")
        ['SELECT * FROM users']
        >>> extract_sql_queries("Use this: SELECT id FROM orders WHERE total > 100")
        ['SELECT id FROM orders WHERE total > 100']
    """
    queries = []

    # Extract from code blocks first (most reliable)
    code_block_pattern = r'```(?:sql)?\s*(.*?)```'
    for match in re.finditer(code_block_pattern, text, re.DOTALL | re.IGNORECASE):
        content = match.group(1).strip()
        if content and contains_sql_patterns(content):
            queries.append(content)

    # Extract inline SQL (heuristic-based)
    # Look for SQL keywords followed by text until period/newline
    for keyword in SQL_KEYWORDS:
        # Pattern: keyword followed by SQL-like content until statement end
        pattern = rf'\b({keyword}\b[^.;]*?(?:;|\.|\n|$))'
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            query = match.group(1).strip()
            # Verify it looks like SQL (has FROM, INTO, TABLE, SET, etc.)
            if re.search(r'\b(FROM|INTO|TABLE|SET|WHERE|JOIN)\b', query, re.IGNORECASE):
                # Clean up: remove trailing punctuation that's not part of SQL
                query = re.sub(r'[.!?]+$', '', query)
                if query not in queries:  # Avoid duplicates
                    queries.append(query)

    return queries
