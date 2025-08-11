"""
Serper-based Research Agent for comprehensive search capabilities.
Uses Google Search via Serper API for high-quality research results.
"""

import asyncio
import httpx
import time
from typing import List, Optional
from datetime import datetime
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from models import ResearchPipelineModel, ResearchItem, AgentResponse
from config import config
from agents.query_expansion import expand_query_to_subquestions as expand_query_to_subquestions_llm
from agents.content_cleaning_agent import clean_research_item_content
from agents.quality_grader import quality_grader
from utils.time_provider import today_str, now


class SerperResearchDeps:
    """Dependencies for Serper Research Agent."""
    
    def __init__(self):
        self.api_key = config.SERPER_API_KEY
        self.max_results = config.MAX_RESEARCH_RESULTS
        self.current_date = today_str()
        self.research_results: List[ResearchItem] = []
        self.sub_questions: List[str] = []


async def expand_query_to_subquestions(query: str) -> List[str]:
    """Delegate to centralized LLM-based query expansion to ensure high-quality, search-optimized sub-questions."""
    return await expand_query_to_subquestions_llm(query)


# PERFORMANCE OPTIMIZATION: Enhanced scraping with pre-flight checks moved to utils
# This eliminates duplicate code and provides intelligent gating to avoid blocked sites
from utils.intelligent_scraper import scrape_url_content_detailed

async def scrape_url_content(url: str, max_chars: int = 2000) -> str:
    """Enhanced scraping with pre-flight checks and intelligent error handling."""
    result = await scrape_url_content_detailed(url, max_chars)
    
    # Log detailed information for debugging
    if not result.success:
        if result.was_blocked:
            print(f"🚫 BLOCKED: {url} - {result.block_reason} (saved {result.processing_time:.2f}s)")
        else:
            print(f"❌ FAILED: {url} - {result.error_reason} (after {result.processing_time:.2f}s)")
    else:
        print(f"✅ SUCCESS: {url} - {len(result.content)} chars (in {result.processing_time:.2f}s)")
    
    return result.content


