#!/usr/bin/env python3
"""
Quick Token Usage Report - Works with MCP Logfire tools
Run this after your research to get token usage breakdown.
"""

import asyncio
import json
from datetime import datetime

# MCP Functions (these would be available in Claude Code environment)
async def get_token_summary(minutes_back: int = 30):
    """Get token usage summary for the latest run."""
    
    # Summary query
    summary_query = f"""
    WITH latest_run AS (
        SELECT trace_id, start_timestamp, duration
        FROM records 
        WHERE service_name = 'pyai'
        AND span_name LIKE '%orchestrator%'
        AND start_timestamp >= now() - interval '{minutes_back} minutes'
        ORDER BY start_timestamp DESC
        LIMIT 1
    )
    SELECT 
        lr.trace_id,
        lr.start_timestamp as run_start,
        lr.duration as total_run_duration,
        COUNT(DISTINCT CASE WHEN r.attributes ? 'token_usage' THEN r.span_id END) as llm_calls,
        SUM(CASE WHEN r.attributes ? 'token_usage' THEN (r.attributes->>'token_usage'->>'total_tokens')::int ELSE 0 END) as total_tokens
    FROM latest_run lr
    LEFT JOIN records r ON r.trace_id = lr.trace_id
    GROUP BY lr.trace_id, lr.start_timestamp, lr.duration;
    """
    
    # Detailed breakdown query  
    detailed_query = f"""
    WITH latest_run AS (
        SELECT trace_id
        FROM records 
        WHERE service_name = 'pyai'
        AND span_name LIKE '%orchestrator%'
        AND start_timestamp >= now() - interval '{minutes_back} minutes'
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
        ) as subprocess,
        r.attributes->>'model' as model,
        COUNT(*) as request_count,
        SUM((r.attributes->>'token_usage'->>'total_tokens')::int) as total_tokens
    FROM records r
    JOIN latest_run lr ON r.trace_id = lr.trace_id
    WHERE r.attributes ? 'token_usage'
    AND (r.attributes->>'token_usage'->>'total_tokens')::int > 0
    GROUP BY subprocess, model
    ORDER BY total_tokens DESC;
    """
    
    # In a real implementation, these would use the MCP tools:
    # summary_result = await mcp__logfire__arbitrary_query(summary_query, minutes_back)  
    # detailed_result = await mcp__logfire__arbitrary_query(detailed_query, minutes_back)
    
    # For now, return the queries to run manually
    return {
        "summary_query": summary_query,
        "detailed_query": detailed_query,
        "instructions": f"""
🔥 LOGFIRE TOKEN USAGE REPORT
{'='*50}

To get your token usage for the latest run:

1️⃣ SUMMARY QUERY:
Copy and run this query in Logfire:

{summary_query}

2️⃣ DETAILED BREAKDOWN:
Copy and run this query in Logfire:

{detailed_query}

📋 This will show you:
- Total tokens used in the latest run
- Breakdown by subprocess (orchestrator, serper, report writer, etc.)  
- Model usage (gpt-5-mini, gpt-5-nano, etc.)
- Request counts per component

⏰ Looking back {minutes_back} minutes from now.
Adjust the interval if your run was longer ago.
        """
    }

def format_results(summary_data, detailed_data):
    """Format query results into a readable report."""
    
    if not summary_data:
        return "❌ No recent runs found"
        
    summary = summary_data[0]
    
    report = []
    report.append("🔥 TOKEN USAGE REPORT")
    report.append("=" * 40)
    report.append(f"🆔 Trace: {summary['trace_id'][:16]}...")
    report.append(f"⏰ Start: {summary['run_start']}")
    report.append(f"⏱️  Duration: {summary['total_run_duration']:.1f}s") 
    report.append(f"🤖 LLM Calls: {summary['llm_calls']}")
    report.append(f"🎯 Total Tokens: {summary['total_tokens']:,}")
    report.append("")
    
    if detailed_data:
        report.append("📋 BY SUBPROCESS:")
        report.append("-" * 30)
        
        total_tokens = sum(row['total_tokens'] for row in detailed_data)
        
        for row in detailed_data:
            subprocess = row['subprocess']
            model = row['model'] or 'unknown'
            tokens = row['total_tokens']
            requests = row['request_count']
            pct = (tokens / max(total_tokens, 1)) * 100
            
            report.append(f"{subprocess:15} | {model:20} | {tokens:>8,} tokens ({pct:4.1f}%) | {requests:2} calls")
    
    return "\\n".join(report)

# Quick usage functions
async def quick_report(minutes_back: int = 30):
    """Get a quick token report for the latest run."""
    result = await get_token_summary(minutes_back)
    print(result["instructions"])

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Quick Logfire token usage report")
    parser.add_argument("--minutes", "-m", type=int, default=30,
                       help="Minutes to look back (default: 30)")
    
    args = parser.parse_args()
    
    asyncio.run(quick_report(args.minutes))