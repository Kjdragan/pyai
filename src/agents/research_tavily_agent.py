"""
Research Pipeline 1: Tavily-based research agent.
Expands queries into 3 sub-questions and performs parallel searches.
"""

import asyncio
import httpx
from typing import List, Optional
from tavily import AsyncTavilyClient
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from datetime import datetime
import time
from bs4 import BeautifulSoup

from models import ResearchPipelineModel, ResearchItem, AgentResponse
from config import config
from agents.query_expansion import expand_query_to_subquestions as expand_query_to_subquestions_llm
from agents.content_cleaning_agent import clean_research_item_content
from agents.quality_grader import quality_grader
from utils.time_provider import today_str, now
from telemetry.run_summary import run_summary  # dev-only tracing summary


class TavilyResearchDeps:
    """Dependencies for Tavily Research Agent."""
    def __init__(self):
        self.api_key = config.TAVILY_API_KEY
        self.timeout = config.RESEARCH_TIMEOUT
        self.max_results = config.MAX_RESEARCH_RESULTS
        self.current_date = today_str()
        self.research_results = []  # Store results for agent access
        self.sub_questions = []     # Store sub-questions for agent access
        self._client = None  # Reusable async client
        self._last_request_time = 0  # Rate limiting
        self._min_request_interval = 1.0 / config.TAVILY_RATE_LIMIT_RPS  # Configurable RPS
    
    async def get_client(self) -> AsyncTavilyClient:
        """Get or create reusable async Tavily client."""
        if self._client is None:
            self._client = AsyncTavilyClient(api_key=self.api_key)
        return self._client
    
    async def rate_limit(self):
        """Implement rate limiting to stay within 5 RPS limit."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()


async def expand_query_to_subquestions(query: str) -> List[str]:
    """Delegate to centralized LLM-based query expansion to ensure high-quality sub-questions."""
    return await expand_query_to_subquestions_llm(query)


async def scrape_url_content(url: str, max_chars: int = 2000) -> str:
    """Scrape content from URL to get more detailed information."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Limit length
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            return text
            
    except Exception as e:
        print(f"Failed to scrape {url}: {str(e)}")
        return ""


async def search_tavily(
    client: AsyncTavilyClient, 
    query: str, 
    max_results: int = 5,
    time_range: str = "month",
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None
) -> List[ResearchItem]:
    """Perform Tavily search and return structured results following best practices."""
    try:
        # Ensure query is under 400 characters (Tavily limit)
        if len(query) > 400:
            query = query[:397] + "..."
        
        # Build search parameters with optional domain filtering
        search_params = {
            "query": query,
            "search_depth": config.TAVILY_SEARCH_DEPTH,  # Configurable search depth
            "max_results": min(max_results, 10),  # Reasonable limit
            "include_raw_content": True,  # Better precision with advanced depth
            "include_answer": True,  # Get LLM-generated answer
            "time_range": time_range  # Configurable time range
        }
        
        # Add domain filtering if specified
        if include_domains:
            search_params["include_domains"] = include_domains
        if exclude_domains:
            search_params["exclude_domains"] = exclude_domains
        
        # Perform async search with timeout
        try:
            response = await asyncio.wait_for(
                client.search(**search_params),
                timeout=30  # 30 second timeout per search
            )
        except asyncio.TimeoutError:
            print(f"Tavily search timeout for query: {query[:50]}...")
            return []
        except Exception as api_error:
            print(f"Tavily API error for query '{query[:50]}...': {str(api_error)}")
            return []
        
        results = []
        for item in response.get("results", []):
            # Filter by relevance score (best practice)
            score = item.get("score", 0)
            if score < config.TAVILY_MIN_SCORE:  # Skip low-relevance results
                continue
            
            # Get basic snippet from Tavily
            basic_snippet = item.get("content", "")
            url = item.get("url", "")
            
            # Prepare scraping variables
            content_scraped = False
            scraping_error = None
            full_scraped_content = None
            scraped_content_length = 0
            
            print(f"🔍 DEBUG: Checking scraping for {url} with score {score}")
            # Use quality-based scraping decision instead of fixed threshold
            should_scrape = url and score >= config.TAVILY_SCRAPING_THRESHOLD
            if should_scrape:
                print(f"🚀 DEBUG: Attempting to scrape {url}")
                scraped_content = await scrape_url_content(url, max_chars=10000)  # Much higher limit for full content
                if scraped_content:
                    full_scraped_content = scraped_content
                    content_scraped = True
                    scraped_content_length = len(scraped_content)
                    print(f"✅ DEBUG: Successfully scraped {scraped_content_length} chars from {url}, content_scraped={content_scraped}")
                    print(f"🔍 DEBUG: Scraped content preview (first 200 chars): {scraped_content[:200]}...")
                    print(f"🔍 DEBUG: Full scraped content will be saved to scraped_content field")
                else:
                    scraping_error = "Failed to scrape content"
                    print(f"❌ DEBUG: Failed to scrape content from {url}, scraping_error={scraping_error}")
            else:
                threshold = config.TAVILY_SCRAPING_THRESHOLD
                print(f"⏭️  DEBUG: Skipping scraping for {url} (score {score:.2f} < {threshold} threshold or no URL)")
            
            research_item = ResearchItem(
                query_variant=query,
                source_url=url,
                title=item.get("title", ""),
                snippet=basic_snippet,  # Keep original snippet separate
                relevance_score=score,
                timestamp=now(),
                content_scraped=content_scraped,
                scraping_error=scraping_error,
                content_length=scraped_content_length,  # Length of scraped content only
                scraped_content=full_scraped_content,  # Full scraped content for report generation
                raw_content=full_scraped_content,  # Preserve exact raw scraped text
                raw_content_length=scraped_content_length
            )
            results.append(research_item)
        
        # Sort by relevance score (best practice)
        results.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        
        # Log quality summary for this search
        if results:
            scraped_count = sum(1 for r in results if r.content_scraped)
            avg_score = sum(r.relevance_score for r in results if r.relevance_score) / len([r for r in results if r.relevance_score])
            print(f"📈 TAVILY QUALITY: {len(results)} results, avg score: {avg_score:.2f}, {scraped_count} scraped ({scraped_count/len(results)*100:.1f}%)")
        
        return results
        
    except Exception as e:
        print(f"Tavily search error for query '{query[:50]}...': {str(e)}")
        # Return empty results on error
        return []


