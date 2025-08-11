"""
Observability shim for consistent tracing across Pydantic‑AI projects.
Uses OpenTelemetry so it works seamlessly with Logfire instrumentation.
"""
from __future__ import annotations

import json
import os
import random
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, ContextManager, Optional, Callable

try:  # Logfire is optional at import time
    import logfire  # type: ignore
except Exception:  # pragma: no cover
    logfire = None  # type: ignore

try:
    from opentelemetry import trace
    from opentelemetry.trace import Tracer, Span
except Exception:  # pragma: no cover
    trace = None  # type: ignore
    Tracer = Any  # type: ignore
    Span = Any  # type: ignore


# -------------------------------
# Internal settings/state
# -------------------------------
@dataclass
class _Settings:
    service_name: str = "pyai"
    environment: str = os.getenv("ENV", "dev")
    service_version: str = os.getenv("SERVICE_VERSION", "0.0.0")
    inline_sample: float = 1.0
    preview_limit: int = 2048


_SETTINGS = _Settings()


def _get_tracer() -> Tracer:
    if trace is None:
        raise RuntimeError("OpenTelemetry not available; ensure logfire/opentelemetry installed")
    # Use service_name as instrumentation scope
    return trace.get_tracer(_SETTINGS.service_name)


def _snake_case(name: str) -> str:
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).replace(" ", "_").lower()


def _normalize_preview(value: Any) -> str:
    try:
        s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except Exception:
        s = str(value)
    # Truncate to preview_limit bytes (UTF-8 safe-ish)
    data = s.encode("utf-8")
    if len(data) <= _SETTINGS.preview_limit:
        return s
    return data[: _SETTINGS.preview_limit].decode("utf-8", errors="ignore")


# -------------------------------
# Public API
# -------------------------------

def configure_observability(
    service_name: str,
    environment: str,
    service_version: str,
    inline_sample: float = 1.0,
    preview_limit: int = 2048,
) -> None:
    """Configure shim defaults and, if present, align Logfire settings.

    Does not force Logfire reconfiguration if already configured elsewhere.
    """
    _SETTINGS.service_name = service_name or _SETTINGS.service_name
    _SETTINGS.environment = environment or _SETTINGS.environment
    _SETTINGS.service_version = service_version or _SETTINGS.service_version
    _SETTINGS.inline_sample = float(inline_sample)
    _SETTINGS.preview_limit = int(preview_limit)

    # Best effort alignment with Logfire if available; avoid conflicting config
    if logfire is not None:
        try:
            # If another module already configured Logfire, this will be a no-op in practice.
            logfire.configure(  # type: ignore[attr-defined]
                send_to_logfire=True,
                console=False,
                service_name=_SETTINGS.service_name,
            )
            # Ensure common instrumentations are active
            try:
                logfire.instrument_pydantic_ai()  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                logfire.instrument_httpx(capture_all=True)  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            # Never fail init due to telemetry
            pass


@contextmanager
def start_orchestration(
    run_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attrs: Optional[dict[str, Any]] = None,
) -> ContextManager:
    tracer = _get_tracer()
    span_name = "orchestration"
    with tracer.start_as_current_span(span_name) as span:
        base_tags = [
            f"project:{_SETTINGS.service_name}",
            f"env:{_SETTINGS.environment}",
        ]
        if tags:
            base_tags.extend(tags)
        # Attributes
        span.set_attribute("pyai.run.id", run_id or "auto")
        span.set_attribute("pyai.service.name", _SETTINGS.service_name)
        span.set_attribute("pyai.environment", _SETTINGS.environment)
        span.set_attribute("pyai.service.version", _SETTINGS.service_version)
        span.set_attribute("tags", base_tags)
        if attrs:
            for k, v in attrs.items():
                span.set_attribute(k, v)
        yield span


