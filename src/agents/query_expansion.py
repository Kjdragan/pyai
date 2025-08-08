"""
Query expansion utilities for research agents.

This module provides sophisticated query expansion capabilities using few-shot examples
and LLM-based generation to create diverse sub-questions that capture the full
scope of the original query.
"""

import asyncio
from typing import List
from datetime import datetime
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from config import config
from models import ResearchPipelineModel


class QueryExpansionDeps:
    """Dependencies for query expansion."""
    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT


# Create a specialized agent for query expansion
query_expansion_agent = Agent(
    model=OpenAIModel(config.RESEARCH_MODEL),
    deps_type=QueryExpansionDeps,
    output_type=List[str],
    system_prompt="""
    You are a query expansion expert that generates diverse sub-questions to fully explore a topic.
    
    Your task is to expand a given query into exactly 3 diverse sub-questions that together 
    capture the full scope and potential intent of the original query.
    
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


@query_expansion_agent.tool
async def generate_subquestions(ctx: RunContext[QueryExpansionDeps], query: str) -> List[str]:
    """Tool to generate sub-questions for a given query."""
    # This is a placeholder - in a real implementation, this would contain
    # the logic to generate sub-questions, but the agent handles this via the system prompt
    return []


async def expand_query_to_subquestions(query: str) -> List[str]:
    """Expand user query into 3 diverse sub-questions using LLM-based generation.
    
    This function uses an LLM with few-shot examples to generate sub-questions
    that cover different aspects of the original query including technical,
    practical, comparative, and contextual dimensions.
    """
    try:
        # Use the agent to generate sub-questions
        result = await query_expansion_agent.run(query)
        return result.data
    except Exception as e:
        # Fallback to deterministic approach if LLM fails
        print(f"⚠️  Query expansion failed, using fallback approach: {e}")
        current_year = datetime.now().year
        return [
            f"{query} - technical aspects, mechanisms, and implementation approaches {current_year}",
            f"{query} - practical applications, industry adoption, and real-world case studies {current_year}",
            f"{query} - comparative analysis, limitations, and future challenges {current_year}"
        ]
