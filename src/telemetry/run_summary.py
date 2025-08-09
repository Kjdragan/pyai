"""
Run summary aggregation utility for dev-only tracing and debugging.
Collects counters and timings across the pipeline and emits a single
JSON summary at end-of-run via Logfire (if available) and Python logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import threading
import time

try:
    import logfire  # type: ignore
    _LOGFIRE = True
except Exception:
    _LOGFIRE = False


@dataclass
class _RunSummary:
    start_ts: float = field(default_factory=time.time)
    end_ts: float | None = None

    # Research
    subquery_count: int = 0
    research_results_total: int = 0
    research_filtered_out: int = 0
    research_pdf_count: int = 0
    tavily_min_score: float | None = None
    garbage_threshold: float | None = None

    # Cleaning
    cleaned_items: int = 0
    cleaned_success: int = 0
    cleaned_chars_in_total: int = 0
    cleaned_chars_out_total: int = 0

    # Report
    report_section_count: int = 0
    report_enhancement_passes: int = 0

    # Concurrency (observed peak sizes)
    research_max_concurrency: int = 0

    # Retries
    retry_count_total: int = 0

    # Errors
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        duration = (self.end_ts or time.time()) - self.start_ts
        return {
            "duration_seconds": round(duration, 2),
            "subquery_count": self.subquery_count,
            "research_results_total": self.research_results_total,
            "research_filtered_out": self.research_filtered_out,
            "research_pdf_count": self.research_pdf_count,
            "tavily_min_score": self.tavily_min_score,
            "garbage_threshold": self.garbage_threshold,
            "cleaned_items": self.cleaned_items,
            "cleaned_success": self.cleaned_success,
            "avg_clean_reduction": self._avg_reduction(),
            "report_section_count": self.report_section_count,
            "report_enhancement_passes": self.report_enhancement_passes,
            "research_max_concurrency": self.research_max_concurrency,
            "retry_count_total": self.retry_count_total,
            "errors": self.errors,
        }

    def _avg_reduction(self) -> float:
        if self.cleaned_items == 0 or self.cleaned_chars_in_total == 0:
            return 0.0
        reduction = (self.cleaned_chars_in_total - self.cleaned_chars_out_total) / max(1, self.cleaned_chars_in_total)
        return round(reduction * 100.0, 2)


class RunSummary:
    """Thread-safe singleton aggregator."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = _RunSummary()

    # Generic helpers
    def add_error(self, msg: str) -> None:
        with self._lock:
            self._state.errors.append(msg)

    def inc_retry(self, n: int = 1) -> None:
        with self._lock:
            self._state.retry_count_total += n

    # Orchestrator / Research
    def set_subquery_count(self, n: int) -> None:
        with self._lock:
            self._state.subquery_count = n

    def set_thresholds(self, min_score: float | None, garbage_threshold: float | None) -> None:
        with self._lock:
            self._state.tavily_min_score = min_score
            self._state.garbage_threshold = garbage_threshold

    def observe_research_results(self, total: int, filtered_out: int, pdf_count: int) -> None:
        with self._lock:
            self._state.research_results_total += total
            self._state.research_filtered_out += filtered_out
            self._state.research_pdf_count += pdf_count

    def observe_research_concurrency(self, current: int) -> None:
        with self._lock:
            self._state.research_max_concurrency = max(self._state.research_max_concurrency, current)

    # Cleaning
    def observe_cleaning(self, chars_in: int, chars_out: int, success: bool) -> None:
        with self._lock:
            self._state.cleaned_items += 1
            if success:
                self._state.cleaned_success += 1
            self._state.cleaned_chars_in_total += max(0, chars_in)
            self._state.cleaned_chars_out_total += max(0, chars_out)

    # Report
    def set_report(self, sections: int, enhancement_passes: int) -> None:
        with self._lock:
            self._state.report_section_count = sections
            self._state.report_enhancement_passes = enhancement_passes

    # Emit summary
    def emit(self, attributes: Dict[str, Any] | None = None) -> Dict[str, Any]:
        with self._lock:
            self._state.end_ts = time.time()
            payload = self._state.to_dict()
        if attributes:
            payload.update(attributes)
        # Emit to Logfire (event) if available
        if _LOGFIRE:
            try:
                logfire.info("run_summary", **payload)  # typed as structured log/event
            except Exception:
                pass
        return payload


# Global instance
run_summary = RunSummary()
