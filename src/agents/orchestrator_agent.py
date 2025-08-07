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
    ReportGenerationModel, ResearchItem
)
from config import config
from agents.youtube_agent import process_youtube_request
from agents.weather_agent import process_weather_request
from agents.research_tavily_agent import process_tavily_research_request
from agents.report_writer_agent import process_report_request
from research_logger import ResearchDataLogger, MasterStateLogger
from state_manager import MasterStateManager


class OrchestratorDeps:
    """Dependencies for Orchestrator Agent with centralized state management."""
    def __init__(self, state_manager: MasterStateManager = None):
        self.timeout = config.REQUEST_TIMEOUT
        self.orchestrator_id = str(uuid.uuid4())
        self.start_time = asyncio.get_event_loop().time()
        self.agents_used = []
        self.errors = []
        self.state_manager = state_manager  # Centralized state access


def extract_youtube_url(text: str) -> str:
    """Extract YouTube URL from text, supporting all common YouTube URL formats."""
    import re
    
    # Comprehensive YouTube URL patterns
    patterns = [
        # Standard YouTube URLs (youtube.com/watch)
        r'https?://(?:www\.)?youtube\.com/watch\?(?:[^&\s]*&)*v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)',
        r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)?',
        
        # Mobile YouTube URLs (m.youtube.com)
        r'https?://m\.youtube\.com/watch\?(?:[^&\s]*&)*v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)',
        r'https?://m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)?',
        
        # YouTube Music URLs
        r'https?://music\.youtube\.com/watch\?(?:[^&\s]*&)*v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)',
        r'https?://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)?',
        
        # YouTube Shorts URLs
        r'https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})(?:[^&\s]*)?',
        
        # Short URLs (youtu.be)
        r'https?://youtu\.be/([a-zA-Z0-9_-]{11})(?:\?[^&\s]*)?',
        
        # Embed URLs
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})(?:[^&\s]*)?',
        
        # YouTube TV URLs
        r'https?://(?:www\.)?youtube\.com/tv#/watch/video/idle\?v=([a-zA-Z0-9_-]{11})',
        
        # Gaming YouTube URLs
        r'https?://gaming\.youtube\.com/watch\?(?:[^&\s]*&)*v=([a-zA-Z0-9_-]{11})(?:[^&\s]*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            video_id = match.group(1)
            # Return a standardized YouTube URL
            return f"https://www.youtube.com/watch?v={video_id}"
    
    return text  # fallback to original text


def parse_job_request(user_input: str) -> JobRequest:
    """Parse user input into a structured job request."""
    user_input_lower = user_input.lower()
    
    # Determine job type based on keywords (order matters - most specific first)
    if any(keyword in user_input_lower for keyword in ["youtube", "video", "transcript"]):
        job_type = "youtube"
    elif any(keyword in user_input_lower for keyword in ["weather", "forecast", "temperature"]):
        job_type = "weather"
    elif any(keyword in user_input_lower for keyword in ["research", "search", "find", "investigate", "latest", "developments", "trends"]):
        job_type = "research"
    elif any(keyword in user_input_lower for keyword in ["report", "generate report", "write", "create", "comprehensive analysis", "summary of"]):
        job_type = "report"
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


