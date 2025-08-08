# Evaluation: Multi‑Agent Research Pipeline (latest run)

Date: 2025-08-08
Author: Cascade
Target: End-to-end research/cleaning/report pipelines with garbage filter

## Scope and Inputs Examined
- Master states and truncated LLM states:
  - `src/logs/state/master_state_afe1a1b7-fc73-4aeb-b233-da1b7eefe320_20250808_095920.json`
  - `src/logs/state/master_state_afe1a1b7-fc73-4aeb-b233-da1b7eefe320_20250808_100248.json`
  - `src/logs/state/master_state_afe1a1b7-fc73-4aeb-b233-da1b7eefe320_20250808_100251.json`
  - `src/logs/state/master_state_afe1a1b7-fc73-4aeb-b233-da1b7eefe320_20250808_100251.llm.json`
- Terminal/log excerpts for scraping outcomes, filtering/cleaning stats, batching times, and HTTP status events.
- Config context in `src/config.py` (models, truncation, filter thresholds, timezone, dual-output logging).

Note: Truncated views were sufficient to verify key behaviors (filter/clean reductions, LLM usage, scraping errors). Full JSONs are large, dual logging (`.llm.json`) worked as intended.

## Pipeline Correctness
- The hub-and-spoke orchestration ran to completion: research agents produced items, cleaning executed, garbage filter applied, `ReportWriterAgent` generated a draft and final report captured in the `.llm.json`.
- No model misconfiguration errors detected; models referenced include `gpt-5-nano-2025-08-07` and `gpt-5-mini-2025-08-07` per config.
- Data models serialized cleanly (no `HttpUrl` serialization regressions). Outputs align with `ResearchItem` expectations.

## Garbage Filter Effectiveness
- Observed runs showed aggressive filtering:
  - Example batch: 7/8 items filtered (~87% character removal pre-LLM).
  - Serper-derived batch showed near 100% filtering in one instance (low-quality domains/duplicate/snippets).
- Direct impact:
  - Significant reduction in tokenized inputs to LLM steps.
  - Estimated API cost savings are material (order-of-magnitude reductions in some batches).
- Qualitative review: filtered-out content matched expected patterns (thin SEO pages, blocked redirects, low signal). Retained items appeared higher quality.

## Cleaning Pipeline Effectiveness
- Cleaning produced large reductions in retained content size (e.g., ~10,000 → ~500 chars ≈ 95% reduction) via summary/boiling-down.
- Batched cleaning timings were logged; throughput stable and predictable post-filtering due to smaller batches.
- Output structure consistently fed into `ReportWriterAgent` without errors.

## Latency Profile and Bottlenecks
- Scraping/HTTP layer:
  - Intermittent 403/302 responses created gaps and retries; these are external but affect wall-clock time.
  - Some sources yielded no usable content after redirects, later filtered as garbage (wasted fetch time).
- Research provider variability:
  - Serper/Tavily depth and raw content inclusion improve recall but lengthen round-trip time under throttling.
- Sequencing/parallelism:
  - Filtering reduces batch sizes early, but some steps appear to serialize sub-batches (opportunity for more parallel cleaning/LLM calls under rate limits).
- LLM inference:
  - Post-cleaning inputs are small; LLM latency is no longer dominant vs. network + provider latency for fetches.

## Reliability Observations
- External blockages (403/302) frequent; current handling prevents hard failures but costs time.
- Domain quality scoring + filter thresholds working; logs include reasons and scores (good for auditability).
- Dual-state logging effective: `.llm.json` keeps small actionable traces; full JSON maintains provenance.

## Cost and Efficiency Summary
- Garbage filtering prior to cleaning removes the majority of tokens before touching LLMs.
- Cleaning further compresses by ~95% on average for retained items.
- Combined, the system likely cuts LLM spend by an order of magnitude vs. naive ingestion, while also reducing inference latency.

## Opportunities to Reduce Latency (no code changes made yet)
- Parallelism within limits:
  - Increase concurrent cleaning/mini-LLM summarizations for retained items, gated by model RPS and CPU.
  - Use `asyncio.gather` with bounded semaphores for fetch → clean pipelines.
- Smarter prefetch and early exit:
  - Abort scraping chains on low-quality domain matches early (denylist/score threshold before fetch when possible).
  - If top-k high-quality items already exceed confidence threshold, short-circuit further depth.
- Caching:
  - Cache per-URL cleaned summaries and domain-allow decisions with TTL; avoid re-cleaning on re-runs.
  - Memoize domain classification and boilerplate trimming for repeated publishers.
- Request tuning:
  - Tighter timeouts for low-value domains; adaptive backoff on 403/302.
  - Prefer text-centric endpoints (RSS/sitemaps/api) where available to bypass anti-bot HTML.
- Provider strategy:
  - Keep Tavily advanced depth for first pass; switch to shallow for follow-ups.
  - Use domain filters to avoid known low-value hosts entirely.
- Batching and streaming:
  - Batch mini-LLM summarizations; stream tokens to overlap compute with fetch.

## Metrics To Add for Better Profiling
- Per-stage timers: fetch, parse, filter, clean, synthesize, with percentiles.
- Counts and sizes: items in/out at each stage, characters/tokens saved by filter and clean.
- Failure taxonomy: 403/302/timeout rates by domain and provider.
- Concurrency metrics: queue depths, wait times, utilization vs. configured rate limits.

## Risks and Trade-offs
- Over-filtering can drop niche but valuable sources; monitor recall by comparing headlines vs. retained set.
- Aggressive timeouts may reduce reliability in slower regions; consider per-domain SLA baselines.
- Increased parallelism may hit provider rate limits; keep configurable and observability-driven.

## Actionable Checklist (Proposed, non-invasive)
- [ ] Add per-stage latency/timing and token accounting to `ResearchDataLogger`.
- [ ] Introduce URL/domain cache with TTL for allow/deny and cleaned summaries.
- [ ] Implement early-exit rule when confidence threshold reached.
- [ ] Tighten timeouts and backoff for repeating 403/302; add alternate source fallback.
- [ ] Increase safe parallelism for cleaning/mini-LLM with bounded concurrency.
- [ ] Expand domain filters to exclude recurring low-quality hosts observed in logs.

## Conclusion
The pipeline is correct and effective. The garbage filter substantially reduces input size before any LLM work, and the cleaning step further compresses retained content, shifting the main latency from inference to network/research providers. Short, targeted improvements in parallelism, caching, early exits, and timeout/backoff policies should yield immediate latency gains without architectural changes.
