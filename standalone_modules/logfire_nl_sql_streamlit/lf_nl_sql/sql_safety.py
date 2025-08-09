from __future__ import annotations

import re

_SINGLE_LINE_COMMENT = re.compile(r"--.*?(\n|$)")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RISKY = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|execute|merge)\b", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT.sub(" ", sql)
    sql = _SINGLE_LINE_COMMENT.sub(" ", sql)
    return sql


def _strip_wrapping(sql: str) -> str:
    # Trim whitespace and redundant trailing semicolons
    s = sql.strip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def ensure_safe_select(sql: str) -> str:
    """Ensure the SQL is a single, read-only SELECT statement.

    - Removes comments and trailing semicolons.
    - Validates it starts with SELECT.
    - Rejects queries containing risky keywords.
    - Rejects multiple statements separated by semicolons.
    Returns the sanitized SQL string, or raises ValueError.
    """
    if not sql or not sql.strip():
        raise ValueError("SQL is empty")

    cleaned = _strip_wrapping(_strip_comments(sql))

    # No internal semicolons allowed after cleanup
    if ";" in cleaned:
        raise ValueError("Multiple statements are not allowed")

    # Must start with SELECT (allow leading parenthesis/CTEs are allowed only if start with 'with' or 'select')
    start = cleaned.lstrip().lower()
    if not (start.startswith("select") or start.startswith("with ")):
        raise ValueError("Only SELECT queries are allowed")

    # Disallow risky keywords anywhere
    if _RISKY.search(cleaned):
        raise ValueError("Disallowed SQL keyword detected")

    return cleaned
