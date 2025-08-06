# Essential Commands for PyAI Multi-Agent System

## Development Setup
```bash
# Install dependencies
uv sync

# Environment setup
cp .env.example .env
# Edit .env with required API keys (OPENAI_API_KEY is mandatory)
```

## Running the Application
```bash
# Web interface (primary interface)
python src/main.py --web

# CLI interface
python src/main.py --query "Research AI trends"
python src/main.py  # Interactive mode
```

## Testing Commands
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

## Code Quality Commands
```bash
# Format code
python run_tests.py format

# Check formatting and imports
python run_tests.py lint

# Type checking
python run_tests.py types
```

## Project Management Commands
```bash
# Development dependency management
uv add --group test pytest
uv add --group dev black isort mypy

# Production dependencies
uv add package_name

# Virtual environment
uv run python script.py
```

## System Commands (Linux WSL2)
- Standard Linux commands: `ls`, `cd`, `grep`, `find`
- Git commands: `git status`, `git add`, `git commit`, `git push`
- Process management: `ps aux`, `kill`, `pkill`
- File operations: `cat`, `head`, `tail`, `less`