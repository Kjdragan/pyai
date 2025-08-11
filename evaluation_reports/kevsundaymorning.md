# Wind Energy Scraper Pipeline Evaluation (Kev Sunday Morning)

Date: 2025-08-10
Report file: `evaluation_reports/kevsundaymorning.md`

## Scope
- Sources analyzed strictly from:
  - Logs: `src/logs/pyai_20250810_002753.log`, `src/logs/pyai_20250810_002815.log`, `src/logs/pyai_20250810_002801.log`
  - Terminal output reflected in these logs
  - State file explicitly provided by user: `src/logs/state/master_state_c1429856-8c2b-4ef4-8bb2-452a62015190_20250810_002927.llm.json`

## Executive Summary
- Target of 10 scraped sources achieved via adaptive fallback.
- Quality grader scheduled 8 initial items; fallback added remaining until 10.
- Multiple large PDFs were successfully extracted (up to ~653k chars, 289 pages).
- Failures observed: HTTP 403 on some PDFs; duplicate URL rejection during fallback.
- Garbage filtering stage reported 0 removals; 40 items proceeded to LLM cleaning.
- Topic drift/hallucination detected in the provided state snapshot: job was for “quantum computing 2025” while this run’s focus was wind energy.

## Funnel Breakdown (from logs)
Source: `src/logs/pyai_20250810_002753.log` lines 401–470

- **Quality grader summary**
  - Total results: 20
  - Scheduled for scraping: 8 (40.0%)
  - Avg quality score: ~0.57 (as logged)

- **Adaptive fallback and target attainment**
  - Initial successful scrapes before fallback: 6/10 (logged check)
  - Fallback triggered due to shortfall (6 < 10)
  - Fallback attempts included successes and failures (examples below)
  - Final scraped: 10/20 (50.0%)
  - Target achievement: 10/10 (100%)
  - Logged sequences show two optimization summaries during the session:
    - One block: API results processed = 20 → Final scraped 10/20
    - Another block: API results processed = 17 → Final scraped 10/17
  - Interpretation: multiple search iterations/sub-runs within the same session reached the 10 target with different intermediate counts.

- **Fallback outcomes (examples)**
  - Successes:
    - `https://en.wikipedia.org/wiki/Cost_of_electricity_by_source` (10,003 chars)
    - `https://www.solarpowereurope.org/.../global-market-outlook-for-solar-power-2023-2027/detail` (440 chars)
    - `https://docs.nrel.gov/docs/fy17osti/67645.pdf` (653,512 chars; 289 pages)
    - `https://www.sdewes.org/jsdewes/pid9.0387` (10,003 chars)
    - `https://www.lazard.com/media/eijnqja3/lazards-lcoeplus-june-2025.pdf` (90,786 chars; 48 pages)
    - `https://docs.nrel.gov/docs/fy23osti/84710.pdf` (563,106 chars; cached reuse noted)
    - `https://css.umich.edu/publications/factsheets/energy/wind-energy-factsheet` (10,003 chars)
    - `https://www.energy.gov/eere/wind/next-generation-wind-technology` (10,003 chars)
    - `https://www.cleanenergywire.org/factsheets/german-onshore-wind-power-output-business-and-perspectives` (10,003 chars)
  - Failures:
    - `https://www.mdpi.com/2071-1050/13/1/396` — Pre-flight failed: HTTP 403
    - `https://www.ethree.com/.../LNG-Alternatives-for-Clean-Electricity-Production_May-2023.pdf` — PDF extraction failed: HTTP 403
    - `https://pmc.ncbi.nlm.nih.gov/articles/PMC10339184/` — Domain previously failed
    - Duplicate prevented: `https://emp.lbl.gov/wind-technologies-market-report`

- **HTTP method behavior (sample logs)**
  - HEAD often OK for HTML pages (e.g., DOE/UMich), followed by successful GET.
  - Some PDFs return 403 on GET despite HEAD or preflight, e.g., EWEA PDF.

- **PDF extraction highlights**
  - Lazard LCOE+ 2025: 90,786 chars, 48 pages
  - NREL (67645): 653,512 chars, 289 pages
  - GOWR-2024: 445,147 chars, 156 pages
  - Cached reuse detected for NREL 84710 during fallback

- **Garbage filtering & cleaning**
  - Programmatic garbage filtering applied to 40 scraped items
  - Filtered 0/40 (0.0%); 40 items proceeded to LLM cleaning
  - Batched cleaning initiated for 40 items (batch_size=4)

