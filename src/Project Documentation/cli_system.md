# CLI System Documentation

## Overview

The Pydantic-AI Multi-Agent System provides a comprehensive command-line interface (CLI) built with Python's `argparse` module. The CLI serves as the primary entry point for interacting with the multi-agent system, offering both interactive query processing and web interface launching capabilities.

## Architecture

### Entry Point Structure

```
src/main.py
├── Hygiene System Initialization
├── Logging System Setup
├── Configuration Validation
├── CLI Interface (argparse)
├── Streamlit Web Interface Launcher
└── Async Agent Orchestration
```

### Core Components

**1. System Initialization**
- Automatic hygiene cleanup at startup
- Comprehensive logging system configuration
- Logfire observability integration
- Environment validation

**2. CLI Interface**
- Argparse-based command parsing
- Interactive and batch query processing
- Web interface launching
- Error handling and user feedback

**3. Agent Orchestration**
- Async multi-agent coordination
- Real-time streaming updates
- Comprehensive result reporting

## Command-Line Options

### Basic Usage

```bash
# Interactive CLI mode
python src/main.py

# Direct query processing
python src/main.py --query "Your question here"

# Launch web interface
python src/main.py --web
```

### Available Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `--web` | Flag | Launch Streamlit web interface | `python src/main.py --web` |
| `--query` | String | Process a specific query in CLI mode | `python src/main.py --query "Weather in NYC"` |

### Using UV Package Manager

The recommended way to run the CLI is using UV:

```bash
# Interactive CLI mode
uv run python src/main.py

# Direct query processing
uv run python src/main.py --query "Your question here"

# Launch web interface
uv run python src/main.py --web
```

## CLI Features

### 1. Interactive Mode

When run without arguments, the CLI enters interactive mode:

```bash
$ python src/main.py
🤖 Pydantic-AI Multi-Agent System
==================================================
✅ Configuration validated

Enter your query (or 'quit' to exit): _
```

**Interactive Features:**
- **Continuous Session**: Process multiple queries in a single session
- **Real-time Streaming**: Live updates as agents work
- **Graceful Exit**: Type 'quit' to exit cleanly
- **Error Recovery**: Continue processing after errors

### 2. Direct Query Mode

Process a single query and exit:

```bash
$ python src/main.py --query "What's the weather like in San Francisco?"
🤖 Pydantic-AI Multi-Agent System
==================================================
✅ Configuration validated

Processing: What's the weather like in San Francisco?
--------------------------------------------------
🔄 [21:32:15] Orchestrator: Starting job: weather - What's the weather like in San Francisco?
...
```

**Direct Query Features:**
- **Batch Processing**: Ideal for scripts and automation
- **Single Execution**: Process one query and exit
- **Full Logging**: Complete observability and debugging
- **Result Export**: Structured output for further processing

### 3. Web Interface Mode

Launch the Streamlit web application:

```bash
$ python src/main.py --web
🌐 Starting Streamlit web interface...
✅ Streamlit app launched successfully
🔗 Access the web interface at: http://localhost:8501
```

**Web Interface Features:**
- **Modern UI**: Beautiful, responsive web interface
- **Real-time Updates**: Live streaming of agent execution
- **Session Management**: Persistent conversation history
- **Multi-user Support**: Concurrent user sessions
- **Export Capabilities**: Download results and reports

## System Initialization

### Startup Sequence

The CLI follows a comprehensive startup sequence:

```
1. Hygiene Cleanup
   ├── Clean logs directory
   ├── Kill processes on port 8501
   ├── Remove temporary files
   └── Clear Python cache

2. Logging Configuration
   ├── Initialize structured logging
   ├── Configure Logfire integration
   ├── Setup file and console handlers
   └── Display clickable dashboard link

3. Configuration Validation
   ├── Check required API keys
   ├── Validate environment variables
   ├── Test model configurations
   └── Verify agent dependencies

4. Interface Launch
   ├── Parse command-line arguments
   ├── Initialize selected interface
   └── Begin query processing
```

### Startup Output Example

