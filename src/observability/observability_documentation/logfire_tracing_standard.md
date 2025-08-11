# Logfire Tracing & Tagging Standard for Pydantic‑AI Agents

Purpose: Define a simple, repeatable, and universal approach to tracing and tagging across PyAI/Pydantic‑AI projects for clear attribution by project, process, agent/sub‑agent, and LLM usage—without over‑engineering.


## Goals
- Simple, repeatable setup across projects
- High‑level observability first; avoid excessive granularity
- Accurate LLM cost/usage accounting without double counting
- Easy per‑agent/per‑process breakdowns via stable tags/attributes
- Works with async tasks, thread/process pools, and multi‑service deployments


## Core Concepts
- Use Logfire as the OpenTelemetry backend for spans/logs/metrics.
- Store business identifiers and stable categories in:
  - tags (array of strings) for coarse filtering/grouping
  - attributes (JSON) for structured metadata and SQL analytics
- Put token usage only on LLM leaf spans using OpenTelemetry GenAI attributes.
- Propagate context across async threads/processes to maintain parent→child.


## Baseline Configuration (Global)
- Configure once per service/process:
  - service_name: project/service identifier (e.g., "pyai-reporter")
  - environment: maps to otel resource `deployment.environment.name` (dev/staging/prod)
  - service_version: git SHA or semantic version

Recommended defaults:
- Tags on root or session spans: `project:pyai`, `app:agents`, `env:{dev|staging|prod}`
- Attributes on root/session spans:
  - `pyai.run.id` – UUID for the end‑to‑end run
  - `pyai.request.id` – per request/session ID
  - Note: Identica default disables user tracking; omit `pyai.user.id` unless explicitly required


## Span Taxonomy (Low‑Cardinality Names)
Use low‑cardinality span_name for efficient filtering; use `message` for specific details.
- Orchestration
  - span_name: `orchestration run`
  - message: `orchestrator run`
- Agent Execution
  - span_name: `agent run`
  - message: `{agent_name} run` (e.g., `generation_agent run`)
- Tool Execution
  - span_name: `tool run`
  - message: `{tool_name}` (e.g., `perform_serper_research`)
- LLM Call (leaf)
  - span_name: `chat {model}` (e.g., `chat gpt-4o-mini`)
  - message: `chat {model}`
  - Attributes: set GenAI usage (below)

Tip: When you need distinct name vs. message, use `_span_name` (Logfire supports overriding span name while using a detailed message template).


## Tagging Standard (Coarse, Repeatable)
Use tags for high‑level grouping; keep a small, stable set:
- `project:pyai`
- `env:{dev|staging|prod}`
- `agent:{name}` (e.g., `agent:orchestrator`, `agent:generation`)
- `process:{stage}` (e.g., `process:research`, `process:reporting`)
- `pipeline:{name}` (optional)

Notes:
- Tags are searchable via `array_has(tags, 'agent:generation')`.
- Apply tags consistently at the agent span and inherit to children when possible.


## Attribute Standard (Structured, Analyzable)
Prefix with `pyai.` to avoid collisions and aid discovery:
- Run/Session
  - `pyai.run.id` (UUID)
  - `pyai.request.id`
- Agent Hierarchy
  - `pyai.agent.name` (e.g., `generation_agent`)
  - `pyai.agent.role` (e.g., `writer`, `researcher`) – optional
  - `pyai.agent.depth` (0=root, 1=child, …) – optional
  - `pyai.agent.parent` (parent agent name) – optional
- Process / Pipeline
  - `pyai.process.name` (e.g., `report_generation`)
  - `pyai.process.step` (e.g., `query_expansion`) – optional
- Tooling
  - Prefer OpenTelemetry GenAI tool attributes when invoked by LLM (see below)
  - Otherwise: `pyai.tool.name`, `pyai.tool.args`, `pyai.tool.result`

Keep attribute values low‑cardinality and string/number where possible.


