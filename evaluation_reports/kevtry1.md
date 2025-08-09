# PyAI Efficiency Evaluation – kevtry1

Date: 2025-08-08
Scope: Assessment based solely on the provided logs/state snapshots.

Sources reviewed:
- `src/logs/pyai_20250808_192303.log`
- `src/logs/pyai_20250808_192308.log`
- `src/logs/pyai_20250808_192329.log`
- `src/logs/state/master_state_f7c73248-f436-41f3-abde-c9ca8e59ace3_20250808_193050.json`
- `src/logs/state/master_state_f7c73248-f436-41f3-abde-c9ca8e59ace3_20250808_193253.json`
- `src/logs/state/master_state_f7c73248-f436-41f3-abde-c9ca8e59ace3_20250808_193304.json`
- `src/logs/state/master_state_f7c73248-f436-41f3-abde-c9ca8e59ace3_20250808_193304.llm.json`

## Findings
- **Intent & planning fast**: LLM intent analysis + centralized sub-query generation complete quickly (seconds): 19:23:34–19:23:47.
- **Phase 1 (data collection) long**: 19:23:37 → 19:30:50 (~7m13s) before report generation begins.
- **Largest latency block observed**: 19:25:52 → 19:27:47 (~1m55s) spent on a blocked/redirected scrape (`statista.com` 302 to SSO) – wasted wait time.
- **Duplicate/redo work**:
  - Same GWEC PDF cleaned multiple times (19:28:16, 19:28:24, 19:28:35, 19:28:43), implying ineffective cross-step dedup.
  - Serper searches returned repeats; dedup said “Prevented 0 duplicate URLs” despite visible repetition.
- **Tavily pipeline waste**: 4 scraped items later fully garbage-filtered (100% of scraped items discarded). Scraping happened before filtering.
- **Batch cleaning defeated by PDFs**: Batch announced, but fell back to sequential per-item cleaning due to PDFs; total ~35s for 5 items.
- **OpenAI calls numerous**: Multiple chat completions across phases (expansion, cleaning, summarization), likely inflating latency and cost.

## Probable Root Causes of Slowness
- **Network-bound scraping delays**: Long waits on 302/403/unsupported_browser flows with default timeouts.
- **Late-stage filtering**: Scraping low-value domains before quality checks/domain filters.
- **Dedup timing/location**: Dedup runs too late or on the wrong key; duplicates slip into scrape and cleaning.
- **PDF handling**: PDFs force sequential cleaning and heavy LLM work; repeated passes on same PDF exacerbate.
- **Over-serialization of cleaning**: Even with “batched” mode, fallback serialized the workload.

## Efficiency Opportunities (without sacrificing much quality)

### 1) Web Fetching Layer
- **Early HEAD + robots/redirect checks**: Issue a HEAD first to detect content-type, content-length, and 3xx/4xx. Skip or fast-fail on `302` to SSO, `403` sites, or binary/PDF beyond thresholds.
- **Aggressive timeouts + retry policy**: e.g., connect=3s, read=8s, total=12–15s; circuit-breaker per domain.
- **Domain allow/deny lists**: Prefer GWEC, IEA, IRENA, DOE/NREL, academic or reputable outlets; down-rank/ban spammy blogs and known SSO-gated properties (Statista, paywalled journals). Apply pre-scrape.
- **Content-length gating**: Skip or down-rank sources > N MB unless explicitly requested; use alternative non-PDF mirrors when available.

### 2) Deduplication & Caching
- **URL canonicalization**: Normalize query params and percent-encoding; dedup on canonical URL before scraping/cleaning.
- **Cross-agent dedup before scrape**: Merge Tavily/Serper sets, dedup, then schedule fetch; avoid “Prevented 0 duplicates” mismatches.
- **Persistent fetch cache**: Cache by `sha1(url)` with TTL; reuse scraped and cleaned artifacts across runs and within a run.
- **Content-similarity dedup**: Compute minhash/SimHash on text snippets to collapse near-duplicates (e.g., same PDF via multiple links).

### 3) Pre-filtering Before Scrape
- **Heuristic scoring pre-scrape**: Apply the same garbage filters (repetition, spam patterns) on metadata/snippets to avoid fetching low-value pages.
- **Source-quality prior**: Learned priors per domain to skip categories that historically get filtered out.

### 4) PDF Strategy
- **Direct PDF text extraction**: Use a fast local extractor (pdfminer/pymupdf) where license allows, avoiding LLM for initial cleaning.
- **Chunked summarization**: If LLM needed, chunk PDFs and summarize hierarchically (map-reduce) to constrain tokens and parallelize.
- **Single-pass per PDF**: Ensure one cleaning/summarization per unique PDF per run.

### 5) LLM Call Minimization
- **Consolidate cleaning prompts**: Combine multiple items in a single prompt where safe; or use a smaller model for cleaning.
- **Static templates over LLM for simple tasks**: Use deterministic rules for boilerplate stripping; reserve LLM for semantic condensation.
- **Adaptive quality tiering**: Lower-cost model for first-pass cleaning; escalate to higher quality only for top N sources feeding the report.

### 6) Orchestration & Concurrency
- **Concurrency caps per domain**: Prevent cascading rate-limits and long queues.
- **Phase pipelining**: Begin report scaffolding (headings, outline) while fetch/clean for top sources completes; fill in incrementally.
- **Timeout budgets per phase**: Hard budget Phase 1 (e.g., 120s). If exceeded, proceed with best available.

### 7) Metrics & Observability
- **Per-URL timeline**: Log start/end/duration for resolve → fetch → scrape → clean → filter.
- **Reason codes for skips**: “Skipped: 302 SSO”, “Skipped: domain denylist”, etc., to validate waste reduction.
- **Dedup efficacy counters**: Pre-scrape and pre-clean dedup hit counts.

## Quick Wins (high impact, low risk)
- **Pre-scrape domain gating and HEAD checks** to eliminate SSO/paywall/blocked sites (e.g., Statista) and media-heavy PDFs.
- **Canonical URL dedup before any scraping/cleaning**; ensure dedup spans both Tavily and Serper results.
- **Persistent fetch/clean cache** keyed by canonical URL; single-pass cleaning enforced.
- **Stricter timeouts** on HTTP GET; fail fast and move on.

## Medium-Term Improvements
- **PDF local extraction + hierarchical summarization** to reduce LLM tokens and latency.
- **Quality-tiered LLM usage**: small model first, escalate only for final top sources.
- **Similarity-based dedup** to catch same docs via different URLs.

## Advanced Options
- **Learning-to-rank** source selection using historical outcomes (which domains contribute to final reports).
- **Asynchronous outline-first reporting**: Start report generation earlier and stream updates as sources land.

## Notes on “Special Batching” Concern
From the trace, latency appears dominated by network/scraping and repeated PDF cleaning rather than the LLM “deciding when to return.” The “batched cleaning” step fell back to sequential per-PDF cleaning, which explains perceived batching/deferral. Tightening pre-scrape filters and enforcing single-pass per URL should remove most of the stall and redundancy.

## Expected Impact
- 30–60% Phase‑1 latency reduction from pre-scrape gating + faster timeouts.
- 50–80% reduction in redundant work via canonical dedup + caching.
- 20–40% token/cost reduction with PDF local extraction + tiered LLM usage.

---
Prepared for: performance tuning and planning. No code changes made in this step.
