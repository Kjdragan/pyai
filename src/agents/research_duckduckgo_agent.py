"""
Research Pipeline 2: DuckDuckGo MCP-based research agent.
Expands queries into 3 sub-questions and uses Pydantic-AI's MCP client.
"""

import asyncio
from typing import List
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from datetime import datetime
import httpx
import json

from models import ResearchPipelineModel, ResearchItem, AgentResponse
from config import config


class DuckDuckGoResearchDeps:
    """Dependencies for DuckDuckGo Research Agent."""
    def __init__(self):
        self.timeout = config.RESEARCH_TIMEOUT
        self.max_results = config.MAX_RESEARCH_RESULTS


async def expand_query_to_subquestions(query: str) -> List[str]:
    """Expand user query into 3 sub-questions (past, present, future)."""
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


async def search_duckduckgo_instant(query: str, max_results: int = 5) -> List[ResearchItem]:
    """
    Perform DuckDuckGo search using instant answer API.
    Note: This is a simplified implementation. In production, you'd use the actual MCP client.
    """
    try:
        # DuckDuckGo Instant Answer API (free, no auth required)
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        
        results = []
        
        # Process abstract if available
        if data.get("Abstract"):
            results.append(ResearchItem(
                query_variant=query,
                source_url=data.get("AbstractURL"),
                title=data.get("AbstractSource", "DuckDuckGo Abstract"),
                snippet=data.get("Abstract"),
                relevance_score=1.0,
                timestamp=datetime.now()
            ))
        
        # Process related topics
        for topic in data.get("RelatedTopics", [])[:max_results-1]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(ResearchItem(
                    query_variant=query,
                    source_url=topic.get("FirstURL"),
                    title=topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else "Related Topic",
                    snippet=topic.get("Text", ""),
                    relevance_score=0.8,
                    timestamp=datetime.now()
                ))
        
        # If no results, create a placeholder
        if not results:
            results.append(ResearchItem(
                query_variant=query,
                source_url=None,
                title=f"Search: {query}",
                snippet=f"No specific results found for: {query}",
                relevance_score=0.1,
                timestamp=datetime.now()
            ))
        
        return results[:max_results]
        
    except Exception as e:
        # Return error result
        return [ResearchItem(
            query_variant=query,
            source_url=None,
            title=f"Search Error: {query}",
            snippet=f"Error searching for {query}: {str(e)}",
            relevance_score=0.0,
            timestamp=datetime.now()
        )]


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


# Create DuckDuckGo Research Agent
duckduckgo_research_agent = Agent(
    model=OpenAIModel(config.RESEARCH_MODEL),
    deps_type=DuckDuckGoResearchDeps,
    output_type=ResearchPipelineModel,
    system_prompt="""
    You are a research coordination agent using DuckDuckGo search. Your job is to:
    1. Expand user queries into 3 focused sub-questions (past, present, future)
    2. Perform parallel searches using DuckDuckGo API
    3. Clean and structure the results using a universal research template
    4. Return comprehensive research data
    
    Always validate search queries and handle API errors gracefully.
    Focus on finding high-quality, relevant sources for each sub-question.
    """,
    retries=config.MAX_RETRIES
)


@duckduckgo_research_agent.tool
async def perform_duckduckgo_research(ctx: RunContext[DuckDuckGoResearchDeps], query: str) -> str:
    """Tool to perform comprehensive DuckDuckGo research."""
    try:
        # Expand query into sub-questions
        sub_questions = await expand_query_to_subquestions(query)
        
        # Perform parallel searches
        search_tasks = [
            search_duckduckgo_instant(question, ctx.deps.max_results // 3)
            for question in sub_questions
        ]
        
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Combine results
        all_results = []
        for results in search_results:
            if isinstance(results, list):
                all_results.extend(results)
        
        return f"Successfully completed DuckDuckGo research for query: {query}. " \
               f"Generated {len(sub_questions)} sub-questions. " \
               f"Found {len(all_results)} total results."
               
    except Exception as e:
        return f"Error performing DuckDuckGo research: {str(e)}"


async def process_duckduckgo_research_request(query: str) -> AgentResponse:
    """Process DuckDuckGo research request."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        deps = DuckDuckGoResearchDeps()
        
        # Expand query into sub-questions
        sub_questions = await expand_query_to_subquestions(query)
        
        # Perform parallel searches
        search_tasks = [
            search_duckduckgo_instant(question, deps.max_results // 3)
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
            pipeline_type="duckduckgo",
            total_results=len(cleaned_results),
            processing_time=asyncio.get_event_loop().time() - start_time
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return AgentResponse(
            agent_name="DuckDuckGoResearchAgent",
            success=True,
            data=result.model_dump(),
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="DuckDuckGoResearchAgent",
            success=False,
            error=str(e),
            processing_time=processing_time
        )