## LLM Usage (Leaf Spans Only)
Use OpenTelemetry GenAI attributes on leaf LLM spans (do not duplicate on parents):
- `gen_ai.system` – e.g., `openai`
- `gen_ai.request.model` – requested model
- `gen_ai.response.model` – actual model (if different)
- `gen_ai.usage.input_tokens` – int64
- `gen_ai.usage.output_tokens` – int64
- Optional: `gen_ai.usage.total_tokens`, `gen_ai.usage.total_cost`
- Tool calls from LLM:
  - `gen_ai.tool.name`, `gen_ai.tool.arguments`, `gen_ai.tool.response`

Rationale: Deduplication—limit token usage to model‑labeled leaf spans so vendor cost queries don’t double count.


## Context Propagation & Concurrency
- Let OpenTelemetry auto‑propagate in instrumented libs (HTTP clients/servers, etc.).
- For manual propagation across threads/processes: use `logfire.propagate.get_context()` and `attach_context()`.
- Logfire also patches `ThreadPoolExecutor`/`ProcessPoolExecutor` for context propagation.


## Do / Don’t Rules
- Do: put token usage only on LLM leaf spans (model present)
- Do: set `pyai.agent.name` on every agent span; add `agent:{name}` tag
- Do: generate a `pyai.run.id` once per orchestration run and attach to root
- Do: keep span names low‑cardinality, messages descriptive
- Don’t: copy token usage to parent agent spans
- Don’t: emit high‑cardinality span names (e.g., include IDs in names)


## Query Recipes (SQL)
- Last run by root span, then total tokens (leaf LLM spans only):
```sql
-- find most recent root span
SELECT trace_id
FROM records
WHERE kind='span' AND parent_span_id IS NULL
ORDER BY end_timestamp DESC
LIMIT 1;

-- deduped LLM usage by agent
WITH llm AS (
  SELECT span_id, parent_span_id, trace_id,
         attributes->>'gen_ai.request.model' AS model,
         CAST(attributes->>'gen_ai.usage.input_tokens' AS BIGINT) AS in_t,
         CAST(attributes->>'gen_ai.usage.output_tokens' AS BIGINT) AS out_t
  FROM records
  WHERE trace_id = $trace_id AND model IS NOT NULL
), parents AS (
  SELECT span_id, parent_span_id, message
  FROM records WHERE trace_id = $trace_id
), attrib AS (
  SELECT llm.span_id, llm.model, llm.in_t, llm.out_t,
         p1.message AS parent_msg, p2.message AS grandparent_msg
  FROM llm
  LEFT JOIN parents p1 ON p1.span_id = llm.parent_span_id
  LEFT JOIN parents p2 ON p2.span_id = p1.parent_span_id
)
SELECT COALESCE(
         CASE WHEN lower(parent_msg) LIKE '%agent run' OR lower(parent_msg) LIKE '%classifier run' THEN parent_msg END,
         CASE WHEN lower(grandparent_msg) LIKE '%agent run' OR lower(grandparent_msg) LIKE '%classifier run' THEN grandparent_msg END,
         'unknown'
       ) AS agent_label,
       COUNT(*) AS llm_calls,
       SUM(in_t) AS in_tokens,
       SUM(out_t) AS out_tokens,
       SUM(in_t + out_t) AS total_tokens
FROM attrib
GROUP BY agent_label
ORDER BY total_tokens DESC;
```

- Tokens by tag (e.g., `agent:generation`):
```sql
SELECT COALESCE(SUM(CAST(attributes->>'gen_ai.usage.input_tokens' AS BIGINT)),0) AS in_tokens,
       COALESCE(SUM(CAST(attributes->>'gen_ai.usage.output_tokens' AS BIGINT)),0) AS out_tokens
FROM records
WHERE attributes->>'gen_ai.request.model' IS NOT NULL
  AND array_has(tags, 'agent:generation');
```

- Project / environment filter:
```sql
SELECT count(*)
FROM records
WHERE service_name='pyai-reporter'
  AND deployment_environment='prod';
```