## Topic Drift / Hallucination (state snapshot)
Source: `src/logs/state/master_state_c1429856-8c2b-4ef4-8bb2-452a62015190_20250810_002927.llm.json`

- **Observed**
  - `job_type`: `research`; `pipeline_type`: `serper`
  - `query`: “Latest developments in quantum computing 2025”
  - 6 results recorded; 4 scraped (`content_scraped: true`), 2 failed
  - Errors: `Pre-flight failed: Blocked content type: application/pdf` (arXiv PDF), `Duplicate URL in session` (Science DOI)
  - `content_cleaned: true` on the 4 successes; `quality_score: null` for all

- **Mismatch with wind energy run**
  - The live logs clearly focus on wind energy sources (LCOE, NREL, DOE, solar/wind outlooks, etc.).
  - The provided state file reflects a different topic (“quantum computing”), indicating topic drift or cross-session state contamination.

- **Likely causes**
  - Stale session state or orchestrator reuse across distinct jobs
  - Misrouted state write when multiple research jobs run close in time
  - Cached query/sub-query injection from a previous run

- **Impact**
  - Off-topic state metrics can confuse automated reporting and skew meta-analytics.
  - If state is used to drive fallback or cleaning, topic mismatch could lead to irrelevant sources being considered.

- **Mitigations**
  - Partition state by query/topic hash; include `topic_tag` = “wind_energy” in state keys and file names.
  - Enforce strict orchestrator/session scoping; prevent cross-run merges.
  - Validate `research_data.original_query` against current UI query prior to enqueueing or persisting.

## Clarification on “10 outside threshold” logic
- Quality grader scheduled 8 above-threshold items initially.
- Adaptive fallback then selected additional candidates from below threshold or alternate queues until total scraped sources reached the target (10).
- The logs show +5 or +4 added in different sub-runs to reach 10/10, consistent with “pull from outside threshold if needed.”

## Issues and Opportunities
- **HEAD vs GET**: HEAD succeeds for many HTML pages, but is unreliable for some PDFs/domains. Consider domain-specific overrides or skip HEAD for known problematic PDF hosts.
- **403s on PDFs**: Add retry with alt headers, or fetch via documented public mirrors when possible.
- **Duplicate handling**: Duplicate rejection occurred during fallback. De-duplicate earlier (pre-scheduling) to avoid churn.
- **Large PDFs**: Multiple very large docs processed successfully; continue chunked cleaning to manage token load.
- **Garbage filtering**: 0/40 filtered — revisit rules/heuristics to ensure they are effective, or confirm that the inputs were already high-quality after grading.

## Recommendations
1. **State isolation & topic guardrails**
   - Hash state files by `(orchestrator_id, topic_tag)`; refuse writes when `original_query` != UI query.
2. **PDF preflight policy**
   - Allow-list trusted `application/pdf` domains (e.g., `lazard.com`, `docs.nrel.gov`, `arxiv.org`) to avoid false preflight blocks.
3. **Early dedupe**
   - Maintain a session-level URL set checked before enqueueing scraping/fallback.
4. **Adaptive HEAD/GET policy**
   - Skip HEAD for known domains where it yields 403/blocked but GET succeeds, or directly probe with GET + lightweight range requests.
5. **Quality score persistence**
   - Ensure `quality_score` is persisted in state for downstream analytics consistency.
6. **Garbage filter tuning**
   - Review filter criteria; if intentionally lenient for graded items, document rationale. Otherwise, tighten rules to reduce noisy inputs.

## Notable Citations from Logs
- `pyai_20250810_002753.log` lines 401–470: final counts, fallback detail, PDF extractions, garbage filtering and cleaning batch start.
- `pyai_20250810_002815.log`: additional HTTP request/extraction context consistent with the above.
- `pyai_20250810_002801.log`: Streamlit app initialization and readiness.
- State file: `master_state_c1429856-...002927.llm.json`: shows quantum-computing topic drift and detailed per-item scrape outcomes.

## Conclusion
The wind energy scraping run achieved its target of 10 sources via adaptive fallback, successfully incorporating multiple substantial PDFs. The provided state file reveals a separate, off-topic research snapshot (quantum computing), indicating a topic drift/state-mixing issue that should be addressed with stronger session isolation and query validation. Implementing the recommendations above should reduce fallback churn, improve PDF handling, and prevent future topic mismatches.