async def search_serper(query: str, api_key: str, max_results: int = 10) -> List[ResearchItem]:
    """Perform search using Serper API with URL content scraping."""
    
    if not api_key:
        return []
    
    url = "https://google.serper.dev/search"
    
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": query,
        "num": config.SERPER_MAX_RESULTS,  # Use optimized result count
        "hl": "en",
        "gl": "us"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Process organic results with position-based quality scoring
            raw_results = []
            organic_results = data.get("organic", [])[:config.SERPER_MAX_RESULTS]  # Use full result set
            
            print(f"📊 SERPER OPTIMIZATION: Processing {len(organic_results)} results from API")
            
            for i, item in enumerate(organic_results):
                basic_snippet = item.get("snippet", "")
                source_url = item.get("link", "")
                
                # Calculate position-based relevance score (1.0 for position 1, decreasing to 0.05 for position 20)
                # Google's organic ranking provides implicit quality - higher positions = higher quality
                position_score = max(0.05, 1.0 - (i * 0.05))  # Position 1 = 1.0, Position 20 = 0.05
                
                # Create initial research item with position-based scoring
                result = ResearchItem(
                    query_variant=query,
                    source_url=source_url,
                    title=item.get("title", ""),
                    snippet=basic_snippet,
                    relevance_score=position_score,  # Position-based quality score
                    timestamp=now(),
                    content_scraped=False,
                    scraping_error=None,
                    content_length=0,
                    scraped_content=None
                )
                raw_results.append(result)
                
                print(f"🎯 SERPER QUALITY: Position {i+1} → Score {position_score:.3f} for {source_url}")
            
            # Apply intelligent quality grading to determine what to scrape
            print(f"📊 SERPER DEBUG: Applying quality grading to {len(raw_results)} results")
            graded_results = quality_grader.grade_result_batch(
                raw_results, query, "serper", max_scrape_count=config.MAX_SCRAPING_PER_QUERY
            )
            
            # Now perform selective scraping based on quality grades
            final_results = []
            for result in graded_results:
                should_scrape = result.metadata.get('should_scrape', False)
                
                if should_scrape and result.source_url:
                    print(f"🚀 SERPER DEBUG: High-quality result - scraping {result.source_url} (score: {result.relevance_score:.2f})")
                    
                    # Use detailed scraper to get metadata about PDF extraction
                    scraping_result = await scrape_url_content_detailed(result.source_url, max_chars=10000)
                    
                    if scraping_result.success:
                        result.scraped_content = scraping_result.content
                        result.content_scraped = True
                        result.content_length = len(scraping_result.content)
                        # CRITICAL: Mark if content came from PDF extraction (exempt from garbage filtering)
                        result.is_pdf_content = scraping_result.content_length > 50000  # Large content likely from PDF
                        # More precise PDF detection using URL analysis
                        from urllib.parse import urlparse
                        try:
                            path = urlparse(result.source_url).path.lower()
                            if path.endswith('.pdf') or '.pdf' in path:
                                result.is_pdf_content = True
                                print(f"📄 SERPER DEBUG: PDF content detected for {result.source_url} - will bypass garbage filtering")
                        except:
                            pass
                        # Preserve exact raw scraped text for quote retention analysis
                        result.raw_content = scraping_result.content
                        result.raw_content_length = len(scraping_result.content)
                        print(f"✅ SERPER DEBUG: Successfully scraped {result.content_length} chars from {result.source_url}")
                    else:
                        result.scraping_error = scraping_result.error_reason or "Failed to scrape content"
                        print(f"❌ SERPER DEBUG: Failed to scrape content from {result.source_url}")
                else:
                    skip_reason = result.metadata.get('skip_reason', 'Quality threshold not met')
                    print(f"⏭️  SERPER DEBUG: Skipping scraping for {result.source_url} - {skip_reason}")
                
                final_results.append(result)
            
            # FUNNEL TRACKING: Count final results
            if result.content_scraped or result.snippet:
                funnel_metrics['final_research_items'] += 1
            
            # ADAPTIVE FALLBACK SCRAPING: Ensure we have at least 20 total successful sources (including PDFs)
            scraped_count = sum(1 for r in final_results if r.content_scraped)
            min_sources_target = config.MIN_SCRAPED_SOURCES_TARGET
            
            print(f"🔍 ADAPTIVE SCRAPING CHECK: {scraped_count} successful sources (including PDFs), target: {min_sources_target}")
            
            if scraped_count < min_sources_target:
                print(f"⚠️ FALLBACK TRIGGERED: Only {scraped_count}/{min_sources_target} sources scraped successfully")
                
                # OPTIMIZED FALLBACK: Get candidates for fallback scraping (previously skipped, sorted by score)
                fallback_candidates = []
                for result in final_results:
                    # Skip if already successfully scraped
                    if result.content_scraped:
                        continue
                    
                    # Skip if no URL or previous scraping error 
                    if not result.source_url or result.scraping_error:
                        continue
                        
                    # Include items that weren't originally scheduled for scraping (below quality threshold)
                    if not result.metadata.get('should_scrape', False):
                        fallback_candidates.append(result)
                
                # Sort fallback candidates by relevance score (best first)
                fallback_candidates.sort(key=lambda x: x.relevance_score or 0, reverse=True)
                
                needed_sources = min_sources_target - scraped_count
                # PERFORMANCE: Try 2.5x needed sources to ensure we hit target despite failures
                candidates_to_try = fallback_candidates[:max(needed_sources * 3, 10)]  # Minimum 10, scale with need
                
                print(f"🔄 FALLBACK SCRAPING: Trying {len(candidates_to_try)} additional sources from fallback queue (need {needed_sources} more)")
                
                # EFFICIENT PARALLEL FALLBACK: Launch all fallback scraping simultaneously
                fallback_tasks = []
                for candidate in candidates_to_try:
                    print(f"🎯 FALLBACK: Queuing {candidate.source_url} (score: {candidate.relevance_score:.2f})")
                    task = scrape_url_content_detailed(candidate.source_url, max_chars=10000)
                    fallback_tasks.append((candidate, task))
                
                # Execute all fallback scraping in parallel for maximum efficiency
                if fallback_tasks:
                    print(f"🚀 PARALLEL FALLBACK: Launching {len(fallback_tasks)} scraping tasks simultaneously")
                    fallback_results = await asyncio.gather(*[task for _, task in fallback_tasks], return_exceptions=True)
                    
                    fallback_success_count = 0
                    for (candidate, _), scraping_result in zip(fallback_tasks, fallback_results):
                        if isinstance(scraping_result, Exception):
                            print(f"❌ FALLBACK FAILED: {candidate.source_url} - Exception: {scraping_result}")
                            continue
                        
                        # Early termination if we've reached our target
                        current_total = scraped_count + fallback_success_count
                        if current_total >= min_sources_target:
                            print(f"🎯 TARGET REACHED: {current_total} sources, stopping fallback processing")
                            break
                            
                        if scraping_result.success:
                            # Update the candidate with scraped content
                            candidate.scraped_content = scraping_result.content
                            candidate.content_scraped = True
                            candidate.content_length = len(scraping_result.content)
                            candidate.scraping_error = None
                            
                            # PDF detection for garbage filter exemption
                            candidate.is_pdf_content = scraping_result.content_length > 50000
                            from urllib.parse import urlparse
                            try:
                                path = urlparse(candidate.source_url).path.lower()
                                if path.endswith('.pdf') or '.pdf' in path:
                                    candidate.is_pdf_content = True
                            except:
                                pass
                                
                            # Preserve raw content
                            candidate.raw_content = scraping_result.content
                            candidate.raw_content_length = len(scraping_result.content)
                            
                            fallback_success_count += 1
                            print(f"✅ FALLBACK SUCCESS: {candidate.source_url} - {candidate.content_length} chars")
                            
                            # Stop if we've reached our target
                            if scraped_count + fallback_success_count >= min_sources_target:
                                print(f"🎯 TARGET REACHED: {scraped_count + fallback_success_count} total sources")
                                break
                        else:
                            candidate.scraping_error = scraping_result.error_reason or "Fallback scraping failed"
                            print(f"❌ FALLBACK FAILED: {candidate.source_url} - {candidate.scraping_error}")
                    
                    final_scraped_count = scraped_count + fallback_success_count
                    print(f"🔄 FALLBACK COMPLETE: +{fallback_success_count} sources, total: {final_scraped_count}/{min_sources_target}")
                else:
                    print(f"⚠️ NO FALLBACK CANDIDATES: No additional sources available to try")
                    final_scraped_count = scraped_count
            else:
                print(f"✅ SUFFICIENT SOURCES: {scraped_count} sources exceeds target of {min_sources_target}")
                final_scraped_count = scraped_count
            
            # Log comprehensive optimization summary with fallback results
            avg_position_score = sum(r.relevance_score for r in final_results if r.relevance_score) / len(final_results) if final_results else 0
            quality_summary = quality_grader.get_quality_summary(final_results)
            
            print(f"📈 SERPER OPTIMIZATION RESULTS (WITH ADAPTIVE FALLBACK):")
            print(f"   • API results processed: {len(organic_results)} (max: {config.SERPER_MAX_RESULTS})")
            print(f"   • Position-based avg score: {avg_position_score:.3f}")
            print(f"   • Final scraped: {final_scraped_count}/{len(final_results)} ({(final_scraped_count/len(final_results)*100) if final_results else 0:.1f}%)")
            print(f"   • Target achievement: {final_scraped_count}/{min_sources_target} ({(final_scraped_count/min_sources_target*100):.1f}%)")
            print(f"   • Quality grader summary: {quality_summary}")
            
            return final_results
            
    except Exception as e:
        print(f"Serper search error for '{query}': {str(e)}")
        return []