# Create Orchestrator Agent with proper instrumentation
orchestrator_agent = Agent(
    model=OpenAIModel(config.ORCHESTRATOR_MODEL),
    deps_type=OrchestratorDeps,
    output_type=str,  # Return coordination summary, not full MasterOutputModel
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt="""
    You are the Orchestrator Agent for a multi-agent system. Your responsibilities:
    
    1. Parse user requests and intelligently extract structured parameters
    2. Coordinate execution using the available tools for each agent type
    3. Return a summary of coordination results (state is managed externally)
    4. Handle errors gracefully and provide meaningful feedback
    
    INTELLIGENT QUERY PARSING:
    When you receive a user query, you must intelligently extract and normalize relevant parameters:
    
    For YouTube requests:
    - Extract YouTube URLs from the query text using pattern recognition
    - Normalize URLs to standard format: https://www.youtube.com/watch?v=VIDEO_ID
    - Support all YouTube URL formats: youtu.be, youtube.com/shorts, mobile, embed, etc.
    - If no valid YouTube URL with video ID found, FAIL EARLY with clear error
    - Valid video IDs are exactly 11 characters: [a-zA-Z0-9_-]
    
    For Weather requests:
    - Extract location names from query text
    - Normalize location formats
    
    For Research requests:
    - Extract search terms and research focus areas
    - Identify specific topics or trends to research
    
    Available tools (use these to dispatch to specialized agents):
    - dispatch_to_youtube_agent: Pass the NORMALIZED YouTube URL, not the raw query
    - dispatch_to_weather_agent: Pass the extracted location
    - dispatch_to_research_agents: Pass refined search terms
    - dispatch_to_report_writer: For generating reports from collected data
    
    CRITICAL: When calling tools, pass the EXTRACTED and NORMALIZED parameters, not the raw user query.
    
    Example flows:
    1. User: "get transcript from https://youtu.be/dQw4w9WgXcQ and write a report"
       → Extract: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
       → Call: dispatch_to_youtube_agent("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    
    2. User: "research latest AI trends"
       → Extract: "latest AI trends"
       → Call: dispatch_to_research_agents("latest AI trends")
    
    ERROR HANDLING:
    - If you cannot extract valid parameters (like invalid YouTube URL), FAIL immediately
    - Set success=False and include detailed error messages
    - Do not attempt to call tools with invalid parameters
    
    Return a brief coordination summary of what was accomplished and any issues encountered.
    """,
    retries=config.MAX_RETRIES
)


@orchestrator_agent.tool
async def dispatch_to_youtube_agent(ctx: RunContext[OrchestratorDeps], url: str) -> str:
    """Dispatch job to YouTube agent with AI-extracted and normalized URL."""
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Dispatching YouTube transcript request for: {url}"
        ))
        
        try:
            # Use proper Pydantic AI agent instead of direct function call
            from agents.youtube_agent import youtube_agent
            youtube_result = await youtube_agent.run(
                f"Process this YouTube URL: {url}",
                usage=ctx.usage
            )
            # Convert to AgentResponse format for compatibility
            # Extract the actual YouTubeTranscriptModel from AgentRunResult (use .output not deprecated .data)
            if hasattr(youtube_result, 'output') and youtube_result.output:
                result_data = youtube_result.output.model_dump() if hasattr(youtube_result.output, 'model_dump') else youtube_result.output
            else:
                result_data = youtube_result.model_dump() if hasattr(youtube_result, 'model_dump') else youtube_result
            
            response = AgentResponse(
                agent_name="YouTubeAgent",
                success=True,
                data=result_data,
                error=None
            )
        except Exception as e:
            response = AgentResponse(
                agent_name="YouTubeAgent",
                success=False,
                data={},
                error=str(e)
            )
            ctx.deps.errors.append(f"YouTube: {str(e)}")
        
        if response.success:
            # Create YouTubeTranscriptModel from the response data
            youtube_model = YouTubeTranscriptModel(**response.data)
            # Store in centralized state for access by other agents
            if ctx.deps.state_manager:
                ctx.deps.state_manager.update_youtube_data("YouTubeAgent", youtube_model)
            ctx.deps.agents_used.append("YouTubeAgent")
            return f"YouTube agent completed successfully. Retrieved transcript with {len(response.data.get('transcript', ''))} characters."
        else:
            ctx.deps.errors.append(response.error)
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
        
        try:
            # Use proper Pydantic AI agent instead of direct function call
            from agents.weather_agent import weather_agent
            weather_result = await weather_agent.run(
                f"Get weather information for: {location}",
                usage=ctx.usage
            )
            # Convert to AgentResponse format for compatibility
            # Extract the actual WeatherModel from AgentRunResult (use .output not deprecated .data)
            if hasattr(weather_result, 'output') and weather_result.output:
                result_data = weather_result.output.model_dump() if hasattr(weather_result.output, 'model_dump') else weather_result.output
            else:
                result_data = weather_result.model_dump() if hasattr(weather_result, 'model_dump') else weather_result
            
            response = AgentResponse(
                agent_name="WeatherAgent",
                success=True,
                data=result_data,
                error=None
            )
        except Exception as e:
            response = AgentResponse(
                agent_name="WeatherAgent",
                success=False,
                data={},
                error=str(e)
            )
            ctx.deps.errors.append(f"Weather: {str(e)}")
        
        if response.success:
            return f"Weather agent completed successfully. Retrieved current weather and forecast for {location}."
        else:
            return f"Weather agent failed: {response.error}"
            
    except Exception as e:
        return f"Error dispatching to Weather agent: {str(e)}"


