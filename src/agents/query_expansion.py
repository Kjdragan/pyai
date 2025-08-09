"""
Query expansion utilities for research agents.

This module provides sophisticated query expansion capabilities using few-shot examples
and LLM-based generation to create diverse sub-questions that capture the full
scope of the original query.
"""

import asyncio
from typing import List
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from config import config
from models import ResearchPipelineModel
from utils.time_provider import today_str, current_year


class QueryExpansionDeps:
    """Dependencies for query expansion."""
    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT


# Create a specialized agent for query expansion
query_expansion_agent = Agent(
    model=OpenAIModel(config.RESEARCH_MODEL),
    deps_type=QueryExpansionDeps,
    output_type=List[str],
    system_prompt=f"""
    You are a query expansion expert that generates diverse sub-questions to fully explore a topic.
    
    Your task is to expand a given query into exactly 3 diverse sub-questions that together 
    capture the full scope and potential intent of the original query.
    
    Current date: {today_str()}
    
    Guidelines:
    1. Create sub-questions that explore different dimensions (technical, practical, comparative)
    2. Ensure sub-questions are specific and searchable
    3. Include the current year in each sub-question when relevant
    4. Avoid overlapping or redundant questions
    5. Make questions clear and unambiguous
    
    Examples:
    
    Query: "artificial intelligence in healthcare"
    Sub-questions:
    1. What are the current technical implementations and breakthrough AI applications in healthcare diagnostics?
    2. What are the practical benefits and challenges of deploying AI systems in hospitals and clinics?
    3. How do AI healthcare solutions compare to traditional methods in terms to accuracy, cost, and patient outcomes?
    
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
    """,
    instrument=True,  # Enable Pydantic AI tracing
    retries=config.MAX_RETRIES
)



async def expand_query_to_subquestions(query: str) -> List[str]:
    """Expand user query into 3 diverse sub-questions using Pydantic AI structured output."""
    try:
        # Use the existing Pydantic AI agent that's properly configured for structured output
        deps = QueryExpansionDeps()
        
        # Run the agent with the query - it will return List[str] due to output_type
        result = await query_expansion_agent.run(
            f"Expand this query into exactly 3 diverse sub-questions: {query}",
            deps=deps
        )
        
        # The agent returns structured List[str] output
        if result and result.data and isinstance(result.data, list):
            return result.data[:3]  # Ensure exactly 3 questions
        else:
            raise Exception(f"Agent returned invalid output format: {type(result.data)}")
            
    except Exception as e:
        # NO FALLBACK - let it fail properly so Pydantic AI retry mechanism can work
        raise Exception(f"Query expansion failed: {e}")
