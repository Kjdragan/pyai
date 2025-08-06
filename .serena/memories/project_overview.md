# PyAI Multi-Agent System - Project Overview

## Project Purpose
A Pydantic-AI multi-agent system with hub-and-spoke architecture for processing user queries through specialized agents including YouTube transcript analysis, weather forecasting, research, and report generation.

## Tech Stack
- **Core Framework**: Pydantic-AI (with OpenAI integration)
- **Language**: Python 3.13+
- **Dependency Management**: UV
- **Web Interface**: Streamlit
- **Observability**: Logfire with OpenTelemetry
- **APIs Used**: YouTube Transcript API, OpenWeather, Tavily, Serper

## Architecture
- **Hub-and-Spoke Design**: OrchestratorAgent coordinates specialized agents
- **Entry Points**: CLI (`main.py`) and Web UI (`streamlit_app.py`)
- **Agents**: YouTube, Weather, Research (Tavily/Serper), Report Writer
- **Type Safety**: All I/O through Pydantic models
- **Async Processing**: Full async/await support with streaming updates

## Key Components
- `src/main.py`: Main CLI entry point
- `src/streamlit_app.py`: Web interface
- `src/agents/orchestrator_agent.py`: Central coordinator
- `src/agents/`: Specialized agent implementations
- `src/models.py`: Pydantic data models
- `src/config.py`: Environment-based configuration
- `src/logging_config.py`: Comprehensive logging with Logfire

## Current Status
- Core architecture implemented
- All agents functional
- Logfire observability integrated
- Web and CLI interfaces working
- Test suite available