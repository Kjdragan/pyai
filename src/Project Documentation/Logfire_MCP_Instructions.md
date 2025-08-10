# Logfire MCP Instructions

## Overview
This document explains how to use the Logfire MCP (Model Context Protocol) integration to analyze token usage and performance metrics from PyAI research runs.

## Prerequisites

### 1. Logfire Configuration
Ensure your `.env` file contains the correct Logfire settings:
```bash
LOGFIRE_TOKEN=pylf_v1_us_PcVjdq2q2H7ySfr4qkcTqxWgmKQJty1m7svm3dZqm3RF
LOGFIRE_PROJECT_NAME=pyai
LOGFIRE_ORG_NAME=Kjdragan
LOGFIRE_READ_TOKEN=pylf_v1_us_W6rwRjKyyYPy6CBYSR1LKmCJT4JcBs5Q2dwjPcb6hXTP
```

### 2. MCP Tool Access
Verify MCP tools are available in your Claude Code environment:
- `mcp__logfire__arbitrary_query`
- `mcp__logfire__get_logfire_records_schema`
- `mcp__logfire__sql_reference`

## Token Usage Analysis Tools

### 1. Quick Token Report (Recommended)
**File**: `quick_token_report.py`

**Usage**:
```bash
# Get token usage for runs in the last 30 minutes
python quick_token_report.py

# Look back further
python quick_token_report.py --minutes 60
```

**What it shows**:
- Total tokens used in latest run
- Breakdown by subprocess (orchestrator, serper, report writer, etc.)
- Model usage (gpt-5-mini, gpt-5-nano, etc.)
- Request counts per component

### 2. Comprehensive Analysis
**File**: `logfire_token_report.py`

**Usage**:
```bash
# Full detailed report
python logfire_token_report.py --minutes 30

# Save to file
python logfire_token_report.py --minutes 30 --output token_report.txt
```

**Features**:
- Detailed subprocess breakdown
- Cost estimation with model-specific pricing
- Performance metrics and timing analysis
- Subprocess ranking by token consumption

### 3. Manual SQL Queries
**File**: `logfire_token_queries.sql`

Contains 5 ready-to-use queries:
1. **Latest Run Summary** - Basic stats and trace ID
2. **Detailed Breakdown** - By subprocess, model, and request type  
3. **Subprocess Summary** - High-level rollup with percentages
4. **Cost Estimation** - GPT-4/GPT-5 pricing calculations
5. **Timeline Analysis** - Token usage over time

## Using MCP Tools Directly

### Check Recent Runs
```python
# In Claude Code, use MCP tool to find recent runs
mcp__logfire__arbitrary_query(
    query="SELECT trace_id, start_timestamp, span_name FROM records WHERE service_name = 'pyai' AND start_timestamp >= now() - interval '30 minutes' ORDER BY start_timestamp DESC LIMIT 5",
    age=30
)
```

### Get Token Usage Summary
```python
# Get token breakdown for latest run
mcp__logfire__arbitrary_query(
    query="<paste query from logfire_token_queries.sql>",
    age=30
)
```

## Understanding the Output

### Subprocess Categories
- **`orchestrator`** - Query expansion and agent coordination
- **`serper_research`** - Google Search via Serper API + scraping
- **`tavily_research`** - Tavily API research (if enabled)
- **`report_writer`** - Final report generation and synthesis
- **`content_cleaning`** - LLM-based content cleaning and processing
- **`youtube`** - YouTube transcript analysis
- **`weather`** - Weather data processing

### Key Metrics
- **Total Tokens** - Complete token consumption
- **Request Count** - Number of LLM API calls
- **Average per Request** - Efficiency metric
- **Percentage of Total** - Relative usage by component
- **Estimated Cost** - USD cost based on model pricing

## Troubleshooting

### "Invalid token" Error
1. Check that `LOGFIRE_TOKEN` is correctly set in `.env`
2. Verify the token has read access to the pyai project
3. Try using `LOGFIRE_READ_TOKEN` instead

### No Data Found
1. Increase the `--minutes` parameter (try 60 or 120)
2. Verify your runs are being logged to Logfire
3. Check that `service_name` matches 'pyai' in your configuration

### MCP Tools Not Available
If MCP tools aren't working:
1. Copy queries directly from `logfire_token_queries.sql`
2. Run them manually in the Logfire dashboard
3. Use the web interface at logfire.pydantic.dev

## Cost Optimization Tips

### High Token Usage Areas
1. **Report Writer** - Consider shorter reports or template optimization
2. **Content Cleaning** - Batch multiple items or use cheaper models
3. **Research Agents** - Optimize query expansion and scraping thresholds

### Model Selection
- **gpt-5-nano** - Use for simple tasks (weather, basic extraction)
- **gpt-5-mini** - Use for complex reasoning (research, reports)
- **Batch Operations** - Group similar operations to reduce per-request overhead

## Integration with Development Workflow

### After Each Run
```bash
# Quick check on token usage
python quick_token_report.py

# Detailed analysis for optimization
python logfire_token_report.py --output last_run_analysis.txt
```

### Performance Monitoring
- Track token usage trends over time
- Identify subprocess optimization opportunities  
- Monitor cost per research query
- Optimize model selection based on actual usage patterns

## Example Output

```
🔥 TOKEN USAGE REPORT
========================================
🆔 Trace: a1b2c3d4e5f6...
⏰ Start: 2025-01-10 14:30:25
⏱️  Duration: 127.3s
🤖 LLM Calls: 23
🎯 Total Tokens: 45,672

📋 BY SUBPROCESS:
------------------------------
report_writer   | gpt-5-mini          |   18,234 tokens (39.9%) |  3 calls
serper_research | gpt-5-mini          |   12,456 tokens (27.3%) |  8 calls
content_cleaning| gpt-5-nano          |    8,932 tokens (19.6%) | 12 calls
orchestrator    | gpt-5-mini          |    6,050 tokens (13.2%) |  1 calls
```

This gives you complete visibility into where your tokens are being consumed and helps optimize the most expensive operations.