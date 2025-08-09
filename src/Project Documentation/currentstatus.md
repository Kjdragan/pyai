# PyAI – Current Status and Developer Onboarding Snapshot

This document is a concise, always-fresh starting point so a new chat/agent can immediately continue development without re-reading the entire history.

Read this first, then also skim:
- `CLAUDE.md`
- `src/Project Documentation/lessonslearned.md`
- `.env.example` or your local `.env` (if present)
- `tests/` and `src/agents/`

## Quickstart for Future Me
- Use python3. In this environment, `python` is not available. Always run: `python3` or `uv run python3`.
- Activate venv before running anything: `source .venv/bin/activate`.
- Prefer fast, isolated tests that avoid external APIs unless you explicitly need them.
- For logging verification (no APIs), run: `python3 test_logger_only.py`.
- Default research logs live in `src/logs/state/` (pipeline). The test writes to project `logs/` by design.

## Architecture Snapshot
Hub-and-spoke multi-agent system using Pydantic-AI.
- OrchestratorAgent (central coordinator)
- Specialized agents:
  - `YouTubeAgent` – transcript extraction
  - `WeatherAgent` – OpenWeather
  - `TavilyResearchAgent` and `SerperResearchAgent` – research pipelines
  - `ReportWriterAgent` – report generation

Interfaces:
- CLI `main.py` and Streamlit `streamlit_app.py` (streaming)

Key files:
- `src/models.py` – Pydantic models (e.g., `ResearchItem`, `MasterOutputModel`, `DomainAnalysis`)
- `src/agents/` – agent implementations
- `src/research_logger.py` – unified state logging (full + truncated copies)
- `src/config.py` – configuration (env-based)
- `tests/` – async tests and unit checks

APIs used:
- OpenAI (primary), Anthropic (optional), Tavily, Serper (Google), OpenWeather, YouTube Transcript

## Configuration Cheatsheet (src/config.py)
Model selection defaults:
- `NANO_MODEL = gpt-5-nano-2025-08-07`
- `STANDARD_MODEL = gpt-5-mini-2025-08-07`
- Agent model getters route appropriately via `Config.get_agent_model()`

Classifier mode:
- `DOMAIN_CLASSIFIER_MODE` in {`llm`, `heuristic`} (default `llm`)

Timezone:
- `TIMEZONE = America/Chicago` (centralized time provider; all agents use this)

State logging & truncation (Dual-output):
- `WRITE_TRUNCATED_STATE_COPY` (default true)
- `LLM_STATE_MAX_FIELD_CHARS` (default 1000)
- `LLM_STATE_TRUNCATE_FIELDS` (default: `raw_content,scraped_content,pre_filter_content,post_filter_content`)

Research parallelism & thresholds:
- `RESEARCH_PARALLELISM_ENABLED` (default false), `RESEARCH_MAX_CONCURRENCY` (default 8)
- `SERPER_MAX_CONCURRENCY` (default 5)
- Tavily: `TAVILY_TIME_RANGE`, `TAVILY_SEARCH_DEPTH`, `TAVILY_MIN_SCORE`, `TAVILY_SCRAPING_THRESHOLD`, `TAVILY_RATE_LIMIT_RPS`
- Quality filter: `GARBAGE_FILTER_THRESHOLD` (default 0.2)
- PDF cleaning: `CLEANING_SKIP_PDFS` (default false — PDFs are processed)

Note: `dotenv` import is optional; config gracefully degrades if python-dotenv isn’t installed.

## Logging & State (src/research_logger.py)
- Always writes a full JSON state snapshot.
- If enabled, also writes a truncated LLM-friendly sibling file with the same name plus `.llm.json`.
- Truncation is a safe recursive deep copy that only caps long string fields whose keys match `LLM_STATE_TRUNCATE_FIELDS`.
- Full file remains the source of truth; truncated file is for debugging and LLM submission.

Paths:
- Pipeline default: `ResearchDataLogger(log_dir="src/logs/state")`
- Master state: `MasterStateLogger(log_dir="src/logs/state")`
- Test script uses `logs/` for convenience.

## ResearchItem Processing Flow (ordered)
- Discovery & scoring
  - `query_variant`, `source_url`, `title`, `snippet`, `relevance_score`, `timestamp`
- Fetch & scrape status
  - `content_scraped`, `scraping_error`
- Raw capture (as fetched)
  - `raw_content`, `raw_content_length`
