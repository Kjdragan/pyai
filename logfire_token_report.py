#!/usr/bin/env python3
"""
Logfire Token Usage Report Generator
Analyzes token usage from the latest PyAI research run, broken down by subprocess.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from config import config
except ImportError:
    # Fallback if config not available
    class Config:
        LOGFIRE_TOKEN = None
        LOGFIRE_PROJECT_NAME = "pyai"
    config = Config()

class LogfireTokenAnalyzer:
    """Analyzes token usage from Logfire for PyAI research runs."""
    
    def __init__(self):
        self.service_name = "pyai"  # From our configuration
        
    def get_latest_run_query(self, minutes_back: int = 30) -> str:
        """Get SQL query to find the latest research run and its token usage."""
        return f"""
        WITH latest_run AS (
            -- Find the most recent orchestrator run
            SELECT trace_id, start_timestamp
            FROM records 
            WHERE service_name = '{self.service_name}'
            AND span_name LIKE '%orchestrator%'
            AND start_timestamp >= now() - interval '{minutes_back} minutes'
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
        """
    
    def get_run_summary_query(self, minutes_back: int = 30) -> str:
        """Get overall summary of the latest run."""
        return f"""
        WITH latest_run AS (
            SELECT trace_id, start_timestamp, duration
            FROM records 
            WHERE service_name = '{self.service_name}'
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
            SUM(CASE WHEN r.attributes ? 'token_usage' THEN (r.attributes->>'token_usage'->>'total_tokens')::int ELSE 0 END) as total_tokens,
            COUNT(DISTINCT r.span_id) as total_spans
        FROM latest_run lr
        LEFT JOIN records r ON r.trace_id = lr.trace_id
        GROUP BY lr.trace_id, lr.start_timestamp, lr.duration;
        """
        
    def format_report(self, token_data: List[Dict], summary_data: List[Dict]) -> str:
        """Format the token usage data into a readable report."""
        if not summary_data:
            return "❌ No recent runs found. Check if PyAI has been run recently with Logfire enabled."
            
        summary = summary_data[0]
        trace_id = summary['trace_id']
        run_start = summary['run_start']
        total_duration = summary['total_run_duration'] or 0
        total_tokens = summary['total_tokens'] or 0
        llm_calls = summary['llm_calls'] or 0
        
        report = []
        report.append("=" * 80)
        report.append("🔥 LOGFIRE TOKEN USAGE REPORT - LATEST RUN")
        report.append("=" * 80)
        report.append(f"🆔 Trace ID: {trace_id}")
        report.append(f"⏰ Run Start: {run_start}")
        report.append(f"⏱️  Total Duration: {total_duration:.2f}s")
        report.append(f"🤖 Total LLM Calls: {llm_calls}")
        report.append(f"🎯 Total Tokens Used: {total_tokens:,}")
        if total_duration > 0:
            report.append(f"📊 Tokens per Second: {total_tokens / total_duration:.1f}")
        report.append("")
        
        if not token_data:
            report.append("⚠️  No detailed token usage data found for this run.")
            report.append("This might indicate:")
            report.append("- Logfire instrumentation is not capturing token usage")  
            report.append("- The run didn't make any LLM calls")
            report.append("- Token usage attributes are stored differently")
            return "\\n".join(report)
        
        # Group by subprocess for better organization
        subprocess_totals = {}
        for row in token_data:
            subprocess = row['subprocess']
            if subprocess not in subprocess_totals:
                subprocess_totals[subprocess] = {
                    'total_tokens': 0,
                    'total_requests': 0,
                    'models': set(),
                    'details': []
                }
            subprocess_totals[subprocess]['total_tokens'] += row['total_tokens'] or 0
            subprocess_totals[subprocess]['total_requests'] += row['request_count'] or 0
            subprocess_totals[subprocess]['models'].add(row['model'] or 'unknown')
            subprocess_totals[subprocess]['details'].append(row)
        
        # Sort subprocesses by token usage
        sorted_subprocesses = sorted(subprocess_totals.items(), 
                                   key=lambda x: x[1]['total_tokens'], 
                                   reverse=True)
        
        report.append("📋 TOKEN USAGE BY SUBPROCESS")
        report.append("-" * 50)
        
        for subprocess, data in sorted_subprocesses:
            pct = (data['total_tokens'] / max(total_tokens, 1)) * 100
            models_str = ", ".join(sorted(data['models']))
            
            report.append(f"")
            report.append(f"🔧 {subprocess.upper()}")
            report.append(f"   📊 Total Tokens: {data['total_tokens']:,} ({pct:.1f}%)")
            report.append(f"   📞 Total Requests: {data['total_requests']}")
            report.append(f"   🤖 Models Used: {models_str}")
            
            # Show detailed breakdown for this subprocess
            for detail in sorted(data['details'], key=lambda x: x['total_tokens'] or 0, reverse=True):
                model = detail['model'] or 'unknown'
                req_type = detail['request_type'] or 'unknown'
                tokens = detail['total_tokens'] or 0
                requests = detail['request_count'] or 0
                avg_tokens = detail['avg_tokens_per_request'] or 0
                
                report.append(f"     • {model} ({req_type}): {tokens:,} tokens ({requests} calls, {avg_tokens:.0f} avg)")
        
        # Cost estimation (rough GPT-4 pricing)
        report.append("")
        report.append("💰 ESTIMATED COSTS (GPT-4 PRICING)")
        report.append("-" * 30)
        
        # Rough cost estimates per 1K tokens (adjust based on actual models used)
        cost_per_1k_input = 0.03   # GPT-4 input
        cost_per_1k_output = 0.06  # GPT-4 output
        
        total_cost = 0
        for row in token_data:
            if row['model'] and 'gpt-4' in row['model'].lower():
                prompt_cost = (row['total_prompt_tokens'] or 0) / 1000 * cost_per_1k_input
                completion_cost = (row['total_completion_tokens'] or 0) / 1000 * cost_per_1k_output
                total_cost += prompt_cost + completion_cost
        
        if total_cost > 0:
            report.append(f"💵 Estimated Cost: ${total_cost:.3f}")
        else:
            report.append("💵 Cost estimation requires model-specific pricing")
        
        report.append("")
        report.append("=" * 80)
        
        return "\\n".join(report)

# Standalone execution functions (can be used without MCP tools)
async def run_token_report(minutes_back: int = 30) -> str:
    """
    Generate token usage report for the latest run.
    Can be called directly or used as a standalone script.
    """
    analyzer = LogfireTokenAnalyzer()
    
    # Note: This would use the MCP tools if available
    # For now, return the SQL queries that should be run
    token_query = analyzer.get_latest_run_query(minutes_back)
    summary_query = analyzer.get_run_summary_query(minutes_back)
    
    return f"""
🔥 LOGFIRE TOKEN ANALYSIS QUERIES
{'='*50}

To get your token usage report, run these queries in Logfire:

1️⃣ RUN SUMMARY:
{summary_query}

2️⃣ DETAILED BREAKDOWN:  
{token_query}

📝 Usage:
- Adjust minutes_back parameter (currently {minutes_back}) to look further back
- Results will show token usage grouped by subprocess and model
- Includes cost estimates and performance metrics

🔧 Integration:
This script can be integrated with MCP tools for automatic execution.
"""

def main():
    """Main entry point for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Logfire token usage report")
    parser.add_argument("--minutes", "-m", type=int, default=30, 
                       help="Look back this many minutes for the latest run (default: 30)")
    parser.add_argument("--output", "-o", type=str, 
                       help="Output file path (default: print to console)")
    
    args = parser.parse_args()
    
    # Generate the report
    result = asyncio.run(run_token_report(args.minutes))
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(result)
        print(f"✅ Report saved to {args.output}")
    else:
        print(result)

if __name__ == "__main__":
    main()