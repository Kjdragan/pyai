# Pydantic-AI Multi-Agent System

A modular, Pydantic-AI-driven multi-agent framework with an **OrchestratorAgent** that dispatches to specialized agents (YouTube, Weather, Research pipelines, Report Writer), validates all I/O via Pydantic models, and streams results through a Streamlit chat UI.

## Features

🤖 **Multi-Agent Architecture**
- **OrchestratorAgent**: Central coordinator for dispatching jobs
- **YouTubeAgent**: Fetch video transcripts and metadata
- **WeatherAgent**: Current weather + 7-day forecasts via OpenWeather API
- **ResearchPipeline1**: Tavily API with query expansion
- **ResearchPipeline2**: DuckDuckGo with query expansion
- **ReportWriterAgent**: Generate comprehensive, top-10, or summary reports

💬 **Streamlit Chat Interface**
- Conversational UI for job submission
- Real-time streaming of partial and final responses
- Interactive result visualization
- Job history tracking

🔒 **Type-Safe Design**
- All agent I/O strictly typed via Pydantic models
- Comprehensive data validation
- Structured output aggregation under `MasterOutputModel`

🔄 **Robust Error Handling**
- Built-in retry logic on all downstream API calls
- Graceful error handling and reporting
- Fallback mechanisms between research pipelines

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd pyai

# Install dependencies
uv sync
# or
pip install -e .
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# Required: OPENAI_API_KEY
# Optional: ANTHROPIC_API_KEY, TAVILY_API_KEY, OPENWEATHER_API_KEY
```

### 3. Run the Application

**Streamlit Web Interface:**
```bash
python src/main.py --web
```

**Command Line Interface:**
```bash
# Interactive mode
python src/main.py

# Direct query
python src/main.py --query "Research AI trends in 2024"
```

## Usage Examples

### Research Queries
```
"Research climate change impacts"
"Generate comprehensive report on renewable energy"
"Create top-10 insights about artificial intelligence"
```

### YouTube Analysis
```
"Analyze YouTube video: https://www.youtube.com/watch?v=VIDEO_ID"
"Summarize this video: <YouTube URL>"
```

### Weather Queries
```
"Weather forecast for New York"
"Current weather in Tokyo"
```

## System Architecture

```
┌───────────────────────────┐
│    Streamlit Chat UI     │
└─────────────┬─────────────┘
              │
   ┌──────────▼──────────┐
   │ OrchestratorAgent   │ ← Pydantic-AI Agent
   │ • dispatch("youtube")       │
   │ • dispatch("weather")       │
   │ • dispatch("research1")     │
   │ • dispatch("research2")     │
   │ • dispatch("report_writer") │
   │ • aggregate outputs         │
   └──────────┬───────────┘
              │
    ┌─────────┴───────────┐
    │  Registered Agents  │
    │                     │
    │  YouTubeAgent       │
    │  WeatherAgent       │
    │  Research1Agent     │
    │  Research2Agent     │
    │  ReportWriterAgent  │
    └─────────────────────┘
```

## Data Models

All agent interactions use strictly typed Pydantic models:

- **`YouTubeTranscriptModel`**: Video transcript and metadata
- **`WeatherModel`**: Current weather and forecast data
- **`ResearchPipelineModel`**: Research results with query expansion
- **`ReportGenerationModel`**: Generated reports with metadata
- **`MasterOutputModel`**: Aggregated results from all agents
- **`StreamingUpdate`**: Real-time progress updates

## API Keys Required

| Service | Required | Purpose |
|---------|----------|----------|
| OpenAI | ✅ Yes | Core LLM functionality |
| Anthropic | ❌ Optional | Alternative LLM provider |
| Tavily | ❌ Optional | Research Pipeline 1 |
| OpenWeather | ❌ Optional | Weather forecasts |

## Project Structure

```
pyai/
├── src/
│   ├── agents/
│   │   ├── __init__.py              # Agent registry
│   │   ├── orchestrator_agent.py    # Central coordinator
│   │   ├── youtube_agent.py         # YouTube transcript fetcher
│   │   ├── weather_agent.py         # Weather data fetcher
│   │   ├── research_tavily_agent.py # Tavily research pipeline
│   │   ├── research_duckduckgo_agent.py # DuckDuckGo research
│   │   └── report_writer_agent.py   # Report generator
│   ├── models.py                    # Pydantic data models
│   ├── config.py                    # Configuration management
│   ├── streamlit_app.py            # Web interface
│   └── main.py                     # CLI entry point
├── pyproject.toml                  # Dependencies
├── .env.example                    # Environment template
└── README.md                       # This file
```

## Development

### Adding New Agents

1. Create agent file in `src/agents/`
2. Implement using Pydantic-AI `Agent` class
3. Add to agent registry in `src/agents/__init__.py`
4. Update orchestrator dispatch logic

### Extending Data Models

1. Add new models to `src/models.py`
2. Update `MasterOutputModel` if needed
3. Ensure type safety throughout pipeline

## Troubleshooting

**Missing API Keys:**
- Check `.env` file configuration
- Verify environment variables are loaded

**Agent Failures:**
- Check API key validity and quotas
- Review error messages in streaming output
- Verify network connectivity

**Streamlit Issues:**
- Ensure port 8501 is available
- Check for conflicting Python environments

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.