@orchestrator_agent.tool
async def dispatch_to_research_agents(ctx: RunContext[OrchestratorDeps], query: str, pipeline: str = "both") -> str:
    """Dispatch job to research agents (Tavily and/or Serper)."""
    try:
        ctx.deps.agents_used.append("ResearchAgents")
        
        results = []
        
        if pipeline in ["tavily", "both"]:
            try:
                # Use proper Pydantic AI agent with explicit tool usage prompt
                from agents.research_tavily_agent import tavily_research_agent, TavilyResearchDeps
                
                # Create proper dependencies for the Tavily agent
                tavily_deps = TavilyResearchDeps()
                
                tavily_result = await tavily_research_agent.run(
                    f"Use your perform_tavily_research tool to conduct comprehensive research on: {query}. "
                    f"Please search for real web sources and return structured results with actual URLs and data.",
                    deps=tavily_deps,
                    usage=ctx.usage
                )
                # Convert to AgentResponse format for compatibility
                # Extract the actual ResearchPipelineModel from AgentRunResult (use .output not deprecated .data)
                if hasattr(tavily_result, 'output') and tavily_result.output:
                    result_data = tavily_result.output.model_dump() if hasattr(tavily_result.output, 'model_dump') else tavily_result.output
                else:
                    result_data = tavily_result.model_dump() if hasattr(tavily_result, 'model_dump') else tavily_result
                
                tavily_response = AgentResponse(
                    agent_name="TavilyResearchAgent",
                    success=True,
                    data=result_data,
                    error=None
                )
                results.append(("Tavily", tavily_response))
            except Exception as e:
                tavily_response = AgentResponse(
                    agent_name="TavilyResearchAgent",
                    success=False,
                    data={},
                    error=str(e)
                )
                results.append(("Tavily", tavily_response))
                ctx.deps.errors.append(f"Tavily: {str(e)}")
        
        if pipeline in ["serper", "both"]:
            try:
                # Use proper Pydantic AI agent with explicit tool usage prompt
                from agents.research_serper_agent import serper_research_agent, SerperResearchDeps
                
                # Create proper dependencies for the Serper agent
                serper_deps = SerperResearchDeps()
                
                serper_result = await serper_research_agent.run(
                    f"Use your perform_serper_research tool to conduct comprehensive research on: {query}. "
                    f"Please search for real web sources and return structured results with actual URLs and data.",
                    deps=serper_deps,
                    usage=ctx.usage
                )
                # Convert to AgentResponse format for compatibility
                # Extract the actual ResearchPipelineModel from AgentRunResult (use .output not deprecated .data)
                if hasattr(serper_result, 'output') and serper_result.output:
                    result_data = serper_result.output.model_dump() if hasattr(serper_result.output, 'model_dump') else serper_result.output
                else:
                    result_data = serper_result.model_dump() if hasattr(serper_result, 'model_dump') else serper_result
                
                serper_response = AgentResponse(
                    agent_name="SerperResearchAgent",
                    success=True,
                    data=result_data,
                    error=None
                )
                results.append(("Serper", serper_response))
            except Exception as e:
                serper_response = AgentResponse(
                    agent_name="SerperResearchAgent",
                    success=False,
                    data={},
                    error=str(e)
                )
                results.append(("Serper", serper_response))
                ctx.deps.errors.append(f"Serper: {str(e)}")
        
        success_count = sum(1 for _, response in results if response.success)
        total_results = sum(response.data.get('total_results', 0) for _, response in results if response.success)
        
        # Aggregate and combine ALL successful research results
        all_research_results = []
        combined_sub_queries = []
        primary_query = query
        
        for name, response in results:
            if response.success:
                research_model = ResearchPipelineModel(**response.data)
                all_research_results.extend(research_model.results)
                combined_sub_queries.extend(research_model.sub_queries)
                primary_query = research_model.original_query  # Use last successful query
                
                # Store individual pipeline data in centralized state
                if ctx.deps.state_manager:
                    ctx.deps.state_manager.update_research_data(name, research_model)
        
        # Create combined research model with ALL results from ALL pipelines
        if all_research_results:
            combined_research = ResearchPipelineModel(
                original_query=primary_query,
                sub_queries=list(set(combined_sub_queries)),  # Remove duplicates
                results=all_research_results,
                pipeline_type="combined_tavily_serper",
                total_results=len(all_research_results),
                processing_time=0.0
            )
            
            # Store the combined research data as the primary research result
            if ctx.deps.state_manager:
                ctx.deps.state_manager.update_research_data("Combined", combined_research)
            else:
                # Fallback to old logging if state manager not available
                logger = ResearchDataLogger()
                logger.log_research_state(combined_research)
        
        return f"Research completed. {success_count}/{len(results)} pipelines successful. Total results: {total_results}"
        
    except Exception as e:
        ctx.deps.errors.append(str(e))
        return f"Error dispatching to research agents: {str(e)}"


