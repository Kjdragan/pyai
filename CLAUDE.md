# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
```bash
# Install test dependencies
python run_tests.py install

# Run all tests
python run_tests.py all
uv run pytest tests/ -v

# Run specific test categories  
python run_tests.py unit        # Unit tests only
python run_tests.py integration # Integration tests only
python run_tests.py quick      # Fast smoke test

# Run specific test file
python run_tests.py --test tests/test_models.py
uv run pytest tests/test_models.py -v

# Run with coverage
python run_tests.py coverage
```

### Code Quality
```bash
# Lint code (check formatting and imports)
python run_tests.py lint

# Auto-format code
python run_tests.py format
uv run black src/ tests/
uv run isort src/ tests/

# Type checking
python run_tests.py types
uv run mypy src/ --ignore-missing-imports
```

### Running the Application
```bash
# Web interface (Streamlit)
python src/main.py --web

# CLI interactive mode
python src/main.py

# Direct query
python src/main.py --query "Research AI trends in 2024"
```

### Development Setup
```bash
# Install dependencies
uv sync

# Copy environment template and configure API keys
cp .env.example .env
# Edit .env with your API keys
```

## Architecture Overview

### Core System Design
This is a **Pydantic-AI powered multi-agent orchestration system** where a central `OrchestratorAgent` coordinates specialized agents through strictly typed interfaces. The system uses **async-first design** with **comprehensive state management** and **real-time streaming updates**.

Key architectural principles:
- **Type-Safe Agent Communication**: All data flows through Pydantic models with strict validation
- **Centralized Orchestration**: Single orchestrator manages agent dispatch, parallel execution, and result aggregation  
- **Performance-Optimized Pipeline**: Batched content processing, parallel API calls, and intelligent caching
- **Comprehensive Observability**: Logfire integration with detailed tracing and performance analytics

### Agent Architecture

#### OrchestratorAgent (`src/agents/orchestrator_agent.py`)
Central coordinator with intelligent workflow optimization:
- **Parallel Execution Engine**: `analyze_and_execute_optimal_workflow()` automatically determines which agents can run concurrently vs sequentially
- **Query Intent Analysis**: LLM-powered query classification to determine required agents (YouTube, Weather, Research, Report)  
- **Cross-Agent Deduplication**: Prevents duplicate URL scraping across research APIs
- **Centralized Query Expansion**: Single expansion shared across all research agents (prevents 6→3 query duplication)
- **Intelligent Tool Selection**: Context-aware routing between simple parallel dispatch vs complex dependency management

#### Research Pipeline (`research_tavily_agent.py`, `research_serper_agent.py`)
Sophisticated multi-API research system with:
- **Centralized Query Expansion**: Uses pre-generated sub-queries from orchestrator instead of generating duplicates
- **Programmatic Garbage Filtering**: Multi-heuristic content quality analysis before expensive LLM processing
- **Batched Content Cleaning**: Parallel batch processing replaces sequential individual cleaning calls
- **Cross-API Deduplication**: URL-based deduplication prevents duplicate scraping
- **Quality Metrics Pipeline**: Complete visibility into filtering process with pre/post content tracking

#### Report Generation (`report_writer_agent.py`, `advanced_report_templates.py`)
Intelligent, adaptive report generation:
- **Domain-Aware Templates**: Automatic domain detection (technology, business, science, etc.) with specialized templates  
- **Multi-Quality Processing**: Standard/Enhanced/Premium quality levels using different LLM models
- **Universal Data Synthesis**: Seamless handling of any combination of YouTube, research, weather data
- **Context-Aware Structure**: Templates adapt to query complexity and available data sources

### Performance Architecture

#### Critical Performance Optimizations
1. **Batched Content Processing**: Research agents use `clean_multiple_contents_batched()` instead of individual cleaning calls
2. **Garbage Content Filtering**: Programmatic heuristic analysis before expensive LLM processing  
3. **Centralized Query Expansion**: Single set of 3 sub-queries shared across APIs (prevents duplication)
4. **Parallel Agent Dispatch**: Independent agents (YouTube, Weather, Research) run concurrently
5. **Intelligent Caching**: Agent result caching prevents re-execution within same orchestration

