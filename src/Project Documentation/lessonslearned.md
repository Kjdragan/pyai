# Lessons Learned (PyAI)

A living document of critical insights, pitfalls, and best practices gathered while building and iterating on the PyAI multi-agent system. New assistants/devs should skim this along with `currentstatus.md` and `CLAUDE.md`.

See also:
- `currentstatus.md` — quick onboarding snapshot
- `CLAUDE.md` — conventions and prompts

## Environment & Execution
- **Always use python3**: This environment lacks a `python` shim. Use `python3` or `uv run python3`. Shebangs: `#!/usr/bin/env python3`.
- **Activate venv**: `source .venv/bin/activate` before running scripts or tests.
- **Avoid long runs**: Long pipelines and live API tests can hang; prefer short, isolated tests.
- **Dotenv is optional**: Import `python-dotenv` defensively; provide a no-op fallback so the app runs even if the package isn't installed.

## Configuration Patterns
- **Centralized config (`src/config.py`)**:
  - Model mapping via `Config.get_agent_model()`; default models tuned for cost/perf.
  - `DOMAIN_CLASSIFIER_MODE` toggles LLM vs heuristic.
  - `TIMEZONE` centralized (America/Chicago); all agents use timezone-aware prompts.
  - **Dual-output logging flags**:
    - `WRITE_TRUNCATED_STATE_COPY` (default true)
    - `LLM_STATE_MAX_FIELD_CHARS` (default 1000)
    - `LLM_STATE_TRUNCATE_FIELDS` (default: raw/scraped/pre/post filter fields)
- **Env overrides**: Ensure .env does not silently override sane Python defaults in ways that break flows—document expected envs in README or `.env.example`.

## Logging & State Management
- **Never mutate pipeline artifacts**: Keep full fidelity state for reproducibility.
- **Dual-output logs** (`src/research_logger.py`):
  - Full JSON is the source of truth.
  - A truncated sibling `.llm.json` is auto-generated for LLM/debug consumption.
  - Truncation is a safe recursive deep copy that only caps configured string fields.
- **Paths differ between test vs pipeline**:
  - Pipeline default `log_dir`: `src/logs/state/`.
  - Simple test uses `logs/` in project root.

## Pydantic v2 Nuances
- **HttpUrl inputs**: Pass plain strings; let Pydantic validate. Constructing `HttpUrl("...")` objects and supplying them can fail validation.
- **JSON serialization**: When logging models, use `model_dump()` and a custom JSONEncoder to handle `datetime` and Pydantic types.
- **Literal types**: Respect `Literal[...]` constraints (e.g., `report_style` must be one of the allowed values like `summary`).

## Research Pipeline Semantics (Quote Retention)
- **Keep both `raw_content` and `scraped_content`**:
  - `raw_content`: as-fetched payload (HTML/transcript/PDF-to-text). Audit trail.
  - `scraped_content`: main text extracted from raw_content. Downstream basis.
  - They may be similar for text-first APIs; still preserve both for diagnostics and quote retention.
- **Processing flow (ordered snapshots)**: discovery → fetch/scrape → raw capture → extraction → cleaning → filtering → quality scoring. Length fields map to each snapshot.

## LLM Classifier & Research Enhancements
- **Domain classifier**: LLM-based (Nano model) with in-memory caching and heuristic fallback. Controlled by `DOMAIN_CLASSIFIER_MODE`.
- **Centralized query expansion**: Research agents use a shared LLM-driven sub-question generator; improved sub-question quality and consistency.
- **Timezone-aware prompts**: All agents reference `TIMEZONE` for current date/time, improving temporal accuracy.

## Tavily Integration Best Practices
- **Async client**: Use reusable `AsyncTavilyClient`.
- **Rate limiting**: Configurable RPS (default 5) to avoid throttling.
- **Search params**: `time_range`, `advanced` depth, min_score heuristics; include raw content; relevance filtering.
- **Timeouts & errors**: Per-search timeout (~30s) and comprehensive error logging.
- **Domain filtering**: Exclude low-quality domains by default.

## Testing & Debugging
- **Prefer isolated tests**: e.g., `test_logger_only.py` to validate logging/truncation without external APIs.
- **Async correctness**: Ensure coroutines are awaited (fixed a prior bug in `get_enhanced_domain_context`).
- **Streaming patterns**: For Streamlit/CLI streaming, use robust async generator patterns with careful cancellation handling.
- **Logfire**: When enabled, ensure proper setup and verify traces; see `fixinglogfiretraces.md` for troubleshooting.

## Operational Tips
- **Consistent file locations**: Be clear about output directories; mismatch between expected and actual paths causes confusion when verifying artifacts.
- **Small, reversible changes**: Make incremental edits; verify with short runs; read logs early.
- **Documentation first**: Update `currentstatus.md` when making architectural or logging changes so the next session spins up fast.

---

If you are a future assistant: read `currentstatus.md` first, then this file and `CLAUDE.md`. Confirm config flags and log paths, run the logger-only test, and only then attempt full pipeline runs.
