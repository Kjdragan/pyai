# Observability Shim API (Design Reference)

Purpose: A tiny, reusable helper layer over Logfire/OpenTelemetry to standardize tracing across Identica Pydantic‑AI projects—without changing architecture.

Use with the standard in: `src/Project Documentation/logfire_tracing_standard.md`.


## Configuration

```python
configure_observability(
    service_name: str,
    environment: str,           # dev|staging|prod (sets deployment.environment.name)
    service_version: str,       # git SHA or semver
    inline_sample: float = 1.0, # 0.0–1.0 for prompt/response preview sampling
    preview_limit: int = 2048,  # bytes to keep inline for previews
)
```

- Applies Logfire global config.
- Stores shim defaults (sampling, preview size) used by helpers below.


## Orchestration

```python
start_orchestration(
    run_id: str | None = None,  # auto-generated UUID if None
    tags: list[str] | None = None,
    attrs: dict | None = None,
) -> ContextManager
```

- Creates a root/span for an end‑to‑end run.
- Sets tags: `project:*`, `env:*` (derived), optional extras.
- Sets attributes: `pyai.run.id` (required), optional extras.


## Agents

```python
agent_span(
    obj_or_name: Any,           # class instance, function, or explicit name
    extra_tags: list[str] | None = None,
    extra_attrs: dict | None = None,
) -> ContextManager
```

- Infers `pyai.agent.name` from class/function/module if not provided.
- Adds `agent:{name}` tag.


## Processes/Stages

```python
@trace_process(name: str | None = None)
```

- Wraps any function as a process stage.
- Uses function name when `name` is not provided.
- Sets `pyai.process.name` and `process:{name}`.


## LLM Calls (leaf spans)

```python
llm_span(
    model: str,
    system: str = "openai",
    usage: dict | None = None,  # {"input_tokens": int, "output_tokens": int}
) -> ContextManager
```

- Creates a leaf LLM span; sets low‑cardinality name (e.g., `chat gpt-4o-mini`).
- Sets GenAI attributes on the active span:
  - `gen_ai.system`, `gen_ai.request.model`
  - If provided via `usage` (or caller sets manually):
    - `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- Rule: Do not copy usage to parents (prevents double counting).


## Prompt/Response Previews (optional)

```python
record_prompt_response(
    prompt: str | dict,
    response: str | dict,
    template_id: str | None = None,
    version: str | None = None,
    blob_url: str | None = None,
) -> None
```

- Stores inline previews on the active span:
  - `pyai.prompt.preview`, `pyai.response.preview` (truncated by `preview_limit`)
  - Flags: `pyai.prompt.truncated`, `pyai.response.truncated`
  - Optional links: `pyai.prompt.blob_url`, `pyai.response.blob_url`
- Sampling: controlled by `inline_sample`.


## Evaluation Context (optional)

```python
set_eval_context(
    run_id: str | None = None,
    suite: str | None = None,
    case_id: str | None = None,
    metric_name: str | None = None,
    metric_value: float | None = None,
) -> None
```

- Sets minimal eval metadata on the active span when running tests/evaluations.


## Auto‑discovery Details

- Agent name inference order:
  1) explicit name
  2) `obj.__class__.__name__`
  3) function name
  4) module basename
- Normalization: convert to `snake_case` for `pyai.agent.name`; tags use `agent:{name}`.
- Process name: decorator defaults to function name.


## Minimal Example

```python
configure_observability("pyai-reporter", environment="dev", service_version="0.1.0")

with start_orchestration() as run:
    with agent_span(self):
        @trace_process()
        def step(q):
            with llm_span(model="gpt-4o-mini") as s:
                # Call your LLM and then attach usage and previews
                # s.set_attribute("gen_ai.usage.input_tokens", in_t)
                # s.set_attribute("gen_ai.usage.output_tokens", out_t)
                record_prompt_response(prompt, response, template_id="sum-v1", version="1.2")
        step("solar storms this week")
```


## Notes

- No user tracking by default (omit `pyai.user.id`).
- LLM token usage belongs only on the model leaf span.
- For distributed/async contexts, rely on Logfire propagation or use `attach_context/get_context`.
