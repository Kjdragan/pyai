# PRD — Streamlit NL→SQL Module for Logfire Querying and Tracing

## 1) Overview
A plug-and-play Streamlit tab that enables Natural Language → SQL (via an LLM) and executes the generated SQL against Logfire's Query API to retrieve trace/log data from `records` (and optionally `metrics`). The module visualizes results, supports basic trace drill‑down, and integrates with existing projects without duplicating Logfire UI functionality.

## 2) Goals and Non‑Goals
- Goals
  - Provide a Streamlit tab/module embeddable in existing apps.
  - Accept NL input, generate SQL using an LLM, and run it via Logfire Query API.
  - Visualize tabular results; offer JSON cell inspection and basic charts.
  - Provide quick trace drill‑down (view span/log details by `trace_id`/`span_id`).
  - Support time-window filters, row limits, and saved queries.
  - Securely manage auth tokens; configurable endpoints and LLM provider.
- Non‑Goals
  - Recreate the full Logfire UI (Live View/Explore) or its proprietary NL→SQL UI logic.
  - Provide an external NL→SQL API; we bring our own LLM inside Streamlit.

## 3) Users and Key Use Cases
- Users: Data engineers, platform teams, developers wanting quick NL queries of Logfire data in their app context.
- Use Cases
  - NL prompt → SQL → table view for debugging and analytics.
  - Tweak/modify SQL iteratively with LLM assistance.
  - Save/share queries; export results.
  - Drill into trace/span details from query results.

## 4) Architecture & Data Flow
1. User enters NL prompt in the Streamlit tab.
2. Module passes prompt + schema/context to an LLM to generate SQL (or modify existing SQL).
3. Module executes SQL against Logfire Query API `/v1/query` with read token.
4. Results return as JSON/Arrow/CSV, converted to DataFrame for display.
5. User can inspect JSON cells, toggle chart view, and drill trace details.

## 5) Functional Requirements
- NL→SQL Generation
  - Use configurable LLM provider/model (e.g., OpenAI, Anthropic, local) via environment/config.
  - Include schema/context in prompt (allowed tables, key columns, JSON fields patterns).
  - Enforce guardrails: use only supported tables/functions; add time window and row limit by default.
  - Support two actions: Generate new SQL; Modify existing SQL.
- SQL Execution
  - Execute read-only SQL via Logfire Query API.
  - Default time filter: last 24h (configurable) and `LIMIT` (e.g., 1000 rows configurable).
  - Toggle response format (JSON default; Arrow for performance; CSV for export).
- Results Visualization
  - Paginated table view; JSON cell popover; column pinning; sorting.
  - Basic charting (line/bar) for simple aggregations.
  - Export: CSV/JSON download.
- Trace Drill‑down
  - If rows contain `trace_id`/`span_id`, provide action to fetch minimal details via a follow-up query (template-based) and present a right panel with attributes/timing.
- Saved Queries & History
  - Local persistence (e.g., file-based JSON in project) for saved queries by name.
  - Session history of prompts/SQL runs.
- Configuration UI
  - Controls for time range, limit, format, and LLM temperature.
  - Toggle to show/hide generated SQL and prompts for transparency.

## 6) Non‑Functional Requirements
- Security
  - Read token stored via env var; never logged; avoid exposing in UI.
  - Sanitize prompts/inputs; disallow DDL/DML.
- Performance & Reliability
  - Timeouts and retries for Query API calls.
  - Backoff on LLM failures; cache recent NL→SQL generations (TTL).
  - Arrow format option for large result sets.
- Observability
  - Optional Logfire SDK instrumentation of the module (spans around NL→SQL and query execution).

## 7) Configuration
- Environment Variables
  - `LOGFIRE_API_BASE` (default `https://logfire-api.pydantic.dev`)
  - `LOGFIRE_READ_TOKEN` (required)
  - `LOGFIRE_DEFAULT_TIME_RANGE` (e.g., `24h`)
  - `LOGFIRE_DEFAULT_ROW_LIMIT` (e.g., `1000`)
  - `LLM_PROVIDER` (e.g., `openai`), `LLM_MODEL` (e.g., `gpt-4o-mini`), provider-specific keys (e.g., `OPENAI_API_KEY`)
- Streamlit Config
  - Enable/disable charts, JSON inspector, saved queries path.

## 8) Prompting Strategy (LLM)
- System instruction with constraints:
  - Only query tables: `records` (and `metrics` if enabled).
  - Include a time filter and `LIMIT`.
  - Prefer JSON extraction operators (`attributes->>...`) for structured fields.
  - Never attempt DDL/DML; only SELECTs.
- Schema/context injection:
  - Known columns: `timestamp`, `service_name`, `span_name`, `trace_id`, `span_id`, `attributes` (JSON), `tags` (array), etc.
  - Examples (few-shot) for top-N, error rate, latency percentiles, time buckets.
- Output formatting:
  - Return SQL only in a code block; no prose.

## 9) Components (Proposed Structure)
- `streamlit_tab_nl_sql.py`
  - `render_nl_sql_tab(st.session_state, config)` — main entry for plug-and-play.
- `nl_to_sql.py`
  - `generate_sql(prompt, schema_ctx, mode="new|modify", llm_config) -> str`
- `logfire_client.py`
  - `query(sql, fmt="json", limit=None, min_ts=None, max_ts=None) -> pd.DataFrame`
  - Handles auth, retries, timeouts, Arrow/CSV decoding.
- `schema_context.py`
  - `build_schema_context()` — attempt introspection; fallback to heuristics/examples.
- `saved_queries.py`
  - `save_query(name, prompt, sql)` / `load_queries()`

## 10) Trace Drill‑Down Design
- If `trace_id` present:
  - Provide a button per row: "View Trace Details".
  - Issue a follow-up parameterized SELECT to fetch spans/logs for that `trace_id` with a small limit.
  - Display a side panel with span tree (basic), attributes, duration.

## 11) Error Handling & Guardrails
- LLM errors: show user-friendly error with retry option; fallback templates offered.
- Query errors (syntax/runtime): capture message, render helpful hints; allow user to edit SQL and retry.
- Safety: refuse to run non-SELECT; enforce max limits; truncate overly large payloads in UI.

## 12) Testing Plan
- Unit tests: NL→SQL prompt builder, SQL sanitizer, client param handling.
- Integration tests: Execute canned SQL against a test Logfire workspace (or stub server).
- UI tests: Streamlit widget interactions, saved queries flow.
- Performance tests: Arrow decoding on large responses; pagination rendering.

## 13) Delivery Plan & Milestones
- M1: Skeleton module (UI scaffold, config, client with mock)
- M2: LLM integration + prompt strategy + schema context
- M3: Query execution + results rendering + drill‑down
- M4: Saved queries, exports, perf polish, docs

## 14) Acceptance Criteria
- NL input generates valid, constrained SQL for typical queries.
- Executed SQL returns results rendered in table with JSON inspection.
- Trace drill‑down works when `trace_id` is present.
- Configurable via env; secrets not leaked in logs/UI.
- Module is importable and callable as a Streamlit tab with minimal setup.

## 15) Dev Notes
- Use `python3` in scripts/shebangs in Linux/WSL environments.
- Prefer async where feasible (LLM + query), but keep Streamlit simplicity; can use threads for non-blocking.
- Keep provider abstraction for LLM to swap models easily.