def clean_and_format_results(results: List[ResearchItem], original_query: str) -> List[ResearchItem]:
    """Clean and format search results while preserving scraping metadata."""
    
    # Remove duplicates by URL
    seen_urls = set()
    cleaned = []
    
    for result in results:
        if result.source_url not in seen_urls and result.source_url:
            seen_urls.add(result.source_url)
            
            # Basic cleaning - remove excessive whitespace from snippet only (keep it short)
            cleaned_snippet = " ".join(result.snippet.split())
            if len(cleaned_snippet) > 500:
                cleaned_snippet = cleaned_snippet[:497] + "..."
            
            # Clean scraped content but DON'T truncate it - keep it full for report generation
            cleaned_scraped_content = None
            if result.scraped_content:
                # Just clean whitespace, but preserve full length
                cleaned_scraped_content = " ".join(result.scraped_content.split())
            
            # Create cleaned item - PRESERVE ALL SCRAPING METADATA AND FULL CONTENT
            cleaned_item = ResearchItem(
                query_variant=result.query_variant,
                source_url=result.source_url,
                title=result.title.strip(),
                snippet=cleaned_snippet,  # Short snippet for display
                relevance_score=result.relevance_score,
                timestamp=result.timestamp,
                # CRITICAL: Preserve scraping metadata
                content_scraped=result.content_scraped,
                scraping_error=result.scraping_error,
                content_length=result.content_length,
                scraped_content=cleaned_scraped_content,  # Full content for report generation (NOT truncated)
                # CRITICAL: Preserve PDF flag for garbage filter exemption
                is_pdf_content=getattr(result, 'is_pdf_content', False),
                # Preserve raw content and cleaning metadata
                raw_content=result.raw_content,
                raw_content_length=result.raw_content_length,
                content_cleaned=result.content_cleaned,
                original_content_length=result.original_content_length,
                cleaned_content_length=result.cleaned_content_length,
                metadata=result.metadata
            )
            cleaned.append(cleaned_item)
    
    # Sort by relevance score (descending)
    cleaned.sort(key=lambda x: x.relevance_score or 0, reverse=True)
    
    return cleaned[:config.MAX_RESEARCH_RESULTS]


