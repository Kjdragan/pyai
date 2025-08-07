# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Environment setup
cp .env.example .env
# Edit .env with required API keys (OPENAI_API_KEY is mandatory)
```

### Running the Application
```bash
# Web interface (primary interface)
python src/main.py --web

# CLI interface
python src/main.py --query "Research AI trends"
python src/main.py  # Interactive mode
```

### Testing
```bash
# Quick smoke test
python run_tests.py quick

# All tests
python run_tests.py all

# Unit tests only
python run_tests.py unit

# Integration tests
python run_tests.py integration

# Single test file
python run_tests.py --test tests/test_agents.py

# With coverage
python run_tests.py coverage
```

### Code Quality
```bash
# Format code
python run_tests.py format

# Check formatting and imports
python run_tests.py lint

# Type checking
python run_tests.py types
```

## Architecture Overview

This is a **Pydantic-AI multi-agent system** with a hub-and-spoke architecture centered around an OrchestratorAgent that dispatches to specialized agents.

### Core Architecture Pattern

1. **OrchestratorAgent** (`agents/orchestrator_agent.py`) - Central coordinator
   - Parses user input into `JobRequest` via `parse_job_request()`
   - Routes to appropriate specialized agents based on detected job type
   - Aggregates results into `MasterOutputModel`
   - Streams progress via `StreamingUpdate` events

2. **Specialized Agents** - Each handles one domain:
   - **YouTubeAgent**: Extracts transcripts using youtube-transcript-api
   - **WeatherAgent**: OpenWeather API integration
   - **ResearchTavilyAgent** / **ResearchSerperAgent**: Parallel research pipelines with URL scraping
   - **ReportWriterAgent**: Generates reports from research/YouTube data

3. **Strict Type Safety** - All agent I/O uses Pydantic models in `models.py`:
   - `JobRequest` → `MasterOutputModel` data flow
   - Agent-specific models: `YouTubeTranscriptModel`, `WeatherModel`, etc.
   - `StreamingUpdate` for real-time UI updates

### Key Integration Points

**Entry Points:**
- `main.py`: CLI and web launcher
- `streamlit_app.py`: Web UI with chat interface
- `agents/orchestrator_agent.py:run_orchestrator_job()`: Main async workflow

**Configuration:**
- `config.py`: Environment-based config with API keys and model settings
- `.env` file required with `OPENAI_API_KEY` (minimum)

**Logging System:**
- `logging_config.py`: Comprehensive logging infrastructure
- Structured JSON logs in `src/logs/` directory
- Agent execution tracing and performance monitoring

### Agent Communication Pattern

All agents follow this pattern:
```python
async def process_[domain]_request(query: str) -> AgentResponse:
    # 1. Parse/validate input
    # 2. Call external APIs
    # 3. Return structured AgentResponse with success/error state
```

The OrchestratorAgent calls these functions and wraps results in domain-specific Pydantic models.

### URL Extraction (YouTube)

YouTube URLs are extracted using comprehensive regex patterns in `orchestrator_agent.py:extract_youtube_url()` supporting:
- Standard: `youtube.com/watch?v=ID`
- Short: `youtu.be/ID`  
- Mobile: `m.youtube.com`
- Shorts: `youtube.com/shorts/ID`
- All normalized to standard format for API consistency

### Error Handling Strategy

- **Agent Level**: Each agent returns `AgentResponse` with success/error state
- **Orchestrator Level**: Aggregates partial failures, continues processing
- **UI Level**: Streams errors as `StreamingUpdate` events
- **Logging**: Comprehensive error capture and monitoring

### Testing Strategy

- **Unit Tests**: Individual agent logic (`test_agents.py`, `test_models.py`)
- **Integration Tests**: Full workflow testing (`test_integration.py`)
- **Smoke Tests**: Quick validation of core imports and functionality
- **Mock Support**: API calls mocked for reliable testing

### Hygiene and Maintenance

The system includes automated hygiene tasks (`hygiene.py`) that run on startup:
- Log file cleanup
- Port conflict resolution  
- Temporary file cleanup
- Process management

## Development Notes

- **Python 3.13** minimum requirement
- **Pydantic-AI** for agent framework
- **UV** for dependency management
- **Streamlit** for web interface
- **Structured logging** for observability and monitoring

The system is designed for extensibility - new agents follow the established pattern and register in `agents/__init__.py`.