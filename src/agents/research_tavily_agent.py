"""
Research Pipeline 1: Tavily-based research agent.
Expands queries into 3 sub-questions and performs parallel searches.
"""

import asyncio
from typing import List
from tavily import TavilyClient
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from datetime import datetime

from models import ResearchPipelineModel, ResearchItem, AgentResponse
from config import config


class TavilyResearchDeps:
    """Dependencies for Tavily Research Agent."""
    def __init__(self):
        self.api_key = config.TAVILY_API_KEY
        self.timeout = config.RESEARCH_TIMEOUT
        self.max_results = config.MAX_RESEARCH_RESULTS


async def expand_query_to_subquestions(query: str) -> List[str]:
    """Expand user query into 3 sub-questions (past, present, future)."""
    # Create a simple agent for query expansion
    expansion_agent = Agent(
        OpenAIModel(config.DEFAULT_MODEL),
        system_prompt="""
        You are a research query expansion specialist. Given a user query, 
        expand it into exactly 3 focused sub-questions that cover:
        1. Historical/past perspective
        2. Current/present state
        3. Future trends/predictions
        
        Return only the 3 questions, one per line, without numbering or bullets.
        Make each question specific and searchable.
        """,
        retries=2
    )
    
    result = await expansion_agent.run(
        f"Expand this query into 3 sub-questions (past, present, future): {query}"
    )
    
    # Parse the result into 3 questions
    questions = [q.strip() for q in result.data.split('\n') if q.strip()]
    
    # Ensure we have exactly 3 questions
    if len(questions) < 3:
        questions.extend([
            f"Historical context of {query}",
            f"Current state of {query}",
            f"Future trends in {query}"
        ])
    
    return questions[:3]


async def search_tavily(client: TavilyClient, query: str, max_results: int = 5) -> List[ResearchItem]:
    """Perform Tavily search and return structured results following best practices."""
    try:
        # Ensure query is under 400 characters (Tavily limit)
        if len(query) > 400:
            query = query[:397] + "..."
        
        # Perform search with optimized parameters
        response = client.search(
            query=query,
            search_depth="advanced",  # 10 credits but better quality
            max_results=min(max_results, 10),  # Reasonable limit
            include_raw_content=True,  # Better precision with advanced depth
            include_answer=True,  # Get LLM-generated answer
            time_range="month"  # Focus on recent content
        )
        
        results = []
        for item in response.get("results", []):
            # Filter by relevance score (best practice)
            score = item.get("score", 0)
            if score < 0.5:  # Skip low-relevance results
                continue
                
            research_item = ResearchItem(
                query_variant=query,
                source_url=item.get("url"),
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                relevance_score=score,
                timestamp=datetime.now()
            )
            results.append(research_item)
        
        # Sort by relevance score (best practice)
        results.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        
        return results
        
    except Exception as e:
        # Return empty results on error
        return []


def clean_and_format_results(results: List[ResearchItem], original_query: str) -> List[ResearchItem]:
    """Clean and format research results using universal template."""
    cleaned_results = []
    
    for item in results:
        # Basic cleaning - remove excessive whitespace, truncate if too long
        cleaned_snippet = " ".join(item.snippet.split())
        if len(cleaned_snippet) > 500:
            cleaned_snippet = cleaned_snippet[:497] + "..."
        
        # Create cleaned item
        cleaned_item = ResearchItem(
            query_variant=item.query_variant,
            source_url=item.source_url,
            title=item.title.strip(),
            snippet=cleaned_snippet,
            relevance_score=item.relevance_score,
            timestamp=item.timestamp
        )
        cleaned_results.append(cleaned_item)
    
    return cleaned_results


# Create Tavily Research Agent
tavily_research_agent = Agent(
    model=OpenAIModel(config.RESEARCH_MODEL),
    deps_type=TavilyResearchDeps,
    output_type=ResearchPipelineModel,
    system_prompt="""
    You are a research coordination agent using Tavily search. Your job is to:
    1. Expand user queries into 3 focused sub-questions (past, present, future)
    2. Perform parallel searches using Tavily API
    3. Clean and structure the results using a universal research template
    4. Return comprehensive research data
    
    Always validate search queries and handle API errors gracefully.
    Focus on finding high-quality, relevant sources for each sub-question.
    """,
    retries=config.MAX_RETRIES
)


@tavily_research_agent.tool
async def perform_tavily_research(ctx: RunContext[TavilyResearchDeps], query: str) -> str:
    """Tool to perform comprehensive Tavily research."""
    try:
        if not ctx.deps.api_key:
            return "Error: Tavily API key not configured"
        
        # Expand query into sub-questions
        sub_questions = await expand_query_to_subquestions(query)
        
        # Initialize Tavily client
        client = TavilyClient(api_key=ctx.deps.api_key)
        
        # Perform parallel searches with proper error handling
        search_tasks = [
            search_tavily(client, question, max(1, ctx.deps.max_results // len(sub_questions)))
            for question in sub_questions
        ]
        
        # Use return_exceptions=True to handle failures gracefully (best practice)
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Combine results
        all_results = []
        for results in search_results:
            if isinstance(results, list):
                all_results.extend(results)
        
        return f"Successfully completed Tavily research for query: {query}. " \
               f"Generated {len(sub_questions)} sub-questions. " \
               f"Found {len(all_results)} total results."
               
    except Exception as e:
        return f"Error performing Tavily research: {str(e)}"


async def process_tavily_research_request(query: str) -> AgentResponse:
    """Process Tavily research request."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        deps = TavilyResearchDeps()
        
        if not deps.api_key:
            return AgentResponse(
                agent_name="TavilyResearchAgent",
                success=False,
                error="Tavily API key not configured"
            )
        
        # Expand query into sub-questions
        sub_questions = await expand_query_to_subquestions(query)
        
        # Initialize Tavily client
        client = TavilyClient(api_key=deps.api_key)
        
        # Perform parallel searches
        search_tasks = [
            search_tavily(client, question, deps.max_results // 3)
            for question in sub_questions
        ]
        
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Combine and clean results
        all_results = []
        for results in search_results:
            if isinstance(results, list):
                all_results.extend(results)
        
        cleaned_results = clean_and_format_results(all_results, query)
        
        # Create result model
        result = ResearchPipelineModel(
            original_query=query,
            sub_queries=sub_questions,
            results=cleaned_results,
            pipeline_type="tavily",
            total_results=len(cleaned_results),
            processing_time=asyncio.get_event_loop().time() - start_time
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return AgentResponse(
            agent_name="TavilyResearchAgent",
            success=True,
            data=result.model_dump(),
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="TavilyResearchAgent",
            success=False,
            error=str(e),
            processing_time=processing_time
        )