```bash
$ uv run python src/main.py
2025-08-03 21:24:43,328 - INFO - 🧹 Starting hygiene cleanup tasks...
2025-08-03 21:24:43,329 - INFO - Successfully cleaned 2 items from logs directory
2025-08-03 21:24:44,290 - INFO - ✅ Hygiene cleanup completed successfully!
✅ Logfire instrumentation enabled
🔗 Logfire Dashboard: https://logfire-us.pydantic.dev/Kjdragan/pyai-debug
   Click to view real-time traces and logs
📝 Logging configured - Files: pyai_20250803_212446.log, pyai_errors_20250803_212446.log
21:24:47 - main - INFO - Starting Pydantic-AI Multi-Agent System CLI
🤖 Pydantic-AI Multi-Agent System
==================================================
21:24:47 - main - INFO - Configuration validation successful
✅ Configuration validated
```

## Configuration Requirements

### Required Environment Variables

The CLI validates the following environment variables at startup:

| Variable | Description | Required For |
|----------|-------------|--------------|
| `OPENAI_API_KEY` | OpenAI API access | All agents (primary LLM) |
| `ANTHROPIC_API_KEY` | Anthropic API access | Alternative LLM support |
| `TAVILY_API_KEY` | Tavily research API | Research agents |
| `OPENWEATHER_API_KEY` | Weather data API | Weather agent |
| `YOUTUBE_API_KEY` | YouTube Data API | YouTube agent (optional) |
| `LOGFIRE_READ_TOKEN` | Logfire observability | Logging and monitoring |

### Configuration Validation

```bash
# Successful validation
✅ Configuration validated

# Missing keys example
❌ Missing required API keys: OPENAI_API_KEY, TAVILY_API_KEY
Please set the following environment variables:
  - OPENAI_API_KEY
  - TAVILY_API_KEY
```

## Query Processing

### Supported Query Types

The CLI can process various types of queries through specialized agents:

**1. Research Queries**
```bash
python src/main.py --query "Latest developments in AI"
```

**2. Weather Queries**
```bash
python src/main.py --query "Weather forecast for Tokyo"
```

**3. YouTube Analysis**
```bash
python src/main.py --query "Analyze this YouTube video: https://youtube.com/watch?v=abc123"
```

**4. Report Generation**
```bash
python src/main.py --query "Create a summary report about renewable energy trends"
```

### Query Processing Flow

```
User Query Input
       ↓
Query Classification
       ↓
Agent Selection & Orchestration
       ↓
Parallel Agent Execution
       ↓
Result Aggregation
       ↓
Report Generation
       ↓
Formatted Output
```

### Real-time Streaming Output

The CLI provides real-time updates during query processing:

```bash
Processing: Latest AI developments
--------------------------------------------------
🔄 [21:32:15] Orchestrator: Starting job: research - Latest AI developments
🔄 [21:32:15] Orchestrator: Running parallel research pipelines...
✅ [21:32:45] TavilyResearchAgent: Tavily research completed
✅ [21:32:50] DuckDuckGoResearchAgent: DuckDuckGo research completed
🔄 [21:32:50] Orchestrator: Generating summary report...
✅ [21:33:15] ReportWriterAgent: Summary report generated
🎉 [21:33:15] Orchestrator: Job completed successfully
```

## Output Formats

### CLI Result Display

The CLI provides structured output with multiple sections:

```bash
==================================================
📊 FINAL RESULTS
==================================================
Job Type: research
Query: Latest AI developments
Agents Used: TavilyResearchAgent, DuckDuckGoResearchAgent, ReportWriterAgent
Processing Time: 45.23s
Success: ✅

🔍 Research Results:
  Pipeline: both
  Original Query: Latest AI developments
  Sub-queries: 6
  Total Results: 15

📄 Report Results:
  Style: summary
  Source Type: research
  Word Count: 487

Generated Report:
------------------------------
# Research Summary: Latest AI Developments
...
------------------------------
```

### Logging Output

**Console Logging** (INFO level):
```
21:32:15 - main - INFO - Processing user query: Latest AI developments
21:32:16 - agent.OrchestratorAgent - INFO - Starting orchestration
21:32:45 - agent.TavilyResearchAgent - INFO - Research completed successfully
```

