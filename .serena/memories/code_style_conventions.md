# Code Style and Conventions

## Language and Type Hints
- **Python 3.13+** minimum requirement
- **Full type hints** required for all functions and methods
- **Pydantic models** for all data structures
- **Async/await** pattern for all I/O operations

## Code Style
- **Black** for code formatting
- **isort** for import organization  
- **MyPy** for type checking
- **PEP 8** compliance
- **Docstrings**: Google-style for functions and classes

## Architecture Patterns
- **Agent Pattern**: Each agent follows `process_[domain]_request(query: str) -> AgentResponse`
- **Pydantic Models**: Strict typing with models in `models.py`
- **Error Handling**: Use `AgentResponse` with success/error state
- **Logging**: Comprehensive structured logging with agent context
- **Configuration**: Environment variables via `config.py`

## File Structure Patterns
```
src/
├── agents/           # Agent implementations
├── models.py         # Pydantic data models
├── config.py         # Configuration management
├── logging_config.py # Logging setup
└── main.py          # Entry points
```

## Agent Implementation Standards
1. Import required models from `models.py`
2. Use `get_agent_logger()` for logging
3. Handle errors gracefully with `AgentResponse`
4. Enable Pydantic-AI instrumentation
5. Follow async patterns throughout

## Testing Standards
- **Unit tests**: Individual agent logic
- **Integration tests**: Full workflow testing
- **Mock API calls** for reliable testing
- **pytest-asyncio** for async test support