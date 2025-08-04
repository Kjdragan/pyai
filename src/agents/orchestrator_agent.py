"""
Orchestrator Agent - Central coordinator for the multi-agent system.
Dispatches jobs to specialized agents and aggregates results.
"""

import asyncio
import uuid
from typing import Dict, Any, AsyncGenerator
from datetime import datetime
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from models import (
    JobRequest, MasterOutputModel, StreamingUpdate, AgentResponse,
    YouTubeTranscriptModel, WeatherModel, ResearchPipelineModel, 
    ReportGenerationModel
)
from config import config
from agents.youtube_agent import process_youtube_request
from agents.weather_agent import process_weather_request
from agents.research_tavily_agent import process_tavily_research_request
from agents.research_duckduckgo_agent import process_duckduckgo_research_request
from agents.report_writer_agent import process_report_request


class OrchestratorDeps:
    """Dependencies for Orchestrator Agent."""
    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT
        self.orchestrator_id = str(uuid.uuid4())


def parse_job_request(user_input: str) -> JobRequest:
    """Parse user input into a structured job request."""
    user_input_lower = user_input.lower()
    
    # Determine job type based on keywords (order matters - most specific first)
    if any(keyword in user_input_lower for keyword in ["youtube", "video", "transcript"]):
        job_type = "youtube"
    elif any(keyword in user_input_lower for keyword in ["weather", "forecast", "temperature"]):
        job_type = "weather"
    elif any(keyword in user_input_lower for keyword in ["report", "generate report", "write", "create", "comprehensive analysis", "summary of"]):
        job_type = "report"
    elif any(keyword in user_input_lower for keyword in ["research", "search", "find", "investigate"]):
        job_type = "research"
    else:
        # Default to research for general queries
        job_type = "research"
    
    # Extract report style if mentioned
    report_style = "summary"  # default
    if "comprehensive" in user_input_lower:
        report_style = "comprehensive"
    elif "top" in user_input_lower and ("10" in user_input_lower or "ten" in user_input_lower):
        report_style = "top_10"
    
    return JobRequest(
        job_type=job_type,
        query=user_input,
        report_style=report_style
    )


async def stream_update(update: StreamingUpdate) -> None:
    """Stream an update (placeholder for actual streaming implementation)."""
    # In a real implementation, this would send to the Streamlit UI
    print(f"[{update.timestamp}] {update.agent_name}: {update.message}")


# Create Orchestrator Agent
orchestrator_agent = Agent(
    model=OpenAIModel(config.ORCHESTRATOR_MODEL),
    deps_type=OrchestratorDeps,
    output_type=MasterOutputModel,
    system_prompt="""
    You are the Orchestrator Agent for a multi-agent system. Your responsibilities:
    
    1. Parse user requests and determine which agents to dispatch to
    2. Coordinate execution of specialized agents (YouTube, Weather, Research, Report Writer)
    3. Stream progress updates to the user interface
    4. Aggregate all results into a comprehensive MasterOutputModel
    5. Handle errors gracefully and provide meaningful feedback
    
    Available agents:
    - YouTubeAgent: Fetch video transcripts and metadata
    - WeatherAgent: Get current weather and forecasts
    - TavilyResearchAgent: Research using Tavily API
    - DuckDuckGoResearchAgent: Research using DuckDuckGo
    - ReportWriterAgent: Generate reports from research or YouTube data
    
    Always provide status updates and handle partial failures gracefully.
    """,
    retries=config.MAX_RETRIES
)


@orchestrator_agent.tool
async def dispatch_to_youtube_agent(ctx: RunContext[OrchestratorDeps], url: str) -> str:
    """Dispatch job to YouTube agent."""
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Dispatching YouTube transcript request for: {url}"
        ))
        
        response = await process_youtube_request(url)
        
        if response.success:
            return f"YouTube agent completed successfully. Retrieved transcript with {len(response.data.get('transcript', ''))} characters."
        else:
            return f"YouTube agent failed: {response.error}"
            
    except Exception as e:
        return f"Error dispatching to YouTube agent: {str(e)}"


