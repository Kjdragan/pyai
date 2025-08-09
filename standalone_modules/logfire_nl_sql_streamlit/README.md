# Logfire NL→SQL Streamlit Module (Standalone)

A plug‑and‑play Streamlit tab that converts natural language to SQL (via an LLM you configure) and executes the SQL against Logfire's Query API. Displays results in a table with JSON inspection and basic trace drill‑down.

## Features
- NL→SQL generation via pluggable LLM (optional; manual SQL editing supported)
- Query execution against Logfire `/v1/query`
- CSV/JSON/Arrow response handling (CSV default for robustness)
- Time range and row limit controls
- Saved queries and session history
- Basic trace drill‑down by `trace_id`

## Quickstart
1. Create a `.env` based on `.env.example` and set:
   - `LOGFIRE_READ_TOKEN` (required)
   - Optional LLM config (e.g., `OPENAI_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`)
2. Install deps (example with uv):
   ```bash
   uv pip install streamlit httpx pandas pyarrow python-dotenv tenacity
   ```
3. Run the example app:
   ```bash
   streamlit run examples/app.py
   ```

## Environment Variables
- `LOGFIRE_API_BASE` (default `https://logfire-api.pydantic.dev`)
- `LOGFIRE_READ_TOKEN` (required)
- `LOGFIRE_DEFAULT_TIME_RANGE` (e.g., `24h`)
- `LOGFIRE_DEFAULT_ROW_LIMIT` (e.g., `1000`)
- `ACCEPT_FORMAT` (`csv`|`json`|`arrow`, default `csv`)
- `LLM_PROVIDER` (`openai`|`none`, default `none`)
- `LLM_MODEL` (e.g., `gpt-4o-mini`)
- `OPENAI_API_KEY` (if provider is `openai`)
- `SAVED_QUERIES_PATH` (default `saved_queries.json`)

## Design
- Package: `lf_nl_sql`
  - `render_nl_sql_tab()` for easy embedding
  - `LogfireQueryClient` (httpx)
  - `generate_sql()` LLM adapter with safe fallback

## Notes
- External NL→SQL API is not provided by Logfire; this module brings its own LLM.
- Use `python3` in Linux/WSL.