def clean_and_format_results(results: List[ResearchItem], original_query: str) -> List[ResearchItem]:
    """Clean and format research results using universal template."""
    cleaned_results = []
    
    for item in results:
        # Basic cleaning - remove excessive whitespace from snippet only (keep it short)
        cleaned_snippet = " ".join(item.snippet.split())
        if len(cleaned_snippet) > 500:
            cleaned_snippet = cleaned_snippet[:497] + "..."
        
        # Clean scraped content but DON'T truncate it - keep it full for report generation
        cleaned_scraped_content = None
        if item.scraped_content:
            # Just clean whitespace, but preserve full length
            cleaned_scraped_content = " ".join(item.scraped_content.split())
        
        # Create cleaned item - PRESERVE ALL SCRAPING METADATA AND FULL CONTENT
        cleaned_item = ResearchItem(
            query_variant=item.query_variant,
            source_url=item.source_url,
            title=item.title.strip(),
            snippet=cleaned_snippet,  # Short snippet for display
            relevance_score=item.relevance_score,
            timestamp=item.timestamp,
            # CRITICAL: Preserve scraping metadata
            content_scraped=item.content_scraped,
            scraping_error=item.scraping_error,
            content_length=item.content_length,
            scraped_content=cleaned_scraped_content,  # Full content for report generation (NOT truncated)
            # Preserve raw content and cleaning metadata
            raw_content=item.raw_content,
            raw_content_length=item.raw_content_length,
            content_cleaned=item.content_cleaned,
            original_content_length=item.original_content_length,
            cleaned_content_length=item.cleaned_content_length,
            metadata=item.metadata
        )
        cleaned_results.append(cleaned_item)
    
    return cleaned_results