@orchestrator_agent.tool
async def dispatch_to_report_writer(ctx: RunContext[OrchestratorDeps], query: str, style: str = "summary") -> str:
    """Dispatch job to Report Writer agent with universal data approach."""
    try:
        ctx.deps.agents_used.append("ReportWriterAgent")
        
        # Get unified data package from state manager
        universal_data = None
        if ctx.deps.state_manager:
            universal_data = ctx.deps.state_manager.get_universal_report_data()
        
        if not universal_data or not universal_data.has_data():
            return "Error: No data available for report generation"
        
        # Build comprehensive prompt with all available data
        data_types = universal_data.get_data_types()
        primary_content = universal_data.get_primary_content()
        
        prompt = f"Generate a {style} report analyzing the following data:\n\n"
        prompt += f"Data Sources Available: {', '.join(data_types)}\n"
        prompt += f"User Query: {universal_data.query}\n\n"
        
        # Add section-by-section data
        if universal_data.youtube_data:
            prompt += f"YOUTUBE DATA:\n"
            prompt += f"Title: {universal_data.youtube_data.title or 'Unknown'}\n"
            prompt += f"URL: {universal_data.youtube_data.url}\n"
            prompt += f"Duration: {universal_data.youtube_data.duration or 'Unknown'}\n"
            prompt += f"Channel: {universal_data.youtube_data.channel or 'Unknown'}\n"
            prompt += f"Transcript ({len(universal_data.youtube_data.transcript)} chars):\n{universal_data.youtube_data.transcript[:3000]}...\n\n"
        
        if universal_data.research_data:
            prompt += f"RESEARCH DATA:\n"
            prompt += f"Query: {universal_data.research_data.original_query}\n"
            prompt += f"Results: {universal_data.research_data.total_results}\n"
            for i, result in enumerate(universal_data.research_data.results[:5], 1):
                prompt += f"{i}. {result.title}: {result.snippet}\n"
            prompt += "\n"
        
        if universal_data.weather_data:
            prompt += f"WEATHER DATA:\n{universal_data.weather_data}\n\n"
        
        prompt += f"Create a {style} report with distinct sections for each data source and quantified insights."
        
        try:
            from agents.report_writer_agent import report_writer_agent
            report_result = await report_writer_agent.run(prompt, usage=ctx.usage)
            
            if hasattr(report_result, 'output') and report_result.output:
                result_data = report_result.output.model_dump() if hasattr(report_result.output, 'model_dump') else report_result.output
            else:
                result_data = report_result.model_dump() if hasattr(report_result, 'model_dump') else report_result
            
            response = AgentResponse(
                agent_name="ReportWriterAgent",
                success=True,
                data=result_data,
                error=None
            )
        except Exception as e:
            response = AgentResponse(
                agent_name="ReportWriterAgent", 
                success=False,
                data={},
                error=str(e)
            )
            ctx.deps.errors.append(f"Report Writer: {str(e)}")
        
        if response.success:
            report_model = ReportGenerationModel(**response.data)
            if ctx.deps.state_manager:
                ctx.deps.state_manager.update_report_data("ReportWriterAgent", report_model)
            return f"Universal report generated successfully from {len(data_types)} data sources: {len(response.data.get('final', ''))} characters"
        else:
            ctx.deps.errors.append(response.error)
            return f"Report Writer failed: {response.error}"
        
    except Exception as e:
        ctx.deps.errors.append(str(e))
        return f"Error in universal report dispatch: {str(e)}"