- Extraction (primary text)
  - `scraped_content`, `content_length`
- Cleaning/normalization snapshot
  - `content_cleaned`, `original_content_length`, `pre_filter_content`, `pre_filter_content_length`
- Filtering/garbage reduction
  - `post_filter_content`, `post_filter_content_length`, `garbage_filtered`, `filter_reason`
- Quality assessment
  - `quality_score`
- Extras
  - `metadata`

Key distinction:
- `raw_content` = as-fetched payload (HTML/transcript/PDF-to-text)
- `scraped_content` = text extracted from raw_content (main article text, etc.). They may be similar for text-first APIs, but we store both for audit and quote retention.

## Recent Work & Rationale
- LLM-based Query Domain Classifier (Nano model) integrated across report gen; `DOMAIN_CLASSIFIER_MODE` toggles llm/heuristic.
- Centralized LLM-driven sub-question expansion for research agents; improved quality; both Tavily and Serper/DuckDuckGo refactored to use it.
- Centralized timezone provider; `TIMEZONE` in config; agents use timezone-aware date/time in prompts.
- Quote retention focus: models and agents updated to preserve `raw_content` alongside `scraped` and cleaned variants; diagnostics added.
- Dual-output logging implemented (full + truncated `.llm.json`) with configurable field limits; data integrity maintained by never mutating pipeline artifacts.
- Fixed issues: use `ResearchItem` (not `ResearchResult`); Pydantic `HttpUrl` JSON serialization in logger; async bug in `get_enhanced_domain_context` fixed; tests added for classifier (with optional live-API if key present).

Latest changes (Aug 08, 2025):
- Parallel research dispatch in `src/agents/orchestrator_agent.py` using `asyncio.gather()` for Tavily + Serper.
- New Pydantic-AI agents: `src/agents/research_tavily_agent.py` and `src/agents/research_serper_agent.py` returning `ResearchPipelineModel`.
- `src/agents/content_cleaning_agent.py`: batched cleaning and PDF-aware handling within batches.
- `src/config.py`: centralized config with research parallelism, Tavily/Serper knobs, and cleaning flags.
- Note: `utils/intelligent_scraper.py` and `utils/pdf_extractor.py` are referenced by agents but not yet present—implement next to avoid ImportError.

## Testing Guidance
- Activate venv: `source .venv/bin/activate`
- Use `python3`, not `python`.
- Quick local logging test (no external APIs): `python3 test_logger_only.py`
  - Produces both full and `.llm.json` copies (see `logs/` in project root for the test; pipeline uses `src/logs/state/`).
- When needed, run live API tests only if keys exist; avoid long runs (hang risk).

## Open TODOs / Next Steps
- Implement missing utilities referenced by agents:
  - `src/utils/intelligent_scraper.py` (pre-flight gating, allow/deny lists, canonicalization)
  - `src/utils/pdf_extractor.py` (fast local PDF text extraction, caching)
- Add citations section to reports (reference metadata of sources used; not scholarly strictness required).
- Create `logs/reports/` output directory and persist final report artifacts there.
- Integrate/verify tracing (e.g., Arise) alongside existing instrumentation.
- Validate parallel research path with bounded concurrency and idempotency guards.
- Run a short E2E test with known PDF-heavy sources (e.g., NREL) to confirm extraction + cleaning.

## Operational Notes (Environment & Pitfalls)
- Long-running commands can hang; keep tests short and isolated.
- Ensure API keys are set for live tests: `OPENAI_API_KEY`, `TAVILY_API_KEY`, etc.
- Use `uv` if that’s your workflow, but keep `python3` in the invocations.

## References & Must-Read Files
- `CLAUDE.md` — high-level guidance, conventions, and prompts for assistants.
- `src/Project Documentation/lessonslearned.md` — critical debugging and architectural insights (env override ordering, async patterns, Logfire, streaming, Pydantic-AI pitfalls).
- `tests/` — look for async tests and domain classifier checks.
- `src/agents/research_tavily_agent.py`, `src/agents/research_serper_agent.py`, `src/agents/content_cleaning_agent.py`, and `src/config.py` — research agents, cleaning pipeline, and configuration knobs.

---

If you’re a future assistant: load this file early, along with `CLAUDE.md` and `lessonslearned.md`, then list current log outputs and config settings before making changes. Keep edits small and reversible, and prefer isolated tests to validate behavior (especially logging and state management).