#### State Management (`state_manager.py`)
Centralized state tracking across the entire pipeline:
- **MasterStateManager**: Unified state aggregation from all agents
- **Performance Metrics**: Detailed timing, API call counts, success rates
- **Error Tracking**: Comprehensive error collection and reporting
- **Data Flow Visibility**: Complete pipeline traceability

### Data Models (`src/models.py`)

#### Core Models
- **`MasterOutputModel`**: Aggregated results from entire orchestration
- **`ResearchPipelineModel`**: Combined research results with deduplication  
- **`ResearchItem`**: Individual research result with comprehensive metadata including garbage filtering pipeline visibility
- **`ReportGenerationModel`**: Generated reports with quality metrics and confidence scoring
- **`StreamingUpdate`**: Real-time progress updates for UI integration

#### Enhanced Visibility Models  
Research items now include complete pipeline visibility:
```python
# Garbage filtering pipeline tracking
pre_filter_content: Optional[str]         # Full content before filtering (truncated post-processing)
pre_filter_content_length: Optional[int]  # Character count pre-filtering
post_filter_content: Optional[str]        # Content after filtering (if passed)  
post_filter_content_length: Optional[int] # Character count post-filtering
garbage_filtered: Optional[bool]          # Whether identified as garbage
filter_reason: Optional[str]              # Specific filtering reason
quality_score: Optional[float]            # Overall quality score (0-1)
```

### Configuration System (`src/config.py`)

#### Model Management
The system uses **GPT-5 models** with intelligent model assignment:
- **NANO_MODEL**: `gpt-5-nano-2025-08-07` (fast/cheap for simple tasks)
- **STANDARD_MODEL**: `gpt-5-mini-2025-08-07` (intelligent reasoning)
- **Agent-Specific Models**: Configurable per-agent model assignment via environment variables

#### Required API Keys
- `OPENAI_API_KEY` (required)
- `TAVILY_API_KEY` (optional - research)
- `SERPER_API_KEY` (optional - research)  
- `OPENWEATHER_API_KEY` (optional - weather)
- `LOGFIRE_TOKEN` (optional - observability)

### Content Quality Pipeline (`src/utils/content_quality_filter.py`)

Multi-stage heuristic analysis preventing garbage content from reaching expensive LLM processing:
- **Repetition Analysis**: Detects keyword spam and repeated content blocks
- **Navigation Detection**: Filters menu/footer/sidebar content  
- **Domain Quality Assessment**: Evaluates URL patterns and domain reputation
- **Readability Scoring**: Uses textstat analysis for content quality
- **Spam Pattern Detection**: Identifies promotional/SEO spam content

Content lifecycle: Raw Scraped → Garbage Filter → LLM Cleaning → Report Generation

### Testing Architecture (`pytest.ini`, `run_tests.py`)

Comprehensive test framework with:
- **Async Test Support**: `asyncio_mode = auto` for proper async testing
- **Test Categories**: Unit, integration, slow, API-dependent tests via markers  
- **Test Runner Script**: Convenient `run_tests.py` with multiple commands
- **Coverage Integration**: HTML and terminal coverage reporting
- **Smoke Testing**: Quick validation of core system functionality

### Key Development Patterns

#### Agent Implementation Pattern
All agents follow this structure:
1. **Pydantic-AI Agent**: Use `Agent` class with proper type hints
2. **Dependencies Class**: Centralized dependencies with timeout/retry configuration  
3. **Tool Methods**: Use `@agent.tool` decorator for agent capabilities
4. **Structured Output**: Return typed Pydantic models, not raw strings
5. **Error Handling**: Comprehensive try/catch with detailed error reporting

#### State Management Pattern  
- **Centralized State**: Use `MasterStateManager` for cross-agent data sharing
- **Immutable Updates**: State updates through manager methods, not direct modification
- **Complete Traceability**: All state changes logged with timestamps and source agents

#### Performance Pattern
- **Batch Operations**: Replace individual calls with batched processing where possible
- **Parallel Dispatch**: Use `asyncio.gather()` for independent operations
- **Early Filtering**: Apply cheap heuristic filters before expensive LLM processing  
- **Result Caching**: Cache expensive operations within orchestration scope