@contextmanager
def agent_span(
    obj_or_name: Any,
    extra_tags: Optional[list[str]] = None,
    extra_attrs: Optional[dict[str, Any]] = None,
) -> ContextManager:
    name = None
    if isinstance(obj_or_name, str):
        name = obj_or_name
    else:
        name = getattr(obj_or_name, "__class__", type(obj_or_name)).__name__
    snake = _snake_case(name)
    tracer = _get_tracer()
    span_name = f"agent {snake}"
    with tracer.start_as_current_span(span_name) as span:
        tags = [f"agent:{snake}"]
        if extra_tags:
            tags.extend(extra_tags)
        span.set_attribute("pyai.agent.name", snake)
        span.set_attribute("tags", tags)
        if extra_attrs:
            for k, v in extra_attrs.items():
                span.set_attribute(k, v)
        yield span


def trace_process(name: Optional[str] = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        import inspect
        proc_name = name or func.__name__
        snake = _snake_case(proc_name)

        if inspect.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                tracer = _get_tracer()
                span_name = f"process {snake}"
                with tracer.start_as_current_span(span_name) as span:
                    span.set_attribute("pyai.process.name", snake)
                    span.set_attribute("tags", [f"process:{snake}"])
                    return await func(*args, **kwargs)
            return async_wrapper  # type: ignore[return-value]
        else:
            def wrapper(*args, **kwargs):
                tracer = _get_tracer()
                span_name = f"process {snake}"
                with tracer.start_as_current_span(span_name) as span:
                    span.set_attribute("pyai.process.name", snake)
                    span.set_attribute("tags", [f"process:{snake}"])
                    return func(*args, **kwargs)
            return wrapper
    return decorator


@contextmanager
def llm_span(
    model: str,
    system: str = "openai",
    usage: Optional[dict[str, int]] = None,
) -> ContextManager:
    tracer = _get_tracer()
    span_name = f"chat {model}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("gen_ai.system", system)
        span.set_attribute("gen_ai.request.model", model)
        if usage:
            if "input_tokens" in usage:
                span.set_attribute("gen_ai.usage.input_tokens", int(usage["input_tokens"]))
            if "output_tokens" in usage:
                span.set_attribute("gen_ai.usage.output_tokens", int(usage["output_tokens"]))
        yield span


def record_prompt_response(
    prompt: Any,
    response: Any,
    template_id: Optional[str] = None,
    version: Optional[str] = None,
    blob_url: Optional[str] = None,
) -> None:
    """Attach inline prompt/response previews to the current span with sampling.
    Safe no-op if no active span exists.
    """
    if trace is None:
        return
    if _SETTINGS.inline_sample < 1.0 and random.random() > _SETTINGS.inline_sample:
        return
    span: Span = trace.get_current_span()
    if span is None:
        return
    prompt_preview = _normalize_preview(prompt)
    response_preview = _normalize_preview(response)
    span.set_attribute("pyai.prompt.preview", prompt_preview)
    span.set_attribute("pyai.response.preview", response_preview)
    span.set_attribute("pyai.prompt.truncated", int(len(json.dumps(prompt, default=str).encode("utf-8")) > _SETTINGS.preview_limit))
    span.set_attribute("pyai.response.truncated", int(len(json.dumps(response, default=str).encode("utf-8")) > _SETTINGS.preview_limit))
    if template_id:
        span.set_attribute("pyai.prompt.template_id", template_id)
    if version:
        span.set_attribute("pyai.prompt.version", version)
    if blob_url:
        span.set_attribute("pyai.prompt.blob_url", blob_url)
        span.set_attribute("pyai.response.blob_url", blob_url)


def set_eval_context(
    run_id: Optional[str] = None,
    suite: Optional[str] = None,
    case_id: Optional[str] = None,
    metric_name: Optional[str] = None,
    metric_value: Optional[float] = None,
) -> None:
    if trace is None:
        return
    span: Span = trace.get_current_span()
    if span is None:
        return
    if run_id:
        span.set_attribute("pyai.eval.run_id", run_id)
    if suite:
        span.set_attribute("pyai.eval.suite", suite)
    if case_id:
        span.set_attribute("pyai.eval.case_id", case_id)
    if metric_name is not None:
        span.set_attribute("pyai.eval.metric.name", metric_name)
    if metric_value is not None:
        span.set_attribute("pyai.eval.metric.value", float(metric_value))
