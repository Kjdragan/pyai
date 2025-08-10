SCHEMA_SUMMARY = """
Table records:
- start_timestamp (timestamp)
- end_timestamp (timestamp)
- service_name (string)
- span_name (string)
- trace_id (string)
- span_id (string)
- attributes (json)
- tags (array<string>)

Notes:
- There is NO column named `timestamp`. Use `start_timestamp` (span start) and `end_timestamp` (span end).
- The app supplies time filters separately; you can omit explicit time predicates unless needed for the query itself.

Table metrics (optional): typical columns include start_timestamp, name, value, attributes(json)

JSON helpers: attributes->'key'->>'subkey', array_has(tags, 'error')
""".strip()


FEW_SHOT_EXAMPLES = [
    """
-- Top services by error rate (example)
SELECT
  service_name,
  COUNT(*) FILTER (
    WHERE array_has(tags, 'error')
       OR CAST(attributes->'http'->>'status_code' AS INT) >= 500
       OR (attributes->'otel'->>'status_code') = 'ERROR'
  )::float / NULLIF(COUNT(*), 0) AS error_rate,
  COUNT(*) AS total_count,
  COUNT(*) FILTER (
    WHERE array_has(tags, 'error')
       OR CAST(attributes->'http'->>'status_code' AS INT) >= 500
       OR (attributes->'otel'->>'status_code') = 'ERROR'
  ) AS error_count
FROM records
WHERE start_timestamp >= now() - interval '24 hours'
GROUP BY service_name
ORDER BY error_rate DESC
LIMIT 20;
""".strip(),
    """
-- Slowest spans (example)
SELECT
  span_name,
  approx_percentile_cont(0.95) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (end_timestamp - start_timestamp)) * 1000
  ) AS p95_ms
FROM records
WHERE start_timestamp >= now() - interval '24 hours'
GROUP BY span_name
ORDER BY p95_ms DESC
LIMIT 20;
""".strip(),
]