@orchestrator_agent.tool
async def dispatch_to_weather_agent(ctx: RunContext[OrchestratorDeps], location: str) -> str:
    """Dispatch job to Weather agent."""
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Fetching weather data for: {location}"
        ))
        
        response = await process_weather_request(location)
        
        if response.success:
            return f"Weather agent completed successfully. Retrieved current weather and forecast for {location}."
        else:
            return f"Weather agent failed: {response.error}"
            
    except Exception as e:
        return f"Error dispatching to Weather agent: {str(e)}"


@orchestrator_agent.tool
async def dispatch_to_research_agents(ctx: RunContext[OrchestratorDeps], query: str, pipeline: str = "both") -> str:
    """Dispatch job to research agents (Tavily and/or DuckDuckGo)."""
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Starting research for: {query}"
        ))
        
        results = []
        
        if pipeline in ["tavily", "both"]:
            tavily_response = await process_tavily_research_request(query)
            results.append(("Tavily", tavily_response))
        
        if pipeline in ["duckduckgo", "both"]:
            ddg_response = await process_duckduckgo_research_request(query)
            results.append(("DuckDuckGo", ddg_response))
        
        success_count = sum(1 for _, response in results if response.success)
        total_results = sum(response.data.get('total_results', 0) for _, response in results if response.success)
        
        return f"Research completed. {success_count}/{len(results)} pipelines successful. Total results: {total_results}"
        
    except Exception as e:
        return f"Error dispatching to research agents: {str(e)}"


@orchestrator_agent.tool
async def dispatch_to_report_writer(ctx: RunContext[OrchestratorDeps], data_type: str, style: str = "summary") -> str:
    """Dispatch job to Report Writer agent."""
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Generating {style} report from {data_type} data"
        ))
        
        # This would use actual data from previous agent results
        # For now, return a placeholder response
        return f"Report writer would generate a {style} report from {data_type} data."
        
    except Exception as e:
        return f"Error dispatching to Report Writer agent: {str(e)}"


