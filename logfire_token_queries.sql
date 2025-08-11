-- Logfire Token Usage Analysis Queries
-- Run these queries in Logfire dashboard or via API

-- 1. LATEST RUN SUMMARY
-- Gets the most recent orchestrator run with basic stats
WITH latest_run AS (
    SELECT trace_id, start_timestamp, duration
    FROM records 
    WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
    AND start_timestamp >= now() - interval '30 minutes'
    ORDER BY start_timestamp DESC
    LIMIT 1
)
SELECT 
    lr.trace_id,
    lr.start_timestamp as run_start,
    lr.duration as total_run_duration,
    COUNT(DISTINCT CASE WHEN r.attributes ? 'token_usage' THEN r.span_id END) as llm_calls,
    SUM(CASE WHEN r.attributes ? 'token_usage' THEN (r.attributes->>'token_usage'->>'total_tokens')::int ELSE 0 END) as total_tokens,
    COUNT(DISTINCT r.span_id) as total_spans
FROM latest_run lr
LEFT JOIN records r ON r.trace_id = lr.trace_id
GROUP BY lr.trace_id, lr.start_timestamp, lr.duration;

-- 2. DETAILED TOKEN BREAKDOWN BY SUBPROCESS
-- Shows token usage grouped by agent/subprocess and model
WITH latest_run AS (
    -- Find the most recent orchestrator run
    SELECT trace_id, start_timestamp
    FROM records 
    WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
    AND start_timestamp >= now() - interval '30 minutes'
    ORDER BY start_timestamp DESC
    LIMIT 1
),
token_records AS (
    -- Get all token usage from the latest run
    SELECT 
        r.trace_id,
        r.span_id,
        r.parent_span_id,
        r.span_name,
        r.message,
        r.start_timestamp,
        r.duration,
        r.attributes,
        r.service_name,
        -- Extract token usage data
        (r.attributes->>'token_usage'->>'completion_tokens')::int as completion_tokens,
        (r.attributes->>'token_usage'->>'prompt_tokens')::int as prompt_tokens,
        (r.attributes->>'token_usage'->>'total_tokens')::int as total_tokens,
        r.attributes->>'model' as model,
        r.attributes->>'request_type' as request_type,
        -- Extract agent/subprocess info
        COALESCE(
            r.attributes->>'agent_name',
            r.attributes->>'component',
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
        ) as subprocess
    FROM records r
    JOIN latest_run lr ON r.trace_id = lr.trace_id
    WHERE r.attributes ? 'token_usage'
    AND (r.attributes->>'token_usage'->>'total_tokens')::int > 0
)
SELECT 
    subprocess,
    model,
    request_type,
    COUNT(*) as request_count,
    SUM(completion_tokens) as total_completion_tokens,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(total_tokens) as total_tokens,
    AVG(total_tokens) as avg_tokens_per_request,
    MIN(start_timestamp) as first_request,
    MAX(start_timestamp) as last_request,
    SUM(duration) as total_duration_seconds
FROM token_records
GROUP BY subprocess, model, request_type
ORDER BY total_tokens DESC;

-- 3. SUBPROCESS SUMMARY (ROLLUP)
-- High-level view of token usage by subprocess
WITH latest_run AS (
    SELECT trace_id, start_timestamp
    FROM records 
    WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
    AND start_timestamp >= now() - interval '30 minutes'
    ORDER BY start_timestamp DESC
    LIMIT 1
),
token_records AS (
    SELECT 
        r.trace_id,
        (r.attributes->>'token_usage'->>'total_tokens')::int as total_tokens,
        COALESCE(
            r.attributes->>'agent_name',
            r.attributes->>'component',
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
        ) as subprocess
    FROM records r
    JOIN latest_run lr ON r.trace_id = lr.trace_id
    WHERE r.attributes ? 'token_usage'
    AND (r.attributes->>'token_usage'->>'total_tokens')::int > 0
)
SELECT 
    subprocess,
    COUNT(*) as request_count,
    SUM(total_tokens) as total_tokens,
    AVG(total_tokens) as avg_tokens_per_request,
    ROUND(100.0 * SUM(total_tokens) / SUM(SUM(total_tokens)) OVER (), 2) as percentage_of_total
FROM token_records
GROUP BY subprocess
ORDER BY total_tokens DESC;

-- 4. COST ESTIMATION (GPT-4 PRICING)
-- Estimates costs based on token usage and model types
WITH latest_run AS (
    SELECT trace_id, start_timestamp
    FROM records 
    WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
    AND start_timestamp >= now() - interval '30 minutes'
    ORDER BY start_timestamp DESC
    LIMIT 1
),
token_records AS (
    SELECT 
        r.attributes->>'model' as model,
        (r.attributes->>'token_usage'->>'completion_tokens')::int as completion_tokens,
        (r.attributes->>'token_usage'->>'prompt_tokens')::int as prompt_tokens,
        (r.attributes->>'token_usage'->>'total_tokens')::int as total_tokens
    FROM records r
    JOIN latest_run lr ON r.trace_id = lr.trace_id
    WHERE r.attributes ? 'token_usage'
    AND (r.attributes->>'token_usage'->>'total_tokens')::int > 0
)
SELECT 
    model,
    COUNT(*) as calls,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(completion_tokens) as total_completion_tokens,
    SUM(total_tokens) as total_tokens,
    -- Cost estimation (adjust rates based on actual model pricing)
    CASE 
        WHEN model LIKE '%gpt-4%' THEN 
            ROUND((SUM(prompt_tokens) / 1000.0 * 0.03) + (SUM(completion_tokens) / 1000.0 * 0.06), 4)
        WHEN model LIKE '%gpt-3.5%' THEN 
            ROUND((SUM(prompt_tokens) / 1000.0 * 0.001) + (SUM(completion_tokens) / 1000.0 * 0.002), 4)
        WHEN model LIKE '%gpt-5%' THEN 
            ROUND((SUM(prompt_tokens) / 1000.0 * 0.05) + (SUM(completion_tokens) / 1000.0 * 0.10), 4)
        ELSE 0
    END as estimated_cost_usd
FROM token_records
GROUP BY model
ORDER BY total_tokens DESC;

-- 5. TIMELINE ANALYSIS
-- Shows token usage over time during the run
WITH latest_run AS (
    SELECT trace_id, start_timestamp
    FROM records 
    WHERE service_name = 'pyai'
    AND span_name LIKE '%orchestrator%'
    AND start_timestamp >= now() - interval '30 minutes'
    ORDER BY start_timestamp DESC
    LIMIT 1
),
token_records AS (
    SELECT 
        r.start_timestamp,
        (r.attributes->>'token_usage'->>'total_tokens')::int as total_tokens,
        r.span_name,
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
        ) as subprocess
    FROM records r
    JOIN latest_run lr ON r.trace_id = lr.trace_id
    WHERE r.attributes ? 'token_usage'
    AND (r.attributes->>'token_usage'->>'total_tokens')::int > 0
)
SELECT 
    start_timestamp,
    subprocess,
    span_name,
    total_tokens,
    SUM(total_tokens) OVER (ORDER BY start_timestamp) as cumulative_tokens
FROM token_records
ORDER BY start_timestamp;

-- Usage Instructions:
-- 1. Run query #1 first to confirm you have data from recent runs
-- 2. Run query #2 for detailed breakdown by subprocess and model
-- 3. Run query #3 for high-level subprocess summary
-- 4. Run query #4 for cost estimation
-- 5. Run query #5 for timeline analysis
--
-- Adjust the 'interval' in each query to look further back if needed
-- (e.g., change '30 minutes' to '60 minutes' or '2 hours')