**Debug Log Files** (JSON format):
```json
{
  "timestamp": "2025-08-03T21:32:15.123456",
  "level": "DEBUG",
  "logger": "agent.OrchestratorAgent",
  "message": "Dispatching to research agents",
  "extra": {
    "agent_name": "OrchestratorAgent",
    "query": "Latest AI developments",
    "pipeline": "both"
  }
}
```

## Error Handling

### Configuration Errors

```bash
❌ Missing required API keys: OPENAI_API_KEY
Please set the following environment variables:
  - OPENAI_API_KEY
```

### Runtime Errors

```bash
⚠️ Error processing query: API rate limit exceeded
Retrying in 30 seconds...
```

### Agent Failures

```bash
❌ [21:32:30] TavilyResearchAgent: Research failed - Network timeout
🔄 [21:32:30] Orchestrator: Continuing with available results...
```

### Graceful Degradation

The CLI handles partial failures gracefully:
- Continue processing with available agents
- Provide partial results when possible
- Log detailed error information for debugging
- Maintain system stability during failures

## Advanced Usage

### Environment Configuration

**Using .env File**:
```bash
# Copy example configuration
cp .env.example .env

# Edit with your API keys
nano .env

# Run CLI
python src/main.py
```

**Using Environment Variables**:
```bash
export OPENAI_API_KEY="your-key-here"
export TAVILY_API_KEY="your-key-here"
python src/main.py --query "Your query"
```

### Batch Processing

**Process Multiple Queries**:
```bash
# Create queries file
echo "Weather in NYC" > queries.txt
echo "Latest tech news" >> queries.txt

# Process each query
while read query; do
    python src/main.py --query "$query"
done < queries.txt
```

**Script Integration**:
```python
import subprocess
import json

def process_query(query):
    result = subprocess.run([
        'python', 'src/main.py', '--query', query
    ], capture_output=True, text=True)
    return result.stdout

# Use in your scripts
response = process_query("Weather forecast")
```

### Development Mode

**Enable Debug Logging**:
```bash
export LOG_LEVEL=DEBUG
python src/main.py --query "Test query"
```

**Monitor Log Files**:
```bash
# Watch debug logs
tail -f src/logs/pyai_*.log | jq .

# Watch error logs
tail -f src/logs/pyai_errors_*.log | jq .
```

## Performance Optimization

### Startup Performance

**Cold Start**: ~3-5 seconds
- Hygiene cleanup: ~1s
- Logging setup: ~1s
- Configuration validation: ~1s
- Agent initialization: ~2s

**Warm Start**: ~1-2 seconds (subsequent runs)

### Query Processing Performance

**Typical Processing Times**:
- Simple queries: 10-30 seconds
- Research queries: 30-60 seconds
- Complex multi-agent queries: 60-120 seconds

**Performance Factors**:
- API response times
- Query complexity
- Number of agents involved
- Network connectivity

### Memory Usage

**Baseline**: ~50-100MB
**During Processing**: ~200-500MB
**Peak Usage**: ~1GB (for large research queries)

## Troubleshooting

### Common Issues

**1. Import Errors**
```bash
ModuleNotFoundError: No module named 'pydantic_ai'
```
**Solution**: Install dependencies with `uv sync`

**2. API Key Errors**
```bash
❌ Missing required API keys: OPENAI_API_KEY
```
**Solution**: Set required environment variables

**3. Port Conflicts**
```bash
Error: Port 8501 is already in use
```
**Solution**: The hygiene system automatically handles this

**4. Permission Errors**
```bash
PermissionError: [Errno 13] Permission denied: 'src/logs'
```
**Solution**: Check directory permissions or run with appropriate privileges

### Debug Mode

**Enable Verbose Output**:
```bash
python src/main.py --query "test" 2>&1 | tee debug.log
```

**Check Log Files**:
```bash
# Latest debug log
ls -la src/logs/pyai_*.log | tail -1

# View structured logs
jq . src/logs/pyai_*.log | less
```

**Monitor System Resources**:
```bash
# CPU and memory usage
top -p $(pgrep -f "python src/main.py")

# Network connections
netstat -an | grep :8501
```

## Integration Examples

### Shell Scripts