# Create Tavily Research Agent with instrumentation
tavily_research_agent = Agent(
    model=OpenAIModel(config.RESEARCH_MODEL),
    deps_type=TavilyResearchDeps,
    output_type=ResearchPipelineModel,
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt=f"""
    You are a research coordination agent that processes raw Tavily API data into structured output.
    
    Timezone: America/Chicago (US Central)
    Current date: {today_str()}
    
    When asked to research something:
    1. Call your perform_tavily_research tool with the exact user query
    2. The tool returns raw data with enhanced content from URL scraping
    3. Convert this raw data into a ResearchPipelineModel with these exact fields:
       - original_query: use the original_query from tool
       - sub_queries: use the sub_queries from tool  
       - results: convert each item in raw_results to ResearchItem format
       - pipeline_type: set to "tavily"
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


@tavily_research_agent.tool
async def expand_query_intelligently(ctx: RunContext[TavilyResearchDeps], query: str) -> List[str]:
    """Tool to intelligently expand a query into 3 diverse sub-questions using LLM analysis.
    
    First analyzes the query type and context, then generates appropriate sub-questions
    that explore different aspects based on the query's nature (product, historical, news, etc.).
    """
    # This tool leverages the agent's LLM capabilities through the system prompt
    # The actual expansion logic is handled by the LLM based on the guidelines in the system prompt
    return await expand_query_to_subquestions(query)


@tavily_research_agent.tool
async def perform_tavily_research(ctx: RunContext[TavilyResearchDeps], query: str) -> ResearchPipelineModel:
    """Tool to perform comprehensive Tavily research and return ResearchPipelineModel."""
    try:
        print(f"🔍 TAVILY TOOL DEBUG: Starting research for query: {query}")
        
        if not ctx.deps.api_key:
            print(f"❌ TAVILY TOOL DEBUG: API key not configured")
            return ResearchPipelineModel(
                original_query=query,
                sub_queries=[],
                results=[],
                pipeline_type="tavily",
                total_results=0,
                processing_time=0.0
            )
        
        print(f"✅ TAVILY TOOL DEBUG: API key configured")
        # DEV-ONLY TRACING: record thresholds used for this run
        try:
            run_summary.set_thresholds(config.TAVILY_MIN_SCORE, config.GARBAGE_FILTER_THRESHOLD)
        except Exception:
            pass
        
        # Check if pre-generated sub-queries are provided in the query (centralized approach)
        # This prevents duplicate query expansion across multiple research APIs
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
            print(f"🎯 TAVILY TOOL DEBUG: Using {len(sub_questions)} pre-generated sub-queries from orchestrator")
            print(f"📝 Sub-queries: {sub_questions}")
        else:
            # CRITICAL FIX: Use single query as fallback instead of generating new sub-queries
            # This prevents the infinite loop that was causing 58+ API calls
            sub_questions = [query]
            print(f"🎯 TAVILY TOOL DEBUG: Using single query fallback (no pre-generated sub-queries found)")
        
        # Get reusable async client
        client = await ctx.deps.get_client()
        print(f"🔗 TAVILY TOOL DEBUG: Client created successfully")
        
        # Perform searches with rate limiting and optional bounded parallelism
        async def _one_search(q: str):
            await ctx.deps.rate_limit()
            return await search_tavily(
                client,
                q,
                ctx.deps.max_results,
                time_range=config.TAVILY_TIME_RANGE,
                exclude_domains=["pinterest.com", "quora.com"],
            )

        if config.RESEARCH_PARALLELISM_ENABLED:
            sem = asyncio.Semaphore(config.RESEARCH_MAX_CONCURRENCY)

            async def _bounded(q: str):
                async with sem:
                    return await _one_search(q)

            search_tasks = [_bounded(question) for question in sub_questions]
            # Use return_exceptions=True to handle failures gracefully (best practice)
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        else:
            search_tasks = [_one_search(question) for question in sub_questions]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        print(f"🔍 TAVILY TOOL DEBUG: Received {len(search_results)} search results")
        
        # Combine results
        all_results = []
        for i, results in enumerate(search_results):
            if isinstance(results, Exception):
                print(f"❌ TAVILY TOOL DEBUG: Sub-query {i+1} failed: {results}")
                continue
            if not results:
                continue
            all_results.extend(results)

        # DEV-ONLY TRACING: observe totals and PDF prevalence
        try:
            pdf_count = sum(1 for r in all_results if (r.source_url or '').lower().endswith('.pdf'))
            run_summary.observe_research_results(total=len(all_results), filtered_out=0, pdf_count=pdf_count)
            # If bounded concurrency enabled, record configured peak as a proxy
            if config.RESEARCH_PARALLELISM_ENABLED:
                run_summary.observe_research_concurrency(config.RESEARCH_MAX_CONCURRENCY)
        except Exception:
            pass
        
        print(f"📊 TAVILY TOOL DEBUG: Total combined results: {len(all_results)}")
        
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
                should_filter, filter_reason = content_filter.should_filter_content(
                    content=item.scraped_content,
                    url=item.source_url or "",
                    title=item.title or "",
                    quality_threshold=config.GARBAGE_FILTER_THRESHOLD  # Configurable threshold
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
                
                # Preserve full pre-filter content for raw logs; truncation handled by logging layer
                    
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
            print(f"🧹 Starting BATCHED content cleaning for {len(scraped_items)} Tavily results")
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
            print(f"⏭️ No scraped content to clean from Tavily results")
        
        # Clean and format results
        cleaned_results = clean_and_format_results(all_results, query)
        print(f"✨ TAVILY TOOL DEBUG: After cleaning: {len(cleaned_results)} results")
        
        # Store results in context for agent access
        ctx.deps.research_results = cleaned_results
        ctx.deps.sub_questions = sub_questions
        
        # CRITICAL FIX: Return ResearchPipelineModel instead of dict to prevent infinite agent loop
        return ResearchPipelineModel(
            original_query=query,
            sub_queries=sub_questions,
            results=cleaned_results,  # Already ResearchItem objects
            pipeline_type="tavily",
            total_results=len(cleaned_results),
            processing_time=0.0  # Will be calculated at agent level
        )
               
    except Exception as e:
        print(f"❌ TAVILY TOOL DEBUG: Exception caught: {str(e)}")
        print(f"❌ TAVILY TOOL DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"❌ TAVILY TOOL DEBUG: Traceback: {traceback.format_exc()}")
        return ResearchPipelineModel(
            original_query=query,
            sub_queries=[],
            results=[],
            pipeline_type="tavily",
            total_results=0,
            processing_time=0.0
        )


# DELETED: Legacy function removed - use tavily_research_agent Pydantic AI agent instead
