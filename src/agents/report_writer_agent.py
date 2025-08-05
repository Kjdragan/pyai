"""
Report Writer Agent for generating and refining reports from research or YouTube data.
Supports comprehensive, top-10, and summary report styles.
"""

import asyncio
from typing import Union, Dict, Any
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from datetime import datetime

from models import (
    ReportGenerationModel, ResearchPipelineModel, YouTubeTranscriptModel, 
    AgentResponse
)
from config import config


class ReportWriterDeps:
    """Dependencies for Report Writer Agent."""
    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT


def get_report_template(style: str, source_type: str) -> str:
    """Get report template based on style and source type."""
    templates = {
        "comprehensive": {
            "research": """
            Create a comprehensive research report with the following structure:
            
            # {title}
            
            ## Executive Summary
            [2-3 paragraph overview of key findings]
            
            ## Historical Context
            [Analysis of past developments and trends]
            
            ## Current State Analysis
            [Detailed examination of present situation]
            
            ## Future Outlook
            [Predictions and emerging trends]
            
            ## Key Insights
            [Bullet points of most important findings]
            
            ## Sources and References
            [List of sources used]
            
            ## Conclusion
            [Summary and implications]
            """,
            "youtube": """
            Create a comprehensive analysis of the YouTube content with this structure:
            
            # {title}
            
            ## Content Overview
            [Summary of the video's main topic and purpose]
            
            ## Key Points and Arguments
            [Detailed breakdown of main points discussed]
            
            ## Supporting Evidence
            [Examples, data, or evidence presented]
            
            ## Critical Analysis
            [Your analysis of the content's validity and significance]
            
            ## Actionable Insights
            [Practical takeaways for the audience]
            
            ## Conclusion
            [Overall assessment and recommendations]
            """
        },
        "top_10": {
            "research": """
            Create a top-10 insights report:
            
            # Top 10 Key Insights: {title}
            
            ## 1. [Most Important Finding]
            [Brief explanation and significance]
            
            ## 2. [Second Most Important]
            [Brief explanation and significance]
            
            [Continue for all 10 insights...]
            
            ## Summary
            [Brief overview of implications]
            """,
            "youtube": """
            Create a top-10 takeaways from the video:
            
            # Top 10 Takeaways: {title}
            
            ## 1. [Most Important Point]
            [Brief explanation and context]
            
            ## 2. [Second Most Important]
            [Brief explanation and context]
            
            [Continue for all 10 takeaways...]
            
            ## Action Items
            [What viewers should do with this information]
            """
        },
        "summary": {
            "research": """
            Create a concise summary report:
            
            # Research Summary: {title}
            
            ## Overview
            [1-2 paragraph summary of the research topic]
            
            ## Key Findings
            • [Finding 1]
            • [Finding 2]
            • [Finding 3]
            
            ## Implications
            [What this means and why it matters]
            
            ## Next Steps
            [Recommended actions or further research]
            """,
            "youtube": """
            Create a concise video summary:
            
            # Video Summary: {title}
            
            ## Main Topic
            [What the video is about]
            
            ## Key Points
            • [Point 1]
            • [Point 2]
            • [Point 3]
            
            ## Takeaways
            [What viewers should remember]
            
            ## Recommended Actions
            [What to do with this information]
            """
        }
    }
    
    return templates.get(style, {}).get(source_type, templates["summary"][source_type])


async def generate_report_draft(
    data: Union[ResearchPipelineModel, YouTubeTranscriptModel],
    style: str,
    template: str
) -> str:
    """Generate initial report draft."""
    
    # Create content-specific generation agent with instrumentation
    generation_agent = Agent(
        OpenAIModel(config.DEFAULT_MODEL),
        instrument=True,  # Enable Pydantic AI tracing
        system_prompt=f"""
        You are an expert report writer. Generate a {style} report using the provided template.
        
        Guidelines:
        - Follow the template structure exactly
        - Use clear, professional language
        - Include specific details from the source data
        - Make insights actionable and relevant
        - Ensure proper flow between sections
        
        Template to follow:
        {template}
        """,
        retries=2
    )
    
    if isinstance(data, ResearchPipelineModel):
        # Research-based report
        content_summary = f"""
        Research Query: {data.original_query}
        Sub-queries: {', '.join(data.sub_queries)}
        Total Results: {data.total_results}
        
        Research Results:
        """
        for item in data.results[:10]:  # Limit to top 10 results
            # Use full scraped content if available, otherwise fall back to snippet
            content_to_use = item.scraped_content if (item.content_scraped and item.scraped_content) else item.snippet
            # USE FULL CONTENT WITHOUT ANY TRUNCATION for maximum report quality
            
            # Add scraping status indicator
            scraping_status = " [FULL CONTENT]" if item.content_scraped else " [SNIPPET ONLY]"
            content_summary += f"\n- {item.title}{scraping_status}: {content_to_use}"
        
        title = data.original_query
        
    else:  # YouTubeTranscriptModel
        # YouTube-based report
        content_summary = f"""
        Video URL: {data.url}
        Transcript Length: {len(data.transcript)} characters
        
        Video Content:
        {data.transcript[:2000]}...
        """
        title = data.metadata.get("title", "YouTube Video Analysis")
    
    prompt = f"""
    Generate a {style} report based on this content:
    
    {content_summary}
    
    Use "{title}" as the main title.
    Follow the template structure provided in your system prompt.
    """
    
    result = await generation_agent.run(prompt)
    return result.data


async def refine_report(draft: str, style: str) -> str:
    """Refine and edit the report draft."""
    
    refinement_agent = Agent(
        OpenAIModel(config.DEFAULT_MODEL),
        instrument=True,  # Enable Pydantic AI tracing
        system_prompt=f"""
        You are an expert editor. Your job is to refine and improve the provided {style} report.
        
        Focus on:
        - Clarity and readability
        - Logical flow and structure
        - Grammar and style consistency
        - Factual accuracy and coherence
        - Professional tone
        
        Return the improved version of the report.
        """,
        retries=2
    )
    
    result = await refinement_agent.run(f"Please refine and improve this {style} report:\n\n{draft}")
    return result.data


# Create Report Writer Agent with instrumentation
report_writer_agent = Agent(
    model=OpenAIModel(config.REPORT_MODEL),
    deps_type=ReportWriterDeps,
    output_type=ReportGenerationModel,
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt="""
    You are a professional report writer agent. Your job is to:
    1. Ingest research data or YouTube transcript data
    2. Generate reports in specified styles (comprehensive, top-10, summary)
    3. Apply synthesis and editing loops to refine the output
    4. Return high-quality, structured reports
    
    Always follow the appropriate template for the requested style and source type.
    Ensure reports are well-structured, insightful, and actionable.
    """,
    retries=config.MAX_RETRIES
)


@report_writer_agent.tool
async def generate_report(
    ctx: RunContext[ReportWriterDeps], 
    data_json: str, 
    style: str, 
    source_type: str
) -> str:
    """Tool to generate a report from research or YouTube data."""
    try:
        # Get appropriate template
        template = get_report_template(style, source_type)
        
        return f"Successfully generated {style} report template for {source_type} data. " \
               f"Template includes {len(template.split('##'))} main sections. " \
               f"Ready to process data and generate draft."
               
    except Exception as e:
        return f"Error generating report: {str(e)}"


async def process_report_request(
    data: Union[ResearchPipelineModel, YouTubeTranscriptModel],
    style: str = "summary"
) -> AgentResponse:
    """Process report generation request."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Determine source type
        source_type = "research" if isinstance(data, ResearchPipelineModel) else "youtube"
        
        # Get template
        template = get_report_template(style, source_type)
        
        # Generate draft
        draft = await generate_report_draft(data, style, template)
        
        # Refine the draft
        final_report = await refine_report(draft, style)
        
        # Count words
        word_count = len(final_report.split())
        
        # Create result model
        result = ReportGenerationModel(
            style=style,
            prompt_template=template,
            draft=draft,
            final=final_report,
            source_type=source_type,
            word_count=word_count,
            generation_time=asyncio.get_event_loop().time() - start_time
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return AgentResponse(
            agent_name="ReportWriterAgent",
            success=True,
            data=result.model_dump(),
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="ReportWriterAgent",
            success=False,
            error=str(e),
            processing_time=processing_time
        )
