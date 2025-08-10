from __future__ import annotations

import os
from typing import Optional
import logging

from .schema_context import SCHEMA_SUMMARY, FEW_SHOT_EXAMPLES


OPENAI_AVAILABLE = True
try:  # optional
    from openai import OpenAI  # type: ignore
except Exception:
    OPENAI_AVAILABLE = False


def _build_prompt(user_prompt: str, mode: str = "new", existing_sql: Optional[str] = None) -> str:
    header = (
        "You are a SQL assistant for querying Logfire data. "
        "Only produce a valid SELECT SQL query for Apache DataFusion/Postgres-like dialect. "
        "Constraints: use only table records (and metrics if asked); prefer JSON extraction operators; "
        "there is NO 'timestamp' column—use start_timestamp (span start) and end_timestamp (span end). "
        "The app supplies time filters, so you may omit explicit time predicates unless necessary. "
        "For latency percentiles, DO NOT use approx_percentile; use ordered-set approx_percentile_cont(p) WITHIN GROUP (ORDER BY expr). "
        "Compute duration expr as EXTRACT(EPOCH FROM (end_timestamp - start_timestamp)) * 1000 (ms). "
        "For error rate, consider any of: array_has(tags, 'error'), CAST(attributes->'http'->>'status_code' AS INT) >= 500, "
        "or (attributes->'otel'->>'status_code') = 'ERROR'. Always include a LIMIT. Never output DDL/DML."
    )
    examples = "\n\n".join(FEW_SHOT_EXAMPLES)
    if mode == "modify" and existing_sql:
        return (
            f"{header}\n\nSchema:\n{SCHEMA_SUMMARY}\n\nExamples:\n{examples}\n\n"
            f"Existing SQL:\n{existing_sql}\n\nUser request: {user_prompt}\n"
            "Return only the modified SQL (no prose)."
        )
    return (
        f"{header}\n\nSchema:\n{SCHEMA_SUMMARY}\n\nExamples:\n{examples}\n\n"
        f"User request: {user_prompt}\nReturn only the SQL (no prose)."
    )


def generate_sql(
    user_prompt: str,
    *,
    provider: str = "none",
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    mode: str = "new",
    existing_sql: Optional[str] = None,
) -> str:
    log = logging.getLogger(__name__)
    prompt = _build_prompt(user_prompt, mode=mode, existing_sql=existing_sql)

    if provider == "openai" and OPENAI_AVAILABLE:
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        log.info("OpenAI generate_sql | model=%s mode=%s prompt_len=%s", model, mode, len(user_prompt or ""))
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Return only SQL in a single code block."},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception:
            log.exception("OpenAI chat.completions.create failed")
            raise
        text = resp.choices[0].message.content or ""
        # strip code fences if present
        if text.strip().startswith("```"):
            text = text.strip().strip("`")
            if "\n" in text:
                text = "\n".join(text.splitlines()[1:])
        sql_out = text.strip()
        log.debug("OpenAI generated SQL (truncated): %s", sql_out.replace("\n", " ")[:300])
        return sql_out

    # Fallback: produce a safe baseline for manual editing
    return (
        "SELECT start_timestamp, end_timestamp, service_name, span_name, trace_id, span_id\n"
        "FROM records\n"
        "ORDER BY start_timestamp DESC\n"
        "LIMIT 100;"
    )