# Create Serper Research Agent with instrumentation
serper_research_agent = Agent(
    model=OpenAIModel(config.RESEARCH_MODEL),
    deps_type=SerperResearchDeps,
    output_type=ResearchPipelineModel,
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt=f"""
    You are a research coordination agent that processes Google search results via Serper API.
    
    Today's date is: {today_str()}
    
    When asked to research something:
    1. Call your perform_serper_research tool with the exact user query
    2. The tool returns raw data: {{"original_query": str, "sub_queries": list, "raw_results": list, "processing_time": float}}
    3. Convert this raw data into a ResearchPipelineModel with these exact fields:
       - original_query: use the original_query from tool
       - sub_queries: use the sub_queries from tool  
       - results: convert each item in raw_results to ResearchItem format
       - pipeline_type: set to "serper"
       - total_results: count of items in raw_results
       - processing_time: use processing_time from tool
    
    CRITICAL: When converting raw_results to ResearchItem format, preserve ALL data exactly as-is:
    - scraped_content field must contain the complete raw scraped text without any summarization, processing, or modification
    - Do NOT summarize, clean, or modify the scraped_content in any way
    - Simply pass through all fields from raw_results unchanged
    - The scraped_content should be the full original scraped text, not a summary
    
    When expanding queries, follow this universal approach:
    
    STEP 1: First analyze the query to understand its nature and context:
    - Is it about a product/service, historical event, current news, scientific concept, business topic, etc.?
    - What domain does it belong to (technology, health, politics, economics, science, etc.)?
    - What might be the user's intent (learning, comparison, current status, trends, etc.)?
    
    STEP 2: Based on the query analysis, generate 3 diverse sub-questions that explore different aspects:
    - For PRODUCTS/SERVICES: features/specs, market position/reviews, pricing/availability
    - For HISTORICAL TOPICS: background/causes, key events/timeline, impact/consequences
    - For CURRENT NEWS: recent developments, context/background, implications/reactions
    - For SCIENTIFIC CONCEPTS: fundamental principles, applications/examples, latest research
    - For BUSINESS TOPICS: current status, market dynamics, future outlook
    - For GENERAL TOPICS: adapt based on what would provide comprehensive coverage
    
    Examples across different query types:
    
    Query: "iPhone 15 Pro" (Product)
    Sub-questions:
    1. What are the key features, specifications, and technical improvements of the iPhone 15 Pro?
    2. How does the iPhone 15 Pro compare to competitors and previous iPhone models in reviews and market reception?
    3. What is the pricing, availability, and market performance of the iPhone 15 Pro?
    
    Query: "Fall of Berlin Wall" (Historical)
    Sub-questions:
    1. What were the political and economic factors that led to the fall of the Berlin Wall in 1989?
    2. What were the key events and timeline surrounding the fall of the Berlin Wall?
    3. What were the immediate and long-term consequences of the Berlin Wall's fall on Germany and Europe?
    
    CRITICAL: Return only the structured ResearchPipelineModel. Do not add commentary, explanations, or extra text.
    Just the properly formatted structured data based on what your tool returned.
    """,
    retries=config.MAX_RETRIES
)


