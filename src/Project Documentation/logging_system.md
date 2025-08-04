# Logging System Documentation

## Overview

This document provides comprehensive documentation for the logging system implemented in the Pydantic-AI Multi-Agent System. The logging system is designed to provide deep visibility into agent behavior, system performance, and debugging information through multiple output channels and structured data formats.

## Architecture

### Core Components

The logging system consists of several key components working together to provide comprehensive observability:

```
┌─────────────────────────────────────────────────────────────┐
│                    Logging Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌──────────────────────────────┐   │
│  │   Application   │───▶│      LoggingManager          │   │
│  │     Code        │    │  - Centralized coordination  │   │
│  └─────────────────┘    │  - Logfire integration       │   │
│                         │  - Handler management        │   │
│                         └──────────────────────────────┘   │
│                                        │                   │
│                         ┌──────────────┼──────────────┐    │
│                         │              │              │    │
│                         ▼              ▼              ▼    │
│  ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐   │
│  │ Console Handler │ │ File Handler│ │ Logfire Handler │   │
│  │ (INFO level)    │ │(DEBUG level)│ │ (All levels)    │   │
│  │ Real-time       │ │ Structured  │ │ OpenTelemetry   │   │
│  │ monitoring      │ │ JSON logs   │ │ Distributed     │   │
│  └─────────────────┘ └─────────────┘ └─────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
src/
├── logging_config.py          # Core logging system implementation
├── logs/                      # Log output directory (auto-managed)
│   ├── pyai_YYYYMMDD_HHMMSS.log      # Debug logs (JSON format)
│   └── pyai_errors_YYYYMMDD_HHMMSS.log # Error-only logs
├── hygiene.py                 # Log cleanup and system hygiene
└── main.py                    # Logging system initialization
```

## Core Classes and Components

### 1. LoggingManager

The central coordinator for all logging activities.

**Key Responsibilities:**
- Initialize and configure all logging handlers
- Manage Logfire integration and OpenTelemetry instrumentation
- Provide factory methods for specialized loggers
- Handle log file rotation and management

**Configuration:**
```python
logging_manager = LoggingManager(
    logs_dir="/path/to/logs",     # Log file directory
    enable_logfire=True           # Enable Logfire integration
)
```

### 2. PydanticAIFormatter

Custom JSON formatter for structured logging output.

**Features:**
- ISO timestamp formatting
- Structured JSON output for machine parsing
- Exception stack trace capture
- Extra field serialization with type safety
- Agent context preservation

**Example Output:**
```json
{
  "timestamp": "2025-08-03T21:18:28.123456",
  "level": "INFO",
  "logger": "agent.YouTubeAgent",
  "message": "Agent YouTubeAgent starting execution",
  "module": "youtube_agent",
  "function": "process_youtube_request",
  "line": 158,
  "extra": {
    "agent_name": "YouTubeAgent",
    "agent_id": "youtube_001",
    "event_type": "agent_start",
    "query": "Process YouTube URL: https://youtube.com/watch?v=abc123"
  }
}
```

### 3. AgentLoggerAdapter

Specialized logger adapter for agent-specific logging with contextual information.

**Features:**
- Automatic agent context injection
- Specialized logging methods for common agent events
- Execution timing and success/failure tracking
- Model call and tool call logging

**Usage Example:**
```python
logger = get_agent_logger("YouTubeAgent", "youtube_001")

# Specialized logging methods
logger.log_agent_start("Process video transcript")
logger.log_model_call("gpt-4.1-mini", 1500)  # model, prompt_length
logger.log_tool_call("get_youtube_transcript", {"url": "..."})
logger.log_agent_complete(True, 5.2)  # success, duration
```

## Logging Levels and Outputs

### Console Output (INFO Level)

Real-time monitoring output displayed to the terminal during system execution.

**Characteristics:**
- Human-readable format with timestamps
- INFO level and above messages
- Color-coded by log level (if terminal supports it)
- Immediate feedback for system operators

