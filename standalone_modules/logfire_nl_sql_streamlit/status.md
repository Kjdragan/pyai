# Logfire NL→SQL Streamlit – Project Status

As of: 2025-08-09 14:13:54 -05:00

## Overview
A standalone, embeddable Streamlit tab that converts natural language into SQL (via an optional LLM) and executes the SQL against Logfire’s Query API. The module is designed to be plug‑and‑play, with isolated configuration, robust diagnostics, and safe defaults.

## Architecture Snapshot
Directory: `standalone_modules/logfire_nl_sql_streamlit/`

- `examples/app.py` – Minimal Streamlit app to run the tab standalone.
- `lf_nl_sql/`
  - `streamlit_tab.py` – UI entrypoint: `render_nl_sql_tab()`.
  - `logfire_client.py` – `LogfireQueryClient` for `/v1/query` (httpx, retries, Accept negotiation).
  - `config.py` – Module‑scoped env loading and diagnostics (supports `LF_NL_SQL_ENV_FILE`).
  - `nl_to_sql.py` – LLM adapter + prompt builder; safe fallback SQL if no LLM configured.
  - `schema_context.py` – Schema summary + few‑shot examples for the LLM.
  - `sql_safety.py` – `ensure_safe_select()` guard (single read‑only SELECT).
  - `saved_queries.py` – File‑backed save/load.
  - `logging_setup.py` – Rotating logs at `logs/app.log`.
  - `__init__.py` – Package exports.
- `logs/app.log` – Rotating file logs.
- `.env` / `.env.example` – Module‑specific env; isolated from project env.

Key data model note: The records table exposes `start_timestamp` and `end_timestamp`. There is no `timestamp` column.

## Recent Changes
- Auth & Token Override
  - Added secure, session‑only override field in the “Connection” expander.
  - Normalizes pasted tokens (strips leading `Bearer ` if present).
  - Persists override across Streamlit reruns; includes a Clear button.
  - Displays a masked token fingerprint for diagnostics (never logs token in full).
- Configuration & Diagnostics
  - Module‑scoped `.env` loading with precedence over process env.
  - UI displays the loaded env file path; logs record the source.
- Logging
  - Rotating file logs at `logs/app.log` with request timing and error bodies (truncated), plus masked token fingerprint from client init.
- NL→SQL and SQL Defaults
  - Updated `schema_context.py` to document `start_timestamp`/`end_timestamp` and removed references to `timestamp`.
  - Updated `nl_to_sql.py` prompt to emphasize no `timestamp` column; added safer fallback SQL using `start_timestamp`.
  - Updated `streamlit_tab.py` default SQL and trace drill‑down query to use `start_timestamp`/`end_timestamp`.

## Current Status
- Authentication: Previous 401 errors are resolved when using a valid token via the override.
- Invalid column issue: 400 errors caused by references to a nonexistent `timestamp` column have been addressed in code and prompt. Verification by running a query in the updated UI is recommended to confirm resolution in your environment.

## How to Verify
1. Ensure `.env` (or `LF_NL_SQL_ENV_FILE`) is set; or use the in‑app token override.
2. Run:
   ```bash
   uv pip install -r requirements.txt
   streamlit run examples/app.py
   ```
3. Open “Connection” expander, paste a valid read token if needed (fingerprint should appear).
4. Generate SQL from a natural language prompt (or use the default).
5. Run the query. Expect no references to `timestamp`; ordering should use `start_timestamp`.
6. If an error occurs, check `logs/app.log` for the response body and share the SQL and log line.

## Open TODOs / Next Steps
- SQL Guardrails
  - Optional sanitizer pass to rewrite accidental `timestamp` → `start_timestamp` and remove duplicate time predicates.
  - Expand `ensure_safe_select()` checks and add unit tests.
- UX Enhancements
  - “Test Connection” button to probe auth and display masked fingerprint/API base.
  - Improved trace drill‑down (parent/child grouping, expandable tree, sorting by start/end).
  - Pagination/infinite scroll for large result sets.
  - Persisted UI preferences (time range, format, row limit).
- LLM & Prompting
  - Add provider adapters beyond OpenAI and a provider‑agnostic config block.
  - Few‑shot library and domain‑specific schema hints per workspace.
- Data & Formats
  - First‑class Arrow/Parquet export and larger‑than‑memory handling.
  - Metrics table support and example queries.
- Quality & Ops
  - Tests for `config.py`, `logfire_client.py`, `nl_to_sql.py`, and `sql_safety.py`.
  - CI (lint, type checks, unit tests) and pre‑commit hooks.
  - Security review for logs (PII scrubbing) and dependency pinning.

## Quickstart (WSL/Linux)
- Always use `python3` when running Python.
- Example:
  ```bash
  uv pip install -r requirements.txt
  streamlit run examples/app.py
  ```

## Notes
- If `LLM_PROVIDER=openai` is set, a small, cost‑effective model like `gpt-4o-mini` is a good default; set `OPENAI_API_KEY` accordingly.
- The app supplies time bounds in requests; you can omit explicit time predicates in generated SQL unless needed.
