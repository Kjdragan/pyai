"""
Serper-based Research Agent for comprehensive search capabilities.
Uses Google Search via Serper API for high-quality research results.
"""

import asyncio
import httpx
from typing import List, Optional
from datetime import datetime
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from bs4 import BeautifulSoup

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
        "num": max_results,
        "hl": "en",
        "gl": "us"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Process organic results with intelligent quality grading
            raw_results = []
            for i, item in enumerate(data.get("organic", [])[:max_results]):
                basic_snippet = item.get("snippet", "")
                source_url = item.get("link", "")
                
                # Create initial research item for quality evaluation (no scraping yet)
                result = ResearchItem(
                    query_variant=query,
                    source_url=source_url,
                    title=item.get("title", ""),
                    snippet=basic_snippet,
                    relevance_score=None,  # Will be calculated by quality grader
                    timestamp=now(),
                    content_scraped=False,
                    scraping_error=None,
                    content_length=0,
                    scraped_content=None
                )
                raw_results.append(result)
            
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
                    scraped_content = await scrape_url_content(result.source_url, max_chars=10000)
                    
                    if scraped_content:
                        result.scraped_content = scraped_content
                        result.content_scraped = True
                        result.content_length = len(scraped_content)
                        # Preserve exact raw scraped text for quote retention analysis
                        result.raw_content = scraped_content
                        result.raw_content_length = len(scraped_content)
                        print(f"✅ SERPER DEBUG: Successfully scraped {result.content_length} chars from {result.source_url}")
                    else:
                        result.scraping_error = "Failed to scrape content"
                        print(f"❌ SERPER DEBUG: Failed to scrape content from {result.source_url}")
                else:
                    skip_reason = result.metadata.get('skip_reason', 'Quality threshold not met')
                    print(f"⏭️  SERPER DEBUG: Skipping scraping for {result.source_url} - {skip_reason}")
                
                final_results.append(result)
            
            # Log quality summary
            quality_summary = quality_grader.get_quality_summary(final_results)
            print(f"📈 SERPER QUALITY SUMMARY: {quality_summary}")
            
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
async def perform_serper_research(ctx: RunContext[SerperResearchDeps], query: str) -> dict:
    """Tool to perform comprehensive Serper research and return raw API data."""
    try:
        print(f"🔍 SERPER TOOL DEBUG: Starting research for query: {query}")
        
        if not ctx.deps.api_key:
            print(f"❌ SERPER TOOL DEBUG: API key not configured")
            return {
                "error": "Serper API key not configured",
                "original_query": query,
                "sub_queries": [],
                "raw_results": [],
                "processing_time": 0.0
            }
        
        print(f"✅ SERPER TOOL DEBUG: API key configured, current date: {ctx.deps.current_date}")
        
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
            print(f"🎯 SERPER TOOL DEBUG: Using {len(sub_questions)} pre-generated sub-queries from orchestrator")
            print(f"📝 Sub-queries: {sub_questions}")
        else:
            # Fallback: Generate sub-questions if not provided (maintain backward compatibility)
            sub_questions = await expand_query_to_subquestions(query)
            print(f"📝 SERPER TOOL DEBUG: Generated {len(sub_questions)} sub-questions: {sub_questions}")
        
        # Perform parallel searches with full result capacity per sub-query
        # This allows comprehensive research coverage instead of artificially limiting results
        search_tasks = [
            search_serper(question, ctx.deps.api_key, ctx.deps.max_results)
            for question in sub_questions
        ]
        
        # Execute searches in parallel
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        print(f"🔍 SERPER TOOL DEBUG: Received {len(search_results)} search results")
        
        # Combine results
        all_results = []
        for i, results in enumerate(search_results):
            if isinstance(results, list):
                print(f"📊 SERPER TOOL DEBUG: Search {i+1} returned {len(results)} results")
                all_results.extend(results)
            else:
                print(f"⚠️ SERPER TOOL DEBUG: Search {i+1} returned non-list: {type(results)}")
        
        print(f"🔢 SERPER TOOL DEBUG: Total combined results: {len(all_results)}")
        
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
                    quality_threshold=0.4  # Configurable threshold
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
        
        # Return raw research data for agent processing
        result_dict = {
            "original_query": query,
            "sub_queries": sub_questions,
            "raw_results": [result.model_dump() for result in cleaned_results],
            "processing_time": 0.0  # Will be calculated at agent level
        }
        print(f"🎯 SERPER TOOL DEBUG: Returning dict with {len(result_dict['raw_results'])} raw results")
        return result_dict
               
    except Exception as e:
        print(f"❌ SERPER TOOL DEBUG: Exception caught: {str(e)}")
        import traceback
        print(f"❌ SERPER TOOL DEBUG: Traceback: {traceback.format_exc()}")
        return {
            "error": f"Error performing Serper research: {str(e)}",
            "original_query": query,
            "sub_queries": [],
            "raw_results": [],
            "processing_time": 0.0
        }


async def process_serper_research_request(query: str) -> AgentResponse:
    """Process Serper research request."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        deps = SerperResearchDeps()
        result = await serper_research_agent.run(
            f"Use your perform_serper_research tool to conduct comprehensive research on: {query}. "
            f"Please search for real web sources and return structured results with actual URLs and data.",
            deps=deps
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return AgentResponse(
            agent_name="SerperResearchAgent",
            success=True,
            data=result.data.model_dump() if result.data else {},
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="SerperResearchAgent",
            success=False,
            error=str(e),
            processing_time=processing_time
        )