**Example:**
```
21:18:28 - main - INFO - Starting Pydantic-AI Multi-Agent System CLI
21:18:28 - agent.YouTubeAgent - INFO - Agent YouTubeAgent starting execution
21:18:30 - httpx - INFO - HTTP Request: POST https://api.openai.com/v1/chat/completions
```

### Debug Log Files (DEBUG Level)

Comprehensive structured logs saved to rotating files for detailed analysis.

**Characteristics:**
- JSON format for machine parsing
- DEBUG level and above (all messages)
- Automatic rotation (10MB max, 5 backups)
- Timestamped filenames for session tracking
- Complete system state capture

**File Location:** `src/logs/pyai_YYYYMMDD_HHMMSS.log`

### Error Log Files (ERROR Level)

Isolated error tracking for quick debugging and alerting.

**Characteristics:**
- ERROR level only messages
- Same JSON structure as debug logs
- Separate file for easy error analysis
- Automatic rotation (5MB max, 3 backups)
- Exception stack traces included

**File Location:** `src/logs/pyai_errors_YYYYMMDD_HHMMSS.log`

### Logfire Integration (All Levels)

Advanced observability through Pydantic AI's built-in Logfire integration.

**Features:**
- OpenTelemetry-compliant distributed tracing
- Real-time dashboard visualization
- SQL queryable logs and metrics
- HTTP request/response instrumentation
- Agent execution flow visualization
- Model call performance tracking

**Dashboard URL:** `https://logfire-us.pydantic.dev/Kjdragan/pyai-debug`

## Agent Integration Patterns

### Basic Agent Logging

```python
from logging_config import get_agent_logger

def process_agent_request(query: str):
    logger = get_agent_logger("MyAgent")
    
    logger.info(f"Processing request: {query}")
    logger.debug("Detailed processing information")
    
    try:
        # Agent processing logic
        result = perform_processing()
        logger.info("Processing completed successfully")
        return result
    except Exception as e:
        logger.exception(f"Processing failed: {str(e)}")
        raise
```

### Advanced Agent Logging with Context Manager

```python
from logging_config import get_agent_logger

async def process_agent_request(query: str):
    logger = get_agent_logger("MyAgent", "agent_001")
    
    with logger.logging_manager.log_agent_execution("MyAgent", query) as agent_logger:
        # Automatic timing and success/failure tracking
        agent_logger.debug("Starting detailed processing")
        
        # Log model calls
        agent_logger.log_model_call("gpt-4.1-mini", len(query))
        
        # Log tool calls
        agent_logger.log_tool_call("my_tool", {"param": "value"})
        
        # Processing logic here
        result = await perform_processing()
        
        # Context manager automatically logs completion with timing
        return result
```

## Configuration and Initialization

### System Initialization

The logging system is automatically initialized during system startup in `main.py`:

```python
from logging_config import initialize_logging, get_logger

# Initialize comprehensive logging system
logging_manager = initialize_logging(
    logs_dir=os.path.join(os.path.dirname(__file__), "logs"),
    enable_logfire=True
)

# Get system logger
system_logger = get_logger("main")
```

### Logfire Configuration

The system automatically configures Logfire with optimal settings:

```python
# Enhanced Logfire configuration
logfire.configure(send_to_logfire=True, console=False)
logfire.instrument_pydantic_ai(event_mode='logs')  # Enhanced granularity
logfire.instrument_httpx(capture_all=True)         # HTTP instrumentation
```

### Custom Instrumentation Settings

For advanced use cases, custom instrumentation settings can be created:

```python
instrumentation_settings = logging_manager.create_instrumentation_settings()

# Use with Pydantic AI agents
agent = Agent(
    model=OpenAIModel("gpt-4.1-mini"),
    instrument=instrumentation_settings
)
```

## Log Management and Hygiene

### Automatic Cleanup

The hygiene system automatically manages log files during startup:

```python
# Executed automatically during system startup
from hygiene import run_hygiene_tasks
run_hygiene_tasks()
```