async def process_orchestrator_request(job_request: JobRequest) -> AsyncGenerator[StreamingUpdate, None]:
    """Process a job request through the orchestrator with streaming updates."""
    start_time = asyncio.get_event_loop().time()
    orchestrator_id = str(uuid.uuid4())
    agents_used = []
    errors = []
    
    # Initialize master output
    master_output = MasterOutputModel(
        job_request=job_request,
        orchestrator_id=orchestrator_id,
        agents_used=agents_used
    )
    
    try:
        yield StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Starting job: {job_request.job_type} - {job_request.query}"
        )
        
        # Route based on job type
        if job_request.job_type == "youtube":
            # Extract URL from query (simplified)
            url = job_request.query
            agents_used.append("YouTubeAgent")
            
            yield StreamingUpdate(
                update_type="status",
                agent_name="Orchestrator",
                message="Dispatching to YouTube Agent..."
            )
            
            response = await process_youtube_request(url)
            if response.success:
                master_output.youtube_data = YouTubeTranscriptModel(**response.data)
                yield StreamingUpdate(
                    update_type="partial_result",
                    agent_name="YouTubeAgent",
                    message="YouTube transcript retrieved successfully",
                    data=response.data
                )
            else:
                errors.append(response.error)
                yield StreamingUpdate(
                    update_type="error",
                    agent_name="YouTubeAgent",
                    message=f"Failed: {response.error}"
                )
        
        elif job_request.job_type == "weather":
            # Extract location from query
            location = job_request.query.replace("weather", "").replace("forecast", "").strip()
            agents_used.append("WeatherAgent")
            
            yield StreamingUpdate(
                update_type="status",
                agent_name="Orchestrator",
                message=f"Fetching weather for {location}..."
            )
            
            response = await process_weather_request(location)
            if response.success:
                master_output.weather_data = WeatherModel(**response.data)
                yield StreamingUpdate(
                    update_type="partial_result",
                    agent_name="WeatherAgent",
                    message=f"Weather data retrieved for {location}",
                    data=response.data
                )
            else:
                errors.append(response.error)
                yield StreamingUpdate(
                    update_type="error",
                    agent_name="WeatherAgent",
                    message=f"Failed: {response.error}"
                )
        
        elif job_request.job_type == "research":
            # Run both research pipelines
            agents_used.extend(["TavilyResearchAgent", "DuckDuckGoResearchAgent"])
            
            yield StreamingUpdate(
                update_type="status",
                agent_name="Orchestrator",
                message="Running parallel research pipelines..."
            )
            
            # Run research pipelines in parallel
            tavily_task = process_tavily_research_request(job_request.query)
            ddg_task = process_duckduckgo_research_request(job_request.query)
            
            tavily_response, ddg_response = await asyncio.gather(
                tavily_task, ddg_task, return_exceptions=True
            )
            
            # Process Tavily results
            if isinstance(tavily_response, AgentResponse) and tavily_response.success:
                master_output.research_data = ResearchPipelineModel(**tavily_response.data)
                yield StreamingUpdate(
                    update_type="partial_result",
                    agent_name="TavilyResearchAgent",
                    message="Tavily research completed",
                    data=tavily_response.data
                )
            else:
                error_msg = tavily_response.error if isinstance(tavily_response, AgentResponse) else str(tavily_response)
                errors.append(f"Tavily: {error_msg}")
                yield StreamingUpdate(
                    update_type="error",
                    agent_name="TavilyResearchAgent",
                    message=f"Failed: {error_msg}"
                )
            
            # Process DuckDuckGo results (as backup if Tavily failed)
            if isinstance(ddg_response, AgentResponse) and ddg_response.success and not master_output.research_data:
                master_output.research_data = ResearchPipelineModel(**ddg_response.data)
                yield StreamingUpdate(
                    update_type="partial_result",
                    agent_name="DuckDuckGoResearchAgent",
                    message="DuckDuckGo research completed",
                    data=ddg_response.data
                )
        
        # Generate report if requested or if we have data
        if (job_request.job_type == "report" or 
            master_output.research_data or 
            master_output.youtube_data):
            
            agents_used.append("ReportWriterAgent")
            
            yield StreamingUpdate(
                update_type="status",
                agent_name="Orchestrator",
                message=f"Generating {job_request.report_style} report..."
            )
            
            # Determine data source for report
            if master_output.research_data:
                report_response = await process_report_request(
                    master_output.research_data, 
                    job_request.report_style
                )
            elif master_output.youtube_data:
                report_response = await process_report_request(
                    master_output.youtube_data, 
                    job_request.report_style
                )
            else:
                # Create dummy research data for report-only requests
                dummy_research = ResearchPipelineModel(
                    original_query=job_request.query,
                    sub_queries=[job_request.query],
                    results=[ResearchItem(
                        query_variant=job_request.query,
                        title="General Information",
                        snippet=f"Information about {job_request.query}",
                        relevance_score=1.0
                    )],
                    pipeline_type="tavily",
                    total_results=1
                )
                report_response = await process_report_request(dummy_research, job_request.report_style)
            
            if report_response.success:
                master_output.report_data = ReportGenerationModel(**report_response.data)
                yield StreamingUpdate(
                    update_type="partial_result",
                    agent_name="ReportWriterAgent",
                    message=f"{job_request.report_style.title()} report generated",
                    data=report_response.data
                )
            else:
                errors.append(report_response.error)
                yield StreamingUpdate(
                    update_type="error",
                    agent_name="ReportWriterAgent",
                    message=f"Failed: {report_response.error}"
                )
        
        # Finalize master output
        master_output.agents_used = agents_used
        master_output.errors = errors
        master_output.success = len(errors) == 0
        master_output.total_processing_time = asyncio.get_event_loop().time() - start_time
        
        yield StreamingUpdate(
            update_type="final_result",
            agent_name="Orchestrator",
            message="Job completed successfully" if master_output.success else "Job completed with errors",
            data=master_output.model_dump()
        )
        
    except Exception as e:
        yield StreamingUpdate(
            update_type="error",
            agent_name="Orchestrator",
            message=f"Orchestrator error: {str(e)}"
        )


async def run_orchestrator_job(user_input: str) -> AsyncGenerator[StreamingUpdate, None]:
    """Main entry point for running orchestrator jobs."""
    try:
        # Parse user input into job request
        job_request = parse_job_request(user_input)
        
        # Process through orchestrator with streaming
        async for update in process_orchestrator_request(job_request):
            yield update
            
    except Exception as e:
        yield StreamingUpdate(
            update_type="error",
            agent_name="Orchestrator",
            message=f"Failed to process request: {str(e)}"
        )
