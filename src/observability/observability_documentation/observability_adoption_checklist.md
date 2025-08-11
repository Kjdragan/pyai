# Observability Adoption Checklist (Identica / Pydantic‑AI)

Use with:
- Standard: `src/Project Documentation/logfire_tracing_standard.md`
- Shim API reference: `src/Project Documentation/observability_shim_api.md`

Goal: Apply a consistent tracing/tagging pattern across any project, focused on debugging and optimization (not user tracking or production alerts).


## Prerequisites
- Logfire workspace and write token configured in environment (e.g., `LOGFIRE_TOKEN`).
- Decide project identifiers:
  - `service_name` (e.g., `pyai-orchestrator`)
  - `environment` (dev|staging|prod)
  - `service_version` (git SHA or semver)
- Retention policy set in Logfire (ephemeral OK).
- Prompt/response preview defaults:
  - `inline_sample` = 1.0 (start at 100%)
  - `preview_limit` = 2048 bytes


## Step-by-step
1) Configure once at startup
   - Call `configure_observability(service_name, environment, service_version, inline_sample, preview_limit)`.

2) Wrap orchestration entrypoint(s)
   - Use `start_orchestration(run_id=None)` at the beginning of each end‑to‑end run.
   - Ensures `pyai.run.id` is set on the root span.

3) Wrap agent execution
   - Use `agent_span(self|name)` wherever an agent “runs”.
   - Auto‑discovers `pyai.agent.name` when given an instance or function; adds `agent:{name}`.

4) Mark pipeline stages
   - Decorate stage functions with `@trace_process(name=None)`; falls back to function name.
   - Adds `pyai.process.name` and `process:{name}`.

5) LLM leaf spans and usage
   - Wrap model calls with `llm_span(model, system='openai', usage=None)`.
   - Set `gen_ai.*` usage only on these spans (never on parents) to avoid double counting.

6) Prompt/response previews (optional)
   - Call `record_prompt_response(prompt, response, template_id=?, version=?, blob_url=?)`.
   - Stores truncated inline previews and flags; links full bodies when provided.

7) Evaluations (optional)
   - Call `set_eval_context(run_id=?, suite=?, case_id=?, metric_name=?, metric_value=?)` during eval runs.
   - Keep metadata minimal; toggle on only when needed.

8) Save queries & dashboards
   - Save the SQL recipes from the Standard file into Logfire.
   - Create three dashboards: Run & Breakage Finder; LLM Review; Optimization Opportunities.

9) Tune sampling/retention as volume grows
   - Adjust `inline_sample` downward if storage/noise grows.
   - Rely on workspace retention to expire old data.


## Verification checklist
- You see a single root span per run with `pyai.run.id`.
- Agent spans have `pyai.agent.name` and `agent:{name}`.
- Process spans have `pyai.process.name` and `process:{name}`.
- LLM usage appears only on model-labeled leaf spans (`gen_ai.request.model` is not NULL).
- Prompt/response previews appear (with truncated flags) when enabled.
- Errors/exceptions are visible on the relevant spans.


## Notes
- No user tracking by default; omit `pyai.user.id` unless explicitly required.
- Keep span names low‑cardinality; use `message` for specifics.
- Prefer tag/attribute emit-time labeling over post-hoc inference.