**Cleanup Operations:**
- Remove old log files from previous sessions
- Clean temporary files and caches
- Kill processes using port 8501 (Streamlit)
- Clear Python bytecode files

### Log Rotation

Automatic log rotation prevents disk space issues:

**Debug Logs:**
- Maximum file size: 10MB
- Backup count: 5 files
- Naming pattern: `pyai_YYYYMMDD_HHMMSS.log.1`, `.2`, etc.

**Error Logs:**
- Maximum file size: 5MB
- Backup count: 3 files
- Naming pattern: `pyai_errors_YYYYMMDD_HHMMSS.log.1`, `.2`, etc.

### Git Integration

Log files are automatically excluded from version control:

```gitignore
# Logs directory
src/logs/
*.log
```

## Event Types and Structured Data

### Standard Event Types

The logging system defines standard event types for consistency:

| Event Type | Description | Usage |
|------------|-------------|-------|
| `agent_start` | Agent execution begins | Automatic via context manager |
| `agent_complete` | Agent execution ends | Automatic via context manager |
| `model_call` | LLM API call made | `logger.log_model_call()` |
| `tool_call` | Tool function called | `logger.log_tool_call()` |
| `api_call` | External API request | `logging_manager.log_api_call()` |
| `system_event` | System-level event | `logging_manager.log_system_event()` |

### Structured Data Fields

Standard fields included in log entries:

**Core Fields:**
- `timestamp`: ISO format timestamp
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Logger name (e.g., "agent.YouTubeAgent")
- `message`: Human-readable message
- `module`: Python module name
- `function`: Function name where log was generated
- `line`: Line number in source code

**Agent Context Fields:**
- `agent_name`: Name of the agent (e.g., "YouTubeAgent")
- `agent_id`: Unique agent instance identifier
- `component`: Component type ("agent", "system", "api")
- `event_type`: Standardized event type
- `duration_seconds`: Execution duration (for completion events)
- `success`: Boolean success indicator

**Exception Fields (when applicable):**
- `exception.type`: Exception class name
- `exception.message`: Exception message
- `exception.traceback`: Full stack trace array

## Performance Considerations

### Logging Overhead

The logging system is designed for minimal performance impact:

**Console Logging:**
- Minimal overhead for INFO level messages
- Asynchronous where possible
- Efficient string formatting

**File Logging:**
- Buffered writes for performance
- JSON serialization optimized for common data types
- Automatic rotation prevents large file issues

**Logfire Integration:**
- OpenTelemetry batching for network efficiency
- Configurable sampling rates (if needed)
- Separate thread for telemetry data transmission

### Memory Management

**Log Rotation:**
- Prevents unlimited disk usage
- Automatic cleanup of old files
- Configurable retention policies

**Object Serialization:**
- Safe handling of non-serializable objects
- Automatic string conversion for complex types
- Memory-efficient JSON generation

## Troubleshooting

### Common Issues

**1. Log Files Not Created**
- Check directory permissions for `src/logs/`
- Verify logging initialization in `main.py`
- Check for filesystem space issues

**2. Logfire Not Working**
- Verify `LOGFIRE_READ_TOKEN` in `.env` file
- Check network connectivity
- Confirm Logfire project configuration

**3. Missing Log Messages**
- Verify log level configuration
- Check logger name consistency
- Ensure proper logger initialization

**4. Performance Issues**
- Review log level settings (reduce DEBUG in production)
- Check log file rotation settings
- Monitor disk I/O usage

### Debugging the Logging System

**Enable Debug Mode:**
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

**Check Log File Contents:**
```bash
# View latest debug log
tail -f src/logs/pyai_*.log | jq .

# View error logs only
tail -f src/logs/pyai_errors_*.log | jq .
```

**Monitor Logfire Dashboard:**
Visit the Logfire dashboard to view real-time traces and logs.

## Best Practices

### For Developers

**1. Use Appropriate Log Levels**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General system information
- `WARNING`: Potential issues that don't stop execution
- `ERROR`: Serious problems that need attention
- `CRITICAL`: System failure conditions

