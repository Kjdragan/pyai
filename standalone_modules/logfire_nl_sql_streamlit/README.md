# Logfire NL→SQL Streamlit Module (Standalone)

A plug‑and‑play Streamlit tab that turns natural language questions into SQL (via an optional LLM) and runs the SQL against Logfire’s Query API. It is designed to be self‑contained and embeddable as a tab in other apps, with isolated configuration, robust diagnostics, and safe defaults.

## Features
- NL→SQL generation via pluggable LLM (OpenAI optional; manual SQL editing always supported)
- Query execution against Logfire `/v1/query` with retries and format negotiation
- CSV/JSON/Arrow handling (CSV default for robustness and minimal deps)
- Time range presets and row‑limit control; app supplies min/max timestamps to the API
- Saved queries and quick load/save
- Trace drill‑down by `trace_id`
- Isolated env loading and in‑app secure token override (persistent for the session)
- Rotating file logs and clear diagnostics (env source, API base, masked token fingerprint)

## Quickstart
1. Create a `.env` in this folder (copy `.env.example`) and set:
   - `LOGFIRE_READ_TOKEN` (required Read token from your Logfire workspace)
   - Optional LLM config (e.g., `OPENAI_API_KEY`, `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`)
2. Install deps (uv example or your tool of choice):
   ```bash
   uv pip install -r requirements.txt
   ```
3. Run the example app (Linux/WSL: always use python3):
   ```bash
   streamlit run examples/app.py
   ```
4. In the UI, open the “Connection” expander and, if needed, paste a valid read token. The app will remember it for the current session and show a masked fingerprint.

## Configuration and Env Loading
This module intentionally isolates configuration from the rest of your project:

- The module loads a dedicated `.env` file from this directory. You may override the path with `LF_NL_SQL_ENV_FILE`.
- Values from the module `.env` take precedence over process env variables.
- The UI shows the effective env source path for transparency.

Environment variables:
- `LOGFIRE_API_BASE` (default `https://logfire-api.pydantic.dev`)
- `LOGFIRE_READ_TOKEN` (required if you don’t use the in‑app override)
- `LOGFIRE_DEFAULT_TIME_RANGE` (e.g., `24h`)
- `LOGFIRE_DEFAULT_ROW_LIMIT` (e.g., `1000`)
- `ACCEPT_FORMAT` (`csv`|`json`|`arrow`, default `csv`)
- `LLM_PROVIDER` (`openai`|`none`, default `none`)
- `LLM_MODEL` (e.g., `gpt-4o-mini`)
- `OPENAI_API_KEY` (if provider is `openai`)
- `SAVED_QUERIES_PATH` (default `saved_queries.json`)
- `LF_NL_SQL_ENV_FILE` (optional explicit path to env file for this module)

## Architecture
Directory: `standalone_modules/logfire_nl_sql_streamlit/`

- `examples/app.py` – minimal Streamlit app that mounts the tab (for standalone runs)
- `lf_nl_sql/`
  - `streamlit_tab.py` – `render_nl_sql_tab()` builds the full UI
  - `logfire_client.py` – `LogfireQueryClient` (httpx) for `/v1/query`, retries, Accept negotiation
  - `config.py` – env loading with module isolation and diagnostics
  - `nl_to_sql.py` – LLM adapter and prompt builder; safe fallback SQL
  - `schema_context.py` – concise schema summary and few‑shot examples
  - `sql_safety.py` – `ensure_safe_select()` validation for read‑only, single‑select SQL
  - `saved_queries.py` – file‑backed save/load
  - `logging_setup.py` – rotating file logs under `logs/app.log`
  - `__init__.py` – package export surface
  
Key data model notes:
- Records table exposes `start_timestamp` and `end_timestamp` (there is no `timestamp` column).
- Attributes are stored as JSON; tags are arrays of strings.

## Security & Auth
- Read token is required. The Connection expander lets you override the token securely at runtime.
- The override persists for the session and is never written to disk.
- Pasted tokens are normalized (e.g., a leading `Bearer ` is stripped).
- Logs include a masked token fingerprint (`auth_fp=abcd…wxyz`) but never the token itself.

## Logging & Diagnostics
- Rotating file logs at `logs/app.log` capture:
  - Env source path used for configuration
  - API base, Accept format, and query timing
  - HTTP status codes and (on errors) truncated response bodies
  - Masked token fingerprint during client initialization

## UI Flow
1. Provide natural language prompt and choose “new” or “modify”.
2. Generated SQL appears in the editor; you can edit it freely.
3. Choose time range preset, row limit, and result format.
4. Run the query. The app supplies `min_timestamp`/`max_timestamp` parameters derived from the preset.
5. Inspect results, then optionally drill down by `trace_id`.

## NL→SQL Strategy
- If configured (`LLM_PROVIDER=openai`), OpenAI is used to translate NL→SQL based on `schema_context.py`.
- The prompt emphasizes that there is no `timestamp` column and to use `start_timestamp`/`end_timestamp`.
- If an LLM isn’t configured, a safe fallback SQL template is inserted for manual editing.

## Query Client
- `LogfireQueryClient` sends GET requests to `${LOGFIRE_API_BASE}/v1/query` with `Authorization: Bearer <token>`.
- Retries transient failures (tenacity) and logs timings.
- Parses CSV (default), JSON (list or `{data:[...]}`), or Arrow streams.

## SQL Safety
- `ensure_safe_select()` enforces a single read‑only SELECT (no DDL/DML, no semicolons in sequence, etc.).
- The app also constrains queries with time range parameters sent alongside the SQL.

## Embedding the Tab
You can embed the tab in your own Streamlit app:

```python
import streamlit as st
from lf_nl_sql.streamlit_tab import render_nl_sql_tab

st.set_page_config(page_title="Logfire NL→SQL")
render_nl_sql_tab()  # uses module Settings() by default
```

## Troubleshooting
- 401 Unauthorized: paste a new read token via the Connection expander. The fingerprint will update.
- 400 invalid query: ensure your SQL does not reference a `timestamp` column; use `start_timestamp`/`end_timestamp`.
- No results: verify time range, row limit, and that fields exist in your workspace’s data.

## Notes
- External NL→SQL is not provided by Logfire; this module brings its own LLM integration.
- On Linux/WSL, always use `python3` when running Python.