**Simple Query Script**:
```bash
#!/bin/bash
# query.sh
QUERY="$1"
if [ -z "$QUERY" ]; then
    echo "Usage: $0 'Your query here'"
    exit 1
fi

cd /path/to/pyai
uv run python src/main.py --query "$QUERY"
```

**Batch Processing Script**:
```bash
#!/bin/bash
# batch_process.sh
QUERIES_FILE="$1"
OUTPUT_DIR="results"

mkdir -p "$OUTPUT_DIR"

while IFS= read -r query; do
    echo "Processing: $query"
    timestamp=$(date +%Y%m%d_%H%M%S)
    output_file="$OUTPUT_DIR/result_$timestamp.txt"
    
    uv run python src/main.py --query "$query" > "$output_file"
    echo "Result saved to: $output_file"
done < "$QUERIES_FILE"
```

### Python Integration

**Direct Import**:
```python
import sys
import os
sys.path.append('src')

from main import main_cli
import asyncio

# Process query programmatically
async def process_query(query):
    return await main_cli(query)

# Usage
result = asyncio.run(process_query("Weather in London"))
```

**Subprocess Integration**:
```python
import subprocess
import json
from pathlib import Path

class PyAIClient:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
    
    def query(self, text):
        cmd = [
            'uv', 'run', 'python', 'src/main.py',
            '--query', text
        ]
        
        result = subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }

# Usage
client = PyAIClient('/path/to/pyai')
response = client.query("Latest AI news")
```

## Future Enhancements

### Planned CLI Features

**1. Enhanced Argument Parsing**
- Migration to Typer for better CLI experience
- Subcommands for different agent types
- Rich help formatting and auto-completion

**2. Configuration Management**
- Interactive configuration wizard
- Profile management for different environments
- Configuration validation and testing

**3. Output Formatting**
- Multiple output formats (JSON, YAML, CSV)
- Template-based output formatting
- Export to various file formats

**4. Performance Improvements**
- Caching for repeated queries
- Parallel processing optimizations
- Reduced startup time

### Potential Typer Migration

```python
# Future Typer-based CLI structure
import typer
from typing import Optional

app = typer.Typer(help="Pydantic-AI Multi-Agent System")

@app.command()
def query(
    text: str = typer.Argument(..., help="Query to process"),
    agent: Optional[str] = typer.Option(None, help="Specific agent to use"),
    format: str = typer.Option("text", help="Output format"),
    verbose: bool = typer.Option(False, help="Enable verbose output")
):
    """Process a query using the multi-agent system."""
    # Implementation here

@app.command()
def web():
    """Launch the Streamlit web interface."""
    # Implementation here

@app.command()
def config():
    """Manage system configuration."""
    # Implementation here

if __name__ == "__main__":
    app()
```

## Best Practices

### For Users

**1. Environment Setup**
- Use `.env` files for API keys
- Keep sensitive information secure
- Regularly update dependencies

**2. Query Formulation**
- Be specific and clear in queries
- Use natural language
- Provide context when needed

**3. Performance Optimization**
- Use direct query mode for single queries
- Monitor system resources for large queries
- Use web interface for interactive sessions

### For Developers

**1. Error Handling**
- Always check return codes
- Log errors appropriately
- Provide meaningful error messages

**2. Integration**
- Use subprocess for external integration
- Handle timeouts and failures gracefully
- Monitor log files for debugging

**3. Testing**
- Test with various query types
- Validate configuration before deployment
- Monitor performance metrics

## Conclusion

The Pydantic-AI Multi-Agent System CLI provides a robust, feature-rich interface for interacting with the multi-agent system. Built with Python's argparse, it offers comprehensive functionality for query processing, system management, and observability.

The CLI's design emphasizes:
- **Ease of Use**: Simple command structure and clear output
- **Flexibility**: Multiple interaction modes and configuration options
- **Reliability**: Comprehensive error handling and graceful degradation
- **Observability**: Detailed logging and real-time monitoring
- **Performance**: Optimized startup and processing times

Whether used for interactive exploration, batch processing, or integration into larger systems, the CLI provides the tools necessary for effective multi-agent AI system operation.