@serper_research_agent.tool
async def expand_query_intelligently(ctx: RunContext[SerperResearchDeps], query: str) -> List[str]:
    """Tool to intelligently expand a query into 3 diverse sub-questions using LLM analysis.
    
    First analyzes the query type and context, then generates appropriate sub-questions
    that explore different aspects based on the query's nature (product, historical, news, etc.).
    """
    # This tool leverages the agent's LLM capabilities through the system prompt
    # The actual expansion logic is handled by the LLM based on the guidelines in the system prompt
    return await expand_query_to_subquestions(query)


@serper_research_agent.tool
async def perform_serper_research(ctx: RunContext[SerperResearchDeps], query: str) -> ResearchPipelineModel:
    """Tool to perform comprehensive Serper research and return ResearchPipelineModel."""
    try:
        print(f"🔍 SERPER TOOL DEBUG: Starting research for query: {query}")
        
        if not ctx.deps.api_key:
            print(f"❌ SERPER TOOL DEBUG: API key not configured")
            return ResearchPipelineModel(
                original_query=query,
                sub_queries=[],
                results=[],
                pipeline_type="serper",
                total_results=0,
                processing_time=0.0
            )
        
        print(f"✅ SERPER TOOL DEBUG: API key configured, current date: {ctx.deps.current_date}")
        
        # NEW APPROACH: Process single query directly from orchestrator
        # Each agent instance now handles one specific query instead of multiple sub-queries
        if "Process this single query directly" in query:
            # Extract the actual query from the orchestrator instruction
            actual_query = query.split("comprehensive research on: ")[1].split(". IMPORTANT:")[0]
            sub_questions = [actual_query]
            print(f"🎯 SERPER TOOL DEBUG: Processing single query from orchestrator: '{actual_query}'")
        else:
            # Legacy fallback for backward compatibility
            import re
            sub_query_match = re.search(r'Use these pre-generated sub-queries.*?:\n((?:\d+\.\s+.*\n?)+)', query, re.DOTALL)
            
            if sub_query_match:
                # Extract pre-generated sub-queries from orchestrator
                sub_queries_text = sub_query_match.group(1)
                sub_questions = []
                for line in sub_queries_text.strip().split('\n'):
                    if line.strip() and re.match(r'\d+\.\s+', line):
                        sub_question = re.sub(r'^\d+\.\s+', '', line.strip())
                        sub_questions.append(sub_question)
                print(f"🎯 SERPER TOOL DEBUG: Using {len(sub_questions)} pre-generated sub-queries from orchestrator")
                print(f"📝 Sub-queries: {sub_questions}")
            else:
                # CRITICAL FIX: Use single query as fallback instead of generating new sub-queries
                # This prevents the infinite loop that was causing 58+ API calls
                sub_questions = [query]
                print(f"🎯 SERPER TOOL DEBUG: Using single query fallback (no pre-generated sub-queries found)")
        
        # Perform parallel searches with full result capacity per sub-query
        # This allows comprehensive research coverage instead of artificially limiting results
        # Execute searches with optional bounded parallelism + FUNNEL TRACKING
        start_time = time.time()
        print(f"🚀 PARALLELISM DEBUG: Starting {len(sub_questions)} queries in parallel at {start_time:.2f}")
        
        # FUNNEL PERFORMANCE: Initialize tracking metrics
        funnel_metrics = {
            'total_queries': len(sub_questions),
            'api_calls_successful': 0,
            'api_calls_failed': 0,
            'total_raw_results': 0,
            'results_above_threshold': 0,
            'scheduled_for_scraping': 0,
            'scraping_successful': 0,
            'scraping_failed': 0,
            'pdf_extractions': 0,
            'garbage_filtered': 0,
            'llm_cleaned': 0,
            'final_research_items': 0
        }
        
        if config.RESEARCH_PARALLELISM_ENABLED:
            sem = asyncio.Semaphore(config.SERPER_MAX_CONCURRENCY)
            print(f"📊 PARALLELISM DEBUG: Using semaphore with {config.SERPER_MAX_CONCURRENCY} concurrent searches")

            async def _bounded_search(q: str, index: int):
                query_start = time.time()
                print(f"🔍 QUERY {index+1} DEBUG: Starting search for '{q[:50]}...' at {query_start:.2f}")
                async with sem:
                    try:
                        result = await search_serper(q, ctx.deps.api_key, ctx.deps.max_results)
                        funnel_metrics['api_calls_successful'] += 1
                        query_end = time.time()
                        print(f"✅ QUERY {index+1} DEBUG: Completed in {query_end - query_start:.2f}s at {query_end:.2f}")
                        return result
                    except Exception as e:
                        funnel_metrics['api_calls_failed'] += 1
                        print(f"❌ QUERY {index+1} DEBUG: Failed in {time.time() - query_start:.2f}s: {e}")
                        return []

            search_tasks = [_bounded_search(question, i) for i, question in enumerate(sub_questions)]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        else:
            # Previous behavior: unbounded gather (usually small N)
            print(f"🚀 PARALLELISM DEBUG: Using unbounded parallel execution")
            search_tasks = [
                search_serper(question, ctx.deps.api_key, ctx.deps.max_results)
                for question in sub_questions
            ]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        end_time = time.time()
        print(f"🏁 PARALLELISM DEBUG: All {len(sub_questions)} queries completed in {end_time - start_time:.2f}s total")
        print(f"🔍 SERPER TOOL DEBUG: Received {len(search_results)} search results")
        
        # FUNNEL TRACKING: Combine results and count raw results
        all_results = []
        for i, results in enumerate(search_results):
            if isinstance(results, list):
                print(f"📊 SERPER TOOL DEBUG: Search {i+1} returned {len(results)} results")
                all_results.extend(results)
                funnel_metrics['total_raw_results'] += len(results)
            else:
                print(f"⚠️ SERPER TOOL DEBUG: Search {i+1} returned non-list: {type(results)}")
        
        print(f"📊 SERPER TOOL DEBUG: Total combined results: {len(all_results)}")
        print(f"📈 FUNNEL STEP 1: API Results - {funnel_metrics['total_raw_results']} raw results from {funnel_metrics['api_calls_successful']} successful API calls")
        
        # FUNNEL TRACKING: Count items that went through quality grading and scraping
        for result in all_results:
            if result.relevance_score and result.relevance_score >= 0.5:
                funnel_metrics['results_above_threshold'] += 1
            
            if result.metadata and result.metadata.get('should_scrape', False):
                funnel_metrics['scheduled_for_scraping'] += 1
                
            if result.content_scraped:
                funnel_metrics['scraping_successful'] += 1
                if getattr(result, 'is_pdf_content', False):
                    funnel_metrics['pdf_extractions'] += 1
            elif result.scraping_error:
                funnel_metrics['scraping_failed'] += 1

        print(f"📈 FUNNEL STEP 2: Quality Filter - {funnel_metrics['results_above_threshold']} results above 0.5 threshold")
        print(f"📈 FUNNEL STEP 3: Scraping Queue - {funnel_metrics['scheduled_for_scraping']} items scheduled for scraping")
        print(f"📈 FUNNEL STEP 4: Scraping Results - {funnel_metrics['scraping_successful']} successful (including {funnel_metrics['pdf_extractions']} PDFs), {funnel_metrics['scraping_failed']} failed")

        # PERFORMANCE OPTIMIZATION: Apply programmatic garbage filtering before expensive LLM cleaning
        # This prevents wasting compute resources on low-quality content
        scraped_items = [item for item in all_results if item.scraped_content and item.content_scraped]
        if scraped_items:
            print(f"🗑️  Applying programmatic garbage filtering to {len(scraped_items)} scraped items")
            
            # Import and apply content quality filter
            from utils.content_quality_filter import content_filter
            
            filtered_items = []
            garbage_count = 0
            
            for item in scraped_items:
                # Store pre-filtering content state for visibility
                item.pre_filter_content = item.scraped_content
                item.pre_filter_content_length = len(item.scraped_content or "")
                
                # Apply quality filtering using comprehensive programmatic analysis
                # CRITICAL: Pass PDF flag to exemp PDF content from garbage filtering
                should_filter, filter_reason = content_filter.should_filter_content(
                    content=item.scraped_content,
                    url=item.source_url or "",
                    title=item.title or "",
                    quality_threshold=config.GARBAGE_FILTER_THRESHOLD,  # Configurable threshold
                    is_pdf_content=getattr(item, 'is_pdf_content', False)  # PDF exemption flag
                )
                
                # Get detailed quality analysis for insights
                quality_analysis = content_filter.analyze_content_quality(
                    content=item.scraped_content,
                    url=item.source_url or "",
                    title=item.title or ""
                )
                item.quality_score = quality_analysis['overall_quality_score']
                
                if should_filter:
                    garbage_count += 1
                    print(f"🚮 GARBAGE FILTERED: {item.source_url} - {filter_reason} (Quality: {item.quality_score:.2f})")
                    
                    # Mark as filtered with detailed information
                    item.garbage_filtered = True
                    item.filter_reason = filter_reason
                    item.post_filter_content = None  # No content passed filtering
                    item.post_filter_content_length = 0
                    funnel_metrics['garbage_filtered'] += 1
                    item.content_cleaned = False  # Skip expensive LLM cleaning
                    
                    # Store filtering metadata for transparency
                    if not hasattr(item, 'metadata') or not item.metadata:
                        item.metadata = {}
                    item.metadata['quality_analysis'] = quality_analysis
                    item.metadata['filtered_as_garbage'] = True
                else:
                    # Content passed filtering
                    item.garbage_filtered = False
                    item.filter_reason = None
                    item.post_filter_content = item.scraped_content
                    item.post_filter_content_length = len(item.scraped_content or "")
                    filtered_items.append(item)
                
                # PERFORMANCE OPTIMIZATION: Truncate pre-filter content after processing for log efficiency
                # Keep full content for processing, but truncate stored version to save space
                if item.pre_filter_content and len(item.pre_filter_content) > 500:
                    item.pre_filter_content = item.pre_filter_content[:500] + "...[TRUNCATED FOR LOG EFFICIENCY]"
                    
            # Generate detailed filtering summary for insights
            total_pre_filter_chars = sum(item.pre_filter_content_length or 0 for item in all_results if hasattr(item, 'pre_filter_content_length') and item.pre_filter_content_length)
            total_post_filter_chars = sum(item.post_filter_content_length or 0 for item in filtered_items)
            chars_filtered = total_pre_filter_chars - total_post_filter_chars
            filter_efficiency = (chars_filtered / total_pre_filter_chars * 100) if total_pre_filter_chars > 0 else 0
            
            print(f"✅ GARBAGE FILTERING SUMMARY:")
            print(f"   • Filtered {garbage_count}/{len(scraped_items)} items ({garbage_count/len(scraped_items)*100:.1f}%)")
            print(f"   • Removed {chars_filtered:,} characters ({filter_efficiency:.1f}% reduction)")
            print(f"   • {len(filtered_items)} quality items proceeding to LLM cleaning")
            print(f"   • Estimated API cost savings: ${garbage_count * 0.02:.2f} (prevented garbage processing)")
            
            scraped_items = filtered_items  # Use only non-garbage items for LLM cleaning
            
        # PERFORMANCE OPTIMIZATION: Clean scraped content using batched nano model processing
        # This removes boilerplate text before report generation with true parallel batch processing
        if scraped_items:
            print(f"🧹 Starting BATCHED content cleaning for {len(scraped_items)} Serper results")
            cleaning_start = asyncio.get_event_loop().time()
            
            # Use batched content cleaning for true parallelization
            from agents.content_cleaning_agent import clean_multiple_contents_batched
            content_tuples = [(item.scraped_content, query, item.source_url or "unknown") for item in scraped_items]
            
            # Execute batched cleaning with real parallel processing
            cleaned_results = await clean_multiple_contents_batched(content_tuples, batch_size=4)
            
            # Apply results back to research items with proper metrics
            for item, (cleaned_content, success) in zip(scraped_items, cleaned_results):
                if success:
                    # Preserve raw content before overwriting
                    if not getattr(item, 'raw_content', None):
                        item.raw_content = item.scraped_content
                        item.raw_content_length = len(item.scraped_content)
                    
                    # Update with cleaned content and correct metrics
                    original_length = len(item.scraped_content)
                    item.scraped_content = cleaned_content
                    item.content_cleaned = True
                    funnel_metrics['llm_cleaned'] += 1
                    item.original_content_length = original_length
                    item.cleaned_content_length = len(cleaned_content)
                    item.content_length = len(cleaned_content)  # Fix: should reflect cleaned length
                    
                    # Add quote metrics
                    def _count_quotes(text):
                        quote_chars = ['"', "'", '"', '"', ''', ''']
                        return sum(text.count(ch) for ch in quote_chars)
                    
                    if not hasattr(item, 'metadata') or not item.metadata:
                        item.metadata = {}
                    item.metadata.setdefault('quote_metrics', {})
                    item.metadata['quote_metrics'].update({
                        'quote_chars_before': _count_quotes(item.raw_content or ""),
                        'quote_chars_after': _count_quotes(cleaned_content),
                        'quote_chars_delta': _count_quotes(cleaned_content) - _count_quotes(item.raw_content or "")
                    })
                else:
                    item.content_cleaned = False
            
            cleaning_time = asyncio.get_event_loop().time() - cleaning_start
            success_count = sum(1 for _, success in cleaned_results if success)
            print(f"✅ BATCHED content cleaning completed: {success_count}/{len(scraped_items)} successful in {cleaning_time:.2f}s")
        else:
            print(f"⏭️ No scraped content to clean from Serper results")
        
        # Clean and format results
        cleaned_results = clean_and_format_results(all_results, query)
        print(f"✨ SERPER TOOL DEBUG: After cleaning: {len(cleaned_results)} results")
        
        # Store results in context for agent access
        ctx.deps.research_results = cleaned_results
        ctx.deps.sub_questions = sub_questions
        
        # FINAL FUNNEL REPORT: Complete research funnel performance  
        total_time = time.time() - agent_start_time
        print(f"\n" + "="*80)
        print(f"📈 RESEARCH FUNNEL PERFORMANCE REPORT")
        print(f"="*80)
        print(f"⚡ Total Processing Time: {total_time:.2f}s")
        print(f"🔄 Queries Processed: {funnel_metrics['total_queries']}")
        print(f"📊 API Success Rate: {funnel_metrics['api_calls_successful']}/{funnel_metrics['api_calls_successful'] + funnel_metrics['api_calls_failed']} ({100 * funnel_metrics['api_calls_successful'] / max(1, funnel_metrics['api_calls_successful'] + funnel_metrics['api_calls_failed']):.1f}%)")
        print(f"🔍 Raw Results: {funnel_metrics['total_raw_results']}")
        print(f"🎯 Above Threshold (≥0.5): {funnel_metrics['results_above_threshold']} ({100 * funnel_metrics['results_above_threshold'] / max(1, funnel_metrics['total_raw_results']):.1f}%)")
        print(f"📋 Scheduled for Scraping: {funnel_metrics['scheduled_for_scraping']}")
        print(f"✅ Scraping Success: {funnel_metrics['scraping_successful']} ({100 * funnel_metrics['scraping_successful'] / max(1, funnel_metrics['scheduled_for_scraping']):.1f}%)")
        print(f"📄 PDF Extractions: {funnel_metrics['pdf_extractions']}")
        print(f"❌ Scraping Failed: {funnel_metrics['scraping_failed']}")
        print(f"🗑️  Garbage Filtered: {funnel_metrics['garbage_filtered']}")
        print(f"🧽 LLM Cleaned: {funnel_metrics['llm_cleaned']}")
        print(f"📝 Final Research Items: {funnel_metrics['final_research_items']}")
        print(f"🎯 Conversion Rate: {100 * funnel_metrics['final_research_items'] / max(1, funnel_metrics['total_raw_results']):.1f}% (raw → final)")
        print(f"="*80 + "\n")

        # CRITICAL FIX: Return ResearchPipelineModel instead of dict to prevent infinite agent loop
        return ResearchPipelineModel(
            original_query=query,
            sub_queries=sub_questions,
            results=cleaned_results,  # Already ResearchItem objects
            pipeline_type="serper",
            total_results=len(cleaned_results),
            processing_time=total_time
        )
               
    except Exception as e:
        print(f"❌ SERPER TOOL DEBUG: Exception caught: {str(e)}")
        import traceback
        print(f"❌ SERPER TOOL DEBUG: Traceback: {traceback.format_exc()}")
        return ResearchPipelineModel(
            original_query=query,
            sub_queries=[],
            results=[],
            pipeline_type="serper",
            total_results=0,
            processing_time=0.0
        )


# DELETED: Legacy function removed - use serper_research_agent Pydantic AI agent instead