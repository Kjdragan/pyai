# Serena MCP: Onboarding + Prepare-for-New-Conversation Output

Generated: 2025-08-10 18:15 (local)
Project: /home/kjdrag/lrepos/pyai (Linux)

---

## 1) Tools Invoked
- activate_project → pyai
- check_onboarding_performed → already performed
- list_memories → 4 memories available
- onboarding → guidance for collecting high-level project info
- read_memory → suggested_commands, task_completion_checklist, code_style_conventions, string-escaping-infinite-loop-debugging

---

## 2) Onboarding Status
- Status: Onboarding has ALREADY been performed for this project.
- Available memories: [suggested_commands, task_completion_checklist, string-escaping-infinite-loop-debugging, code_style_conventions]

---

## 3) Serena Onboarding Guidance (Tool Output Summary)
Serena recommends assembling high-level project information and saving it to memory files:
- Project purpose, tech stack, code style/conventions
- Commands for running, testing, formatting, linting
- Rough structure of the codebase
- Linux/utility commands you use
- Any special design patterns/guidelines

These should be persisted using `write_memory` (Serena’s memory system) so future conversations can rehydrate quickly.

---

## 4) Project Memories (Read via Serena)

### 4.1 suggested_commands
```
# Essential Commands for PyAI Multi-Agent System

## Development Setup
uv sync
cp .env.example .env
# Edit .env with required API keys (OPENAI_API_KEY is mandatory)

## Running the Application
python src/main.py --web
python src/main.py --query "Research AI trends"
python src/main.py  # Interactive mode

## Testing Commands
python run_tests.py quick
python run_tests.py all
python run_tests.py unit
python run_tests.py integration
python run_tests.py --test tests/test_agents.py
python run_tests.py coverage

## Code Quality Commands
python run_tests.py format
python run_tests.py lint
python run_tests.py types

## Project Management Commands
uv add --group test pytest
uv add --group dev black isort mypy
uv add package_name
uv run python script.py

## System Commands (Linux WSL2)
- ls, cd, grep, find
- git status, git add, git commit, git push
- ps aux, kill, pkill
- cat, head, tail, less
```

### 4.2 task_completion_checklist
```
# Task Completion Checklist

## Code Quality Checks
format → lint → types → tests

## Testing Requirements
Units, integrations, smoke; ensure pass

## Documentation Updates
Docstrings, type hints, comments

## Environment Validation
Ensure .env keys; verify Logfire traces when modifying observability

## Deployment Preparation
Run in CLI and web; validate config & logging

## Agent-Specific Requirements
YouTube/Weather/Research/Report agent checks

## Observability Verification
Logfire traces present; structured logging OK; timing captured
```

### 4.3 code_style_conventions
```
# Code Style and Conventions
- Python 3.13+
- Full type hints; Pydantic models for data
- Async/await for I/O
- Black, isort, MyPy; PEP8; Google-style docstrings
- Architecture: agents, strict typing in models.py
- Error handling via AgentResponse; structured logging; env via config.py
- File structure includes src/agents, models.py, config.py, logging_config.py, main.py
- Testing: unit/integration; mock APIs; pytest-asyncio
```

### 4.4 string-escaping-infinite-loop-debugging
```
# Critical String Escaping Bug Pattern
- Double-escaped newlines ("\\n") in f-strings can cause infinite loops and massive API usage
- Search: grep -r "\\\\n" src/agents/ --include="*.py"
- Fix: use "\n" not "\\n" in f-strings
```

---

## 5) Prepare-for-New-Conversation Package (Synthesized)
Use this package at the start of any fresh chat to rehydrate Serena/LLM context.

### 5.1 Minimal Rehydration Steps
1. Activate project
   - Tool: `activate_project` with path `/home/kjdrag/lrepos/pyai`
2. Ensure onboarding is present
   - Tool: `check_onboarding_performed` (expect: already performed)
3. Load key memories
   - Tool: `read_memory` for:
     - `suggested_commands`
     - `task_completion_checklist`
     - `code_style_conventions`
     - `string-escaping-infinite-loop-debugging`
4. Set working assumptions (system-level reminders)
   - Python 3.13+, full type hints, Pydantic models
   - Black/isort/MyPy/PEP8; Google docstrings
   - Async I/O everywhere
   - Structured logging + Logfire enabled
5. Confirm run commands
   - Primary UI: `python src/main.py --web` (or `uv run src/main.py --web`)
   - CLI: `python src/main.py --query "..."`
6. Confirm quality loop
   - `python run_tests.py format | lint | types | all`

### 5.2 Suggested System Prompt Snippet (to paste into a new chat)
```
You are assisting on the PyAI multi-agent project at /home/kjdrag/lrepos/pyai.
Follow these constraints and practices:
- Python 3.13+, full type hints; async for I/O
- Use Pydantic models; Google-style docstrings
- Use Black, isort, MyPy; adhere to PEP8
- Use Serena tools for semantic navigation and safe edits
- Before editing: find_symbol/get_symbols_overview; prefer replace_symbol_body/insert_* over raw patches
- Validate with tests and task_completion_checklist; ensure Logfire observability remains intact
Key references to load via memory: suggested_commands, task_completion_checklist, code_style_conventions, string-escaping-infinite-loop-debugging.
```

### 5.3 Quick Commands Block (copy/paste)
```
# Setup
uv sync && cp -n .env.example .env || true

# Run (web)
python src/main.py --web

# Run (CLI)
python src/main.py --query "Research AI trends"

# Quality loop
python run_tests.py format && \
python run_tests.py lint && \
python run_tests.py types && \
python run_tests.py all
```

### 5.4 Known Pitfalls to Recheck Early
- Double-escaped newlines in prompts (see memory)
- Env keys present; Logfire enabled and not double-instrumented
- When instrumenting observability: avoid duplicate OTel instrumentation warnings (harmless, but prefer single configuration site)

---

## 6) Notes for Future Use
- If onboarding content changes, re-run Serena onboarding and persist updates with `write_memory`.
- Consider adding additional memories for: project architecture overview, agent interaction map, and common debugging playbooks.

---

End of report.
