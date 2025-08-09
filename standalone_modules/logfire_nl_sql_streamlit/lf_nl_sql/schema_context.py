SCHEMA_SUMMARY = """
Table records:
- timestamp (timestamp)
- service_name (string)
- span_name (string)
- trace_id (string)
- span_id (string)
- attributes (json)
- tags (array<string>)

Table metrics (optional): typical columns include timestamp, name, value, attributes(json)

JSON helpers: attributes->'key'->>'subkey', array_has(tags, 'error')
""".strip()


FEW_SHOT_EXAMPLES = [
    """
-- Top services by error rate (example)
SELECT service_name, COUNT(*) FILTER (WHERE array_has(tags, 'error'))::float / COUNT(*) AS error_rate
FROM records
WHERE timestamp >= now() - interval '24 hours'
GROUP BY service_name
ORDER BY error_rate DESC
LIMIT 20;
""".strip(),
    """
-- Slowest spans (example)
SELECT span_name, approx_percentile(duration_ms, 0.95) AS p95_ms
FROM records
WHERE timestamp >= now() - interval '24 hours'
GROUP BY span_name
ORDER BY p95_ms DESC
LIMIT 20;
""".strip(),
]