**2. Include Contextual Information**
```python
logger.info("Processing request", extra={
    'user_id': user_id,
    'request_type': request_type,
    'processing_time': duration
})
```

**3. Use Agent-Specific Loggers**
```python
# Good: Agent-specific logger
logger = get_agent_logger("YouTubeAgent")

# Avoid: Generic logger
logger = logging.getLogger(__name__)
```

**4. Log Exceptions Properly**
```python
try:
    risky_operation()
except Exception as e:
    logger.exception("Operation failed")  # Includes stack trace
    # or
    logger.error(f"Operation failed: {str(e)}", exc_info=True)
```

### For Operations

**1. Monitor Log File Growth**
- Set up disk space monitoring
- Configure appropriate rotation settings
- Archive old logs if needed for compliance

**2. Use Structured Queries**
```bash
# Find all errors from specific agent
jq 'select(.level == "ERROR" and .extra.agent_name == "YouTubeAgent")' src/logs/pyai_*.log

# Find slow operations
jq 'select(.extra.duration_seconds > 10)' src/logs/pyai_*.log
```

**3. Set Up Alerting**
- Monitor error log file for new entries
- Set up Logfire alerts for critical errors
- Track agent success/failure rates

## Integration Examples

### YouTube Agent Integration

The YouTube agent demonstrates comprehensive logging integration:

```python
async def process_youtube_request(url: str) -> AgentResponse:
    logger = get_agent_logger("YouTubeAgent")
    
    with logger.logging_manager.log_agent_execution("YouTubeAgent", f"Process YouTube URL: {url}") as agent_logger:
        try:
            agent_logger.debug(f"Extracting video ID from URL: {url}")
            video_id = extract_video_id(url)
            
            if not video_id:
                agent_logger.warning(f"Invalid YouTube URL format: {url}")
                return AgentResponse(success=False, error="Invalid URL")
            
            agent_logger.info(f"Processing video ID: {video_id}")
            agent_logger.debug("Fetching YouTube transcript")
            
            transcript, metadata = await fetch_youtube_transcript(video_id)
            
            agent_logger.info(f"Transcript fetched - Length: {len(transcript)} chars, Language: {metadata.get('language')}")
            agent_logger.log_model_call(config.YOUTUBE_MODEL, len(transcript))
            
            # ... processing logic ...
            
            agent_logger.info(f"YouTube processing completed successfully for video {video_id}")
            return AgentResponse(success=True, data=response_data)
            
        except Exception as e:
            agent_logger.error(f"YouTube processing failed for URL {url}: {str(e)}")
            return AgentResponse(success=False, error=str(e))
```

### System-Level Logging

Main system components use centralized logging:

```python
system_logger = get_logger("main")

system_logger.info("Starting Pydantic-AI Multi-Agent System CLI")
system_logger.debug("Validating configuration")
system_logger.info(f"Processing user query: {query}")
system_logger.exception(f"Unexpected error in CLI: {str(e)}")
system_logger.info("CLI session completed")
```

## Future Enhancements

### Planned Features

**1. Advanced Analytics**
- Agent performance metrics
- Success/failure rate tracking
- Processing time analysis
- Resource usage monitoring

**2. Enhanced Filtering**
- Log level filtering by component
- Agent-specific log isolation
- Time-based log filtering
- Custom query interfaces

**3. Integration Improvements**
- Additional observability platforms
- Custom webhook notifications
- Slack/Teams integration for alerts
- Prometheus metrics export

**4. Security Enhancements**
- Log data encryption at rest
- PII scrubbing capabilities
- Access control for sensitive logs
- Audit trail functionality

## Conclusion

The Pydantic-AI Multi-Agent System logging infrastructure provides comprehensive visibility into system behavior through multiple complementary channels. The combination of structured file logging, real-time console output, and advanced Logfire observability creates a robust foundation for debugging, monitoring, and system optimization.

The logging system follows industry best practices for observability while being specifically tailored to the needs of multi-agent AI systems, providing the deep insights necessary for understanding complex agent interactions and system performance.
