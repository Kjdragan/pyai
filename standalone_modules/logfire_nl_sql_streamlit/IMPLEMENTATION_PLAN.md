# Implementation Plan — Logfire NL→SQL Streamlit Module (Standalone)

## Objectives
- Build a standalone, plug-and-play module that can later be integrated into the main project.
- Provide NL→SQL via pluggable LLM, execute against Logfire Query API, visualize results, and support basic trace drill‑down.
- Emphasize safety (read-only), configurability, and testability without requiring live external calls.

## Milestones
1. M1: Core scaffolding (DONE)
   - Package `lf_nl_sql` with `render_nl_sql_tab()`, `LogfireQueryClient`, LLM adapter, schema context, saved queries helper, example app.
   - README, requirements, .env.example.
2. M2: Safety & Guardrails (THIS STEP)
   - Add SQL safety checks (allow SELECT only; block DDL/DML).
   - Add input sanitization helpers.
   - Wire safety into Streamlit UI before execution.
3. M3: UX polish & features
   - JSON cell inspector; optional charts (basic aggregations).
   - Toggle to show prompts/SQL for transparency.
   - Better trace drill‑down templating and small tree view.
4. M4: Config & Perf
   - Arrow format optimization; pagination and column toggles.
   - Caching for LLM generations (TTL).
5. M5: Testing & Docs
   - Add offline quick checks (no network).
   - Add integration test stub (skipped without token).
   - Expand README with integration guidance.

## Module Structure
- `lf_nl_sql/streamlit_tab.py`: UI and user flow.
- `lf_nl_sql/logfire_client.py`: HTTP client for `/v1/query`.
- `lf_nl_sql/nl_to_sql.py`: LLM prompt builder and generation.
- `lf_nl_sql/schema_context.py`: schema and few-shot examples.
- `lf_nl_sql/saved_queries.py`: persistence helpers.
- `lf_nl_sql/sql_safety.py`: safety & sanitization utilities (NEW in M2).
- `examples/app.py`: runnable demo.

## Detailed Tasks — M2 (Safety & Guardrails)
- Add `sql_safety.ensure_safe_select(sql: str) -> str`:
  - Lowercase check; must start with `select` (ignoring leading whitespace/comments).
  - Reject known risky keywords: `insert`, `update`, `delete`, `drop`, `alter`, `create`, `truncate`.
  - (Optional) Reject multiple statements separated by `;` unless only one and trailing semicolon.
- Call `ensure_safe_select()` in `render_nl_sql_tab()` before executing a query.
- Add `tests/run_quick_checks.py` to validate `ensure_safe_select()` and prompt assembly without network.

## Out of Scope (for now)
- Project-wide integration; wiring into the main app (to be done separately).
- Advanced visualization (span trees, flamegraphs) beyond basic drill‑down.
- Full schema introspection from Logfire.

## Acceptance for M2
- Disallowed SQL raises a clear error in the UI.
- Quick checks run locally and pass without network.