## Adoption Checklist
0) Create/import the observability shim module and configure defaults
1) Global configure: `service_name`, `environment`, `service_version`
2) Generate and attach `pyai.run.id` at root
3) Adopt span taxonomy (orchestration / agent / tool / LLM)
4) Add tags: `project:pyai`, `env:*`, `agent:*`, `process:*`
5) Add attributes: `pyai.*` keys (agent/process/run)
6) Ensure LLM spans set GenAI attributes; remove usage from parents
7) Verify context propagation in async, threads, and processes
8) Decide prompt/response preview settings (inline_sample, preview_limit); optionally enable eval context
9) Add saved SQL snippets to your Logfire workspace


## Future Enhancements
- Emit `gen_ai.client.token.usage` metrics if available for aggregated dashboards
- Standardize `pyai.cost.usd` if you compute costs
- Add `pyai.dataset.id` or `pyai.customer.id` when relevant


## References
- Logfire GenAI attributes: `gen_ai.*` (LLM panels)
- Set attributes on active span: `span.set_attribute(key, value)`
- Context propagation: `logfire.propagate.get_context()` / `attach_context()`
- Environments: `deployment.environment.name` via `logfire.configure(environment=...)`
- Tags: `tags` array (query with `array_has(tags, 'tag')`)


## Shim API (Modular, Reusable)
A thin helper you can reuse across projects to standardize span taxonomy, tags/attributes, GenAI usage placement, and prompt/response previews—without changing architecture.

- Purpose: Consistency, DRY config, dynamic agent/process discovery, and correctness for LLM leaf usage.
- Configure once: `service_name`, `environment`, `service_version`, `inline_sample` (default 1.0), `preview_limit` (default 2048 bytes).
- Surface (illustrative):
  - `configure_observability(...)`
  - `start_orchestration(run_id=None, tags=None, attrs=None)`
  - `agent_span(obj_or_name, extra_tags=None, extra_attrs=None)`
  - `@trace_process(name=None)` → defaults to function name
  - `llm_span(model, system='openai', usage=None)`
  - `record_prompt_response(prompt, response, template_id=None, version=None, blob_url=None)`
  - `set_eval_context(run_id=None, suite=None, case_id=None, metric_name=None, metric_value=None)`

Example usage:
```python
with start_orchestration() as run:
    with agent_span(self):
        @trace_process()
        def step():
            with llm_span(model="gpt-4o-mini", system="openai"):
                record_prompt_response(prompt, response, template_id="sum-v1", version="1.2")
```


## Auto‑discovery Strategy
- Agent name: infer from class (`obj.__class__.__name__`) or function/module name; normalize to kebab/snake case for `pyai.agent.name` and `agent:{name}` tag.
- Process name: `@trace_process(name=None)` uses function name when not provided; adds `pyai.process.name` and `process:{name}`.
- Fallback: if neither is available, use module/function basename; allow explicit override via parameters.


## Evaluation Defaults
- Inline previews (on by default):
  - `pyai.prompt.preview`, `pyai.response.preview` (truncated to `preview_limit`, default 2048)
  - Flags: `pyai.prompt.truncated`, `pyai.response.truncated`
- Optional links for full bodies: `pyai.prompt.blob_url`, `pyai.response.blob_url`
- Optional eval context (enable during evals):
  - `pyai.eval.run.id`, `pyai.eval.suite`, `pyai.eval.case.id`
  - `pyai.eval.metric.name`, `pyai.eval.metric.value`
- Sampling knob: `inline_sample` (0.0–1.0); Identica default 1.0
- No user tracking by default; exclude `pyai.user.id` unless explicitly required


## Dashboards (Debugging & Optimization)
- Run & Breakage Finder:
  - Errors by agent/process (recent runs), recent exceptions, long‑running spans (p95) by agent/process
- LLM Review & Prompt Improvements:
  - Recent LLM calls with model, latency, tokens, inline previews/links; filter by agent/process/model/template
- Optimization Opportunities:
  - Token hotspots by agent/process/model, output/input ratio outliers, tool‑call error rates
- Optional: emit `gen_ai.client.token.usage` metric for dashboard performance (not required)


## Modularization & Reuse
- Keep the shim in a small module (e.g., `observability/shim.py`) with zero project‑specific imports.
- Expose only the stable surface above; avoid leaking internal project types.
- Configure via environment or a tiny settings object so projects can adopt it without code changes.
- Document defaults in this file; projects can override via config without altering the shim code.
