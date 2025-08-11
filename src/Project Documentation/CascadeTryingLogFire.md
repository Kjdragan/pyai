# Cascade Attempt: Logfire Token Usage Queries

Date: 2025-08-10 13:47-05:00
Location: `src/Project Documentation/CascadeTryingLogFire.md`

## Goal
Get token usage from the latest PyAI research run in Logfire, with a summary and (if possible) a breakdown by subprocess and model.

## What I worked on
- Used MCP Logfire tools to validate SQL dialect and run queries from the editor.
- Converted original Postgres-like queries to Logfire/DataFusion-compatible SQL.
- Investigated UI parsing errors and the “Include existing SQL code” behavior in Logfire’s editor.

## Environment/Context
- Reference doc: `src/Project Documentation/Logfire_MCP_Instructions.md` (MCP tool names and .env keys).
- Logfire SQL engine: Apache DataFusion with Postgres-like syntax, JSON via `->` and `->>`.

## Lessons learned (dialect + UI)
- __No `?` has-key operator__: Replace `attributes ? 'token_usage'` with `attributes->'token_usage' IS NOT NULL`.
- __Avoid `::int` casts__: Use `CAST(... AS BIGINT)` (or INT) instead of Postgres `::`.
- __Remove trailing semicolons__ in the Logfire UI; they can trigger parse errors.
- __Group by ordinals__ is safe: `GROUP BY 1,2,3`.
- __Editor gotcha__: If “Include existing SQL code” is ON, the UI prepends `SELECT * FROM records WHERE (<your text>)` and treats your input as a WHERE subquery that must return one column. Pasting a full SELECT then yields “Too many columns”. Turn it OFF, or paste only a single-column filter.
- __`json_extract` not available__: The engine errored on `json_extract/json_extract_scalar`; use `->/->>` instead.

## Working queries (paste as full queries; no semicolons)

### A) Latest run summary
```sql
WITH latest_run AS (
  SELECT trace_id, start_timestamp, duration
  FROM records
  WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
  ORDER BY start_timestamp DESC
  LIMIT 1
)
SELECT
  lr.trace_id,
  lr.start_timestamp AS run_start,
  lr.duration AS total_run_duration,
  SUM(CASE WHEN r.attributes->'token_usage' IS NOT NULL THEN 1 ELSE 0 END) AS llm_calls,
  SUM(CASE WHEN r.attributes->'token_usage' IS NOT NULL
           THEN CAST((r.attributes->'token_usage'->>'total_tokens') AS BIGINT)
           ELSE 0 END) AS total_tokens
FROM latest_run lr
LEFT JOIN records r ON r.trace_id = lr.trace_id
GROUP BY 1, 2, 3
```

### B) Breakdown by subprocess and model
```sql
WITH latest_run AS (
  SELECT trace_id
  FROM records
  WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
  ORDER BY start_timestamp DESC
  LIMIT 1
)
SELECT
  COALESCE(
    r.attributes->>'agent_name',
    CASE
      WHEN r.span_name LIKE '%orchestrator%' THEN 'orchestrator'
      WHEN r.span_name LIKE '%serper%' THEN 'serper_research'
      WHEN r.span_name LIKE '%tavily%' THEN 'tavily_research'
      WHEN r.span_name LIKE '%youtube%' THEN 'youtube'
      WHEN r.span_name LIKE '%weather%' THEN 'weather'
      WHEN r.span_name LIKE '%report%' THEN 'report_writer'
      WHEN r.span_name LIKE '%content%' THEN 'content_cleaning'
      ELSE 'unknown'
    END
  ) AS subprocess,
  COALESCE(r.attributes->>'model', 'unknown_model') AS model,
  COUNT(*) AS request_count,
  SUM(CAST((r.attributes->'token_usage'->>'total_tokens') AS BIGINT)) AS total_tokens
FROM records r
JOIN latest_run lr ON r.trace_id = lr.trace_id
WHERE r.attributes->'token_usage' IS NOT NULL
  AND CAST((r.attributes->'token_usage'->>'total_tokens') AS BIGINT) > 0
GROUP BY 1, 2
ORDER BY total_tokens DESC
```

## If you must keep “Include existing SQL code” ON
- Paste only a single-column WHERE filter to pick the latest run:
```sql
trace_id IN (
  SELECT trace_id
  FROM records
  WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
  ORDER BY start_timestamp DESC
  LIMIT 1
)
```
- Then run summary/breakdown queries in a clean editor tab without the wrapper, or copy the `trace_id` and use the parameterized form below.

## Parameterized queries by trace_id
- Summary:
```sql
SELECT
  MIN(start_timestamp) AS run_start,
  MAX(duration) AS total_run_duration,
  SUM(CASE WHEN attributes->'token_usage' IS NOT NULL THEN 1 ELSE 0 END) AS llm_calls,
  SUM(CASE WHEN attributes->'token_usage' IS NOT NULL
           THEN CAST((attributes->'token_usage'->>'total_tokens') AS BIGINT)
           ELSE 0 END) AS total_tokens
FROM records
WHERE trace_id = 'PASTE_TRACE_ID_HERE'
```
- Breakdown:
```sql
SELECT
  COALESCE(
    attributes->>'agent_name',
    CASE
      WHEN span_name LIKE '%orchestrator%' THEN 'orchestrator'
      WHEN span_name LIKE '%serper%' THEN 'serper_research'
      WHEN span_name LIKE '%tavily%' THEN 'tavily_research'
      WHEN span_name LIKE '%youtube%' THEN 'youtube'
      WHEN span_name LIKE '%weather%' THEN 'weather'
      WHEN span_name LIKE '%report%' THEN 'report_writer'
      WHEN span_name LIKE '%content%' THEN 'content_cleaning'
      ELSE 'unknown'
    END
  ) AS subprocess,
  COALESCE(attributes->>'model', 'unknown_model') AS model,
  COUNT(*) AS request_count,
  SUM(CAST((attributes->'token_usage'->>'total_tokens') AS BIGINT)) AS total_tokens
FROM records
WHERE trace_id = 'PASTE_TRACE_ID_HERE'
  AND attributes->'token_usage' IS NOT NULL
  AND CAST((attributes->'token_usage'->>'total_tokens') AS BIGINT) > 0
GROUP BY 1, 2
ORDER BY total_tokens DESC
```

## Troubleshooting checklist
- Turn off “Include existing SQL code” for full SELECTs.
- Remove trailing semicolons.
- Use CAST(... AS BIGINT) instead of `::int`.
- Widen UI time filter if no rows appear.
- Scope by env if needed: add `AND deployment_environment = 'production'`.

## Next steps
- Create a small helper in our repo (CLI or MCP action) to:
  1) Fetch latest orchestrator `trace_id`.
  2) Run summary + breakdown queries.
  3) Print totals and a simple table.
- Optionally use Logfire MCP `logfire_link` once we have the `trace_id` to store a clickable trace link in reports.

Status: Documented working SQL and UI steps to get token usage summary and breakdown reliably in Logfire.