async def run_orchestrator_job(user_input: str) -> AsyncGenerator[StreamingUpdate, None]:
    """Main entry point for running orchestrator jobs using proper Pydantic AI agent execution."""
    try:
        # Parse user input into job request
        job_request = parse_job_request(user_input)
        
        yield StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Starting job: {job_request.job_type} - {job_request.query}"
        )
        
        # Initialize centralized state manager
        state_manager = MasterStateManager(
            orchestrator_id=str(uuid.uuid4()),
            job_request=job_request
        )
        
        # Create dependencies with state manager
        deps = OrchestratorDeps(state_manager=state_manager)
        
        # Run the actual Pydantic AI orchestrator agent
        result = await orchestrator_agent.run(
            job_request.query,
            deps=deps
        )
        
        # Update final state in the centralized state manager
        processing_time = asyncio.get_event_loop().time() - deps.start_time
        state_manager.set_processing_time(processing_time)
        
        # Add any remaining errors from deps
        for error in deps.errors:
            state_manager.add_error("Orchestrator", error)
            
        # Get the complete master state document
        master_output = state_manager.get_master_state()
        
        # Update with orchestrator-specific data
        master_output.agents_used.extend(deps.agents_used)
        master_output.success = len(deps.errors) == 0 and master_output.success
        
        # VALIDATION: Pre-validate the master output before final processing
        try:
            # Test serialization to catch any validation issues early
            test_data = master_output.model_dump()
            
            # Validate specific agent data that commonly causes issues
            if master_output.youtube_data:
                # Ensure YouTube data has required metadata field
                if not master_output.youtube_data.metadata:
                    yield StreamingUpdate(
                        update_type="error", 
                        agent_name="Orchestrator",
                        message="Warning: YouTube data missing metadata field - populating with defaults"
                    )
                    master_output.youtube_data.metadata = {"validation_fix": "empty_metadata_populated"}
            
            # Re-validate after any fixes
            validated_data = master_output.model_dump()
            
        except Exception as validation_error:
            yield StreamingUpdate(
                update_type="error",
                agent_name="Orchestrator", 
                message=f"Validation failed: {str(validation_error)}"
            )
            master_output.success = False
            master_output.errors.append(f"Final validation error: {str(validation_error)}")
        
        # Log the complete master state document
        master_logger = MasterStateLogger()
        master_logger.log_master_state(
            master_output, 
            state_summary=state_manager.get_state_summary()
        )
        
        # Stream the final result
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
            message=f"Failed to process request: {str(e)}"
        )
