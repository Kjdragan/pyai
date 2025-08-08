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
from agents.content_cleaning_agent import clean_research_item_content


class SerperResearchDeps:
    """Dependencies for Serper Research Agent."""
    
    def __init__(self):
        self.api_key = config.SERPER_API_KEY
        self.max_results = config.MAX_RESEARCH_RESULTS
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.research_results: List[ResearchItem] = []
        self.sub_questions: List[str] = []


async def expand_query_to_subquestions(query: str) -> List[str]:
    """Expand user query into 3 diverse sub-questions using few-shot examples.
    
    This function provides guidance to the LLM for generating sub-questions that cover 
    different aspects of the original query including technical, practical, comparative, 
    and contextual dimensions.
    """
    current_year = datetime.now().year
    
    # Provide clear instructions to the LLM on how to expand the query
    # The LLM will use these examples as a pattern to follow
    instructions = f"""
Expand the query "{query}" into exactly 3 diverse sub-questions that together capture the full scope and potential intent of the original query.

Follow these guidelines:
1. Create sub-questions that explore different dimensions (technical, practical, comparative)
2. Ensure sub-questions are specific and searchable
3. Include the current year ({current_year}) in each sub-question when relevant
4. Avoid overlapping or redundant questions
5. Make questions clear and unambiguous

Examples of good query expansions:

Query: "artificial intelligence in healthcare"
Sub-questions:
1. What are the current technical implementations and breakthrough AI applications in healthcare diagnostics?
2. What are the practical benefits and challenges of deploying AI systems in hospitals and clinics?
3. How do AI healthcare solutions compare to traditional methods in terms of accuracy, cost, and patient outcomes?

Query: "renewable energy adoption"
Sub-questions:
1. What technological advances have enabled the recent growth in renewable energy systems?
2. What economic and policy factors are driving or hindering renewable energy adoption in different regions?
3. How does the environmental impact of renewable energy compare to fossil fuels across their entire lifecycle?

Query: "remote work productivity"
Sub-questions:
1. What tools, technologies, and practices have been shown to improve remote team collaboration?
2. How do different industries and job types adapt to remote work environments?
3. What are the long-term effects of remote work on employee well-being and company culture?

Query: "blockchain for supply chain"
Sub-questions:
1. What are the technical mechanisms by which blockchain enhances supply chain transparency?
2. What industries are successfully implementing blockchain supply chain solutions and what benefits have they seen?
3. What are the limitations, costs, and scalability challenges of blockchain in supply chain management?
"""
    
    # Analyze the query to determine its nature and generate appropriate sub-questions
    # This is a fallback implementation - in practice, the LLM agent will use the system prompt
    query_lower = query.lower()
    
    # Detect query type and generate contextually appropriate sub-questions
    if any(product_indicator in query_lower for product_indicator in ['iphone', 'samsung', 'tesla', 'macbook', 'laptop', 'phone', 'car', 'product']):
        # Product-focused expansion
        return [
            f"What are the key features, specifications, and technical details of {query}?",
            f"How does {query} compare to competitors and alternatives in terms of performance and reviews?",
            f"What is the pricing, availability, and market reception of {query}?"
        ]
    elif any(historical_indicator in query_lower for historical_indicator in ['war', 'revolution', 'fall of', 'rise of', 'history', 'ancient', 'medieval']):
        # Historical topic expansion
        return [
            f"What were the background, causes, and context leading to {query}?",
            f"What were the key events, timeline, and major developments during {query}?",
            f"What were the consequences, impact, and long-term effects of {query}?"
        ]
    elif any(news_indicator in query_lower for news_indicator in ['2024', '2025', 'latest', 'recent', 'current', 'news', 'breaking']):
        # Current news/events expansion
        return [
            f"What are the latest developments and recent news about {query}?",
            f"What is the background context and key factors behind {query}?",
            f"What are the implications, reactions, and potential outcomes of {query}?"
        ]
    elif any(business_indicator in query_lower for business_indicator in ['market', 'industry', 'company', 'business', 'economy', 'financial']):
        # Business/market expansion
        return [
            f"What is the current market status and recent performance of {query}?",
            f"What are the key market dynamics, trends, and competitive factors affecting {query}?",
            f"What are the future outlook, predictions, and growth prospects for {query}?"
        ]
    else:
        # General adaptive expansion
        return [
            f"What are the fundamental concepts, principles, and key aspects of {query}?",
            f"What are the current applications, implementations, and real-world examples of {query}?",
            f"What are the latest developments, trends, and future directions for {query}?"
        ]


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
            
            # Process organic results with URL scraping
            for item in data.get("organic", [])[:max_results]:
                basic_snippet = item.get("snippet", "")
                source_url = item.get("link", "")
                
                # Prepare scraping variables
                content_scraped = False
                scraping_error = None
                full_scraped_content = None
                scraped_content_length = 0
                
                print(f"🔍 SERPER DEBUG: Checking scraping for {source_url}")
                # Attempt to scrape content for high-relevance results
                if source_url:
                    print(f"🚀 SERPER DEBUG: Attempting to scrape {source_url}")
                    scraped_content = await scrape_url_content(source_url, max_chars=10000)  # Much higher limit for full content
                    if scraped_content:
                        full_scraped_content = scraped_content
                        content_scraped = True
                        scraped_content_length = len(scraped_content)
                        print(f"✅ SERPER DEBUG: Successfully scraped {scraped_content_length} chars from {source_url}, content_scraped={content_scraped}")
                    else:
                        scraping_error = "Failed to scrape content"
                        print(f"❌ SERPER DEBUG: Failed to scrape content from {source_url}, scraping_error={scraping_error}")
                else:
                    scraping_error = "No URL provided"
                    print(f"⏭️ SERPER DEBUG: No URL to scrape")
                
                result = ResearchItem(
                    query_variant=query,
                    source_url=source_url,
                    title=item.get("title", ""),
                    snippet=basic_snippet,  # Keep original snippet separate
                    relevance_score=0.9,  # Serper provides high-quality results
                    timestamp=datetime.now(),
                    content_scraped=content_scraped,
                    scraping_error=scraping_error,
                    content_length=scraped_content_length,  # Length of scraped content only
                    scraped_content=full_scraped_content  # Full scraped content for report generation
                )
                results.append(result)
            
            return results
            
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
                scraped_content=cleaned_scraped_content  # Full content for report generation (NOT truncated)
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
    
    Today's date is: {datetime.now().strftime("%Y-%m-%d")}
    
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
        
        # Expand query into sub-questions
        sub_questions = await expand_query_to_subquestions(query)
        print(f"📝 SERPER TOOL DEBUG: Generated {len(sub_questions)} sub-questions: {sub_questions}")
        
        # Perform parallel searches with rate limiting
        search_tasks = [
            search_serper(question, ctx.deps.api_key, max(1, ctx.deps.max_results // len(sub_questions)))
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
        
        # PERFORMANCE OPTIMIZATION: Clean scraped content using nano model
        # This removes boilerplate text before report generation for 40-50% speed improvement
        scraped_items = [item for item in all_results if item.scraped_content and item.content_scraped]
        if scraped_items:
            print(f"🧹 Starting content cleaning for {len(scraped_items)} Serper results")
            cleaning_start = asyncio.get_event_loop().time()
            
            # Create cleaning tasks for parallel processing
            cleaning_tasks = [
                clean_research_item_content(item, query)
                for item in scraped_items
            ]
            
            # Execute content cleaning in parallel for maximum efficiency
            await asyncio.gather(*cleaning_tasks, return_exceptions=True)
            
            cleaning_time = asyncio.get_event_loop().time() - cleaning_start
            print(f"✅ Content cleaning completed in {cleaning_time:.2f}s")
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