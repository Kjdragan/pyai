#!/usr/bin/env python3
"""
Offline quick checks for the standalone module.
No network or external API calls required.
"""
from __future__ import annotations

import sys

from lf_nl_sql.sql_safety import ensure_safe_select
from lf_nl_sql.nl_to_sql import generate_sql
from lf_nl_sql.schema_context import SCHEMA_SUMMARY, FEW_SHOT_EXAMPLES


def check_sql_safety() -> None:
    good = """
        -- comment
        SELECT timestamp FROM records WHERE service_name = 'api';
    """
    assert ensure_safe_select(good).lower().startswith("select")

    good_with_cte = """
        WITH x AS (SELECT 1 AS a) SELECT * FROM x
    """
    assert ensure_safe_select(good_with_cte).lower().startswith("with")

    bad_multi = "SELECT 1; SELECT 2"
    try:
        ensure_safe_select(bad_multi)
        raise AssertionError("Multiple statements should fail")
    except ValueError:
        pass

    bad_ddl = "DROP TABLE records"
    try:
        ensure_safe_select(bad_ddl)
        raise AssertionError("DDL should fail")
    except ValueError:
        pass


def check_nl_to_sql_fallback() -> None:
    sql = generate_sql("show last rows", provider="none")
    assert sql.strip().lower().startswith("select"), "Fallback should return SELECT"
    assert "limit" in sql.lower(), "Fallback should include LIMIT"


def check_schema_context() -> None:
    assert "Table records" in SCHEMA_SUMMARY
    assert FEW_SHOT_EXAMPLES and isinstance(FEW_SHOT_EXAMPLES, list)


def main() -> int:
    check_sql_safety()
    check_nl_to_sql_fallback()
    check_schema_context()
    print("Quick checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
