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
    ReportGenerationModel, ResearchItem, QueryIntentAnalysis
)
from config import config
from agents.youtube_agent import process_youtube_request
from agents.weather_agent import process_weather_request
from agents.research_tavily_agent import process_tavily_research_request
from agents.report_writer_agent import process_report_request
from research_logger import ResearchDataLogger, MasterStateLogger
from state_manager import MasterStateManager


class OrchestratorDeps:
    """Dependencies for Orchestrator Agent with centralized state management and execution tracking."""
    def __init__(self, state_manager: MasterStateManager = None):
        self.timeout = config.REQUEST_TIMEOUT
        self.orchestrator_id = str(uuid.uuid4())
        self.start_time = asyncio.get_event_loop().time()
        self.agents_used = []  # All agent calls (including duplicates for tracking)
        self.completed_agents = set()  # Successfully completed agents (prevents duplicates)
        self.agent_results = {}  # Cache results to avoid re-execution
        self.errors = []
        self.state_manager = state_manager  # Centralized state access  # Centralized state access


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


async def classify_query_intent_llm(user_query: str) -> QueryIntentAnalysis:
    """Classify user query intent using LLM intelligence instead of regex patterns.
    
    This replaces brittle keyword matching with intelligent query understanding.
    """
    # Build a specialized query intent classifier using the nano model
    intent_classifier = Agent(
        OpenAIModel(config.NANO_MODEL),
        instrument=True,
        output_type=QueryIntentAnalysis,
        system_prompt="""
        You analyze user queries to determine which agents/services are needed.
        
        Classification Guidelines:
        
        RESEARCH is needed for:
        - Questions about topics, trends, developments, news, analysis
        - Requests for information, facts, data, insights
        - Market research, competitive analysis, technical details
        - "Tell me about...", "What are...", "How does...", "Find information..."
        - Any query seeking factual information not in the conversation
        
        YOUTUBE is needed when:
        - Query contains YouTube URLs (youtube.com, youtu.be, m.youtube.com, etc.)
        - Extract the full YouTube URL if found
        
        WEATHER is needed for:
        - Weather, temperature, climate, forecast queries
        - Extract location if mentioned, otherwise leave empty
        
        REPORT is needed when:
        - User requests reports, summaries, documents, analysis
        - Words like "report", "summary", "write", "document", "analyze"
        - Or when research results need structured presentation
        
        Return structured JSON with confidence scores and rationale.
        Be generous with research - most information queries benefit from it.
        """,
        retries=2
    )
    
    prompt = f"""
    Analyze this user query and determine which agents are needed:
    
    Query: "{user_query}"
    
    Consider:
    - Does this need research/information gathering?
    - Contains YouTube URLs?
    - Asking about weather/climate?
    - Requesting a report or structured output?
    
    Return analysis with confidence scores and brief rationale.
    """
    
    try:
        result = await intent_classifier.run(prompt)
        return result.data if hasattr(result, 'data') and result.data else create_fallback_analysis(user_query)
    except Exception as e:
        print(f"LLM intent classification failed: {e}, using fallback")
        return create_fallback_analysis(user_query)


def create_fallback_analysis(user_query: str) -> QueryIntentAnalysis:
    """Fallback heuristic analysis if LLM classification fails."""
    query_lower = user_query.lower()
    
    # Extract YouTube URL
    youtube_url = extract_youtube_url(user_query)
    
    # Basic weather detection
    weather_location = None
    if any(word in query_lower for word in ["weather", "temperature", "forecast", "climate"]):
        # Simple location extraction
        words = user_query.split()
        for i, word in enumerate(words):
            if word.lower() in ["weather", "in", "for"] and i + 1 < len(words):
                potential_location = words[i + 1].strip(".,!?")
                if len(potential_location) > 2:
                    weather_location = potential_location
                    break
    
    return QueryIntentAnalysis(
        needs_research=True,  # Default to research for most queries
        needs_youtube=bool(youtube_url),
        needs_weather=bool(weather_location),
        needs_report=any(word in query_lower for word in ["report", "summary", "write", "document", "analyze"]),
        confidence_score=0.7,  # Moderate confidence for heuristic
        research_rationale="Fallback heuristic analysis - defaulting to research",
        youtube_url=youtube_url if youtube_url else None,
        weather_location=weather_location,
        query_complexity="moderate"
    )


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
    You are the Orchestrator Agent for a multi-agent system with PARALLEL EXECUTION capabilities. Your responsibilities:
    
    1. Parse user requests and intelligently extract structured parameters
    2. Coordinate execution using optimal parallel/sequential strategies
    3. Return a summary of coordination results (state is managed externally)
    4. Handle errors gracefully and provide meaningful feedback
    
    PERFORMANCE OPTIMIZATION:
    You now have advanced parallel execution tools that can dramatically improve performance:
    
    PARALLEL EXECUTION TOOLS (use these for maximum speed):
    - analyze_and_execute_optimal_workflow: PREFERRED tool for complex multi-agent requests
      * Automatically analyzes dependencies and runs independent agents in parallel
      * Handles YouTube + Weather + Research concurrently, then Report sequentially
      * Use this for any request involving multiple data sources
    
    - dispatch_parallel_independent_agents: For simple parallel dispatch
      * Run multiple independent agents simultaneously (youtube,weather,research)
      * Faster than sequential calls for independent operations
    
    SINGLE AGENT TOOLS (use only when parallel tools aren't suitable):
    - dispatch_to_youtube_agent: Pass the NORMALIZED YouTube URL, not the raw query
    - dispatch_to_weather_agent: Pass the extracted location
    - dispatch_to_research_agents: Pass refined search terms
    - dispatch_to_intelligent_report_writer: For generating adaptive, high-quality reports from collected data
    - dispatch_to_report_writer: Legacy report writer (maintained for compatibility)
    
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
    
    EXECUTION STRATEGY DECISION MATRIX:
    
    1. COMPLEX MULTI-AGENT REQUESTS (YouTube + Report, Research + Analysis, etc.):
       → USE: analyze_and_execute_optimal_workflow(user_query)
       → REASON: Automatic parallel optimization with dependency management
    
    2. SIMPLE PARALLEL REQUESTS (YouTube + Weather, multiple independent tasks):
       → USE: dispatch_parallel_independent_agents("youtube,weather", user_query)
       → REASON: Fast concurrent execution for independent operations
    
    3. SINGLE AGENT REQUESTS (just YouTube, just research, just weather):
       → USE: Individual dispatch tools (dispatch_to_youtube_agent, etc.)
       → REASON: No parallelization benefit
    
    PERFORMANCE EXAMPLES:
    
    User: "get transcript from https://youtu.be/ABC123 and create comprehensive report"
    → BEST: analyze_and_execute_optimal_workflow(user_query)
    → RESULT: YouTube transcript fetched, then report generated (optimal sequence)
    
    User: "get weather in NYC and transcript from https://youtu.be/XYZ789"  
    → BEST: dispatch_parallel_independent_agents("youtube,weather", user_query)
    → RESULT: Both agents run simultaneously (50% faster)
    
    User: "research AI trends and get weather in Tokyo"
    → BEST: dispatch_parallel_independent_agents("research,weather", user_query) 
    → RESULT: Research and weather fetched concurrently
    
    ERROR HANDLING:
    - If you cannot extract valid parameters (like invalid YouTube URL), FAIL immediately
    - Set success=False and include detailed error messages
    - Do not attempt to call tools with invalid parameters
    - Parallel tools have built-in error isolation (one failure won't stop others)
    
    CRITICAL: When calling tools, pass the EXTRACTED and NORMALIZED parameters, not the raw user query.
    
    Return a brief coordination summary of what was accomplished, execution strategy used, and any issues encountered.
    """,
    retries=config.MAX_RETRIES
)


@orchestrator_agent.tool
async def dispatch_parallel_independent_agents(ctx: RunContext[OrchestratorDeps], agent_list: str, task_description: str) -> str:
    """Dispatch multiple independent agents in parallel for faster execution.
    
    Args:
        agent_list: Comma-separated list of agents to run (e.g., "youtube,weather")
        task_description: Description of what each agent should do
    """
    import asyncio
    from typing import Dict, Any
    
    # Parse agent list
    agents_to_run = [agent.strip().lower() for agent in agent_list.split(',')]
    
    await stream_update(StreamingUpdate(
        update_type="status",
        agent_name="Orchestrator", 
        message=f"Starting parallel execution of {len(agents_to_run)} independent agents"
    ))
    
    # Create parallel tasks based on agents requested
    parallel_tasks = []
    task_names = []
    
    for agent_name in agents_to_run:
        if agent_name in ctx.deps.completed_agents:
            continue  # Skip already completed agents
            
        if agent_name == "youtube":
            # Extract YouTube URL from task description
            url = extract_youtube_url(task_description)
            if url:
                task = dispatch_to_youtube_agent(ctx, url)
                parallel_tasks.append(task)
                task_names.append("YouTube")
        
        elif agent_name == "weather":
            # Extract location from task description (simple heuristic)
            # This would need smarter extraction in production
            words = task_description.split()
            location = "New York"  # Default fallback
            for i, word in enumerate(words):
                if word.lower() in ["weather", "forecast", "temperature"] and i + 1 < len(words):
                    location = words[i + 1]
                    break
            task = dispatch_to_weather_agent(ctx, location)
            parallel_tasks.append(task)
            task_names.append("Weather")
        
        elif agent_name in ["research", "tavily", "serper"]:
            task = dispatch_to_research_agents(ctx, task_description, "both")
            parallel_tasks.append(task)
            task_names.append("Research")
    
    if not parallel_tasks:
        return "No independent agents to run in parallel (all completed or none specified)"
    
    # Execute all tasks concurrently
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Executing {len(parallel_tasks)} agents concurrently: {', '.join(task_names)}"
        ))
        
        results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        
        # Process results
        success_count = 0
        total_agents = len(results)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                ctx.deps.errors.append(f"Parallel {task_names[i]} failed: {str(result)}")
            else:
                success_count += 1
        
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Parallel execution completed: {success_count}/{total_agents} agents succeeded"
        ))
        
        return f"Parallel execution completed: {success_count}/{total_agents} agents succeeded. " \
               f"Agents: {', '.join(task_names)}"
        
    except Exception as e:
        error_msg = f"Error in parallel execution: {str(e)}"
        ctx.deps.errors.append(error_msg)
        return error_msg

@orchestrator_agent.tool
async def analyze_and_execute_optimal_workflow(ctx: RunContext[OrchestratorDeps], user_query: str) -> str:
    """Analyze user query and execute agents in optimal order (parallel where possible).
    
    This tool intelligently determines which agents can run in parallel vs sequentially
    based on their dependencies and the user's request.
    """
    import asyncio
    
    # Analyze what agents are needed using LLM intelligence instead of regex patterns
    intent_analysis = await classify_query_intent_llm(user_query)
    needs_youtube = intent_analysis.needs_youtube
    needs_weather = intent_analysis.needs_weather
    needs_research = intent_analysis.needs_research
    needs_report = intent_analysis.needs_report
    
    print(f"🧠 LLM Intent Analysis: Research={needs_research}, YouTube={needs_youtube}, Weather={needs_weather}, Report={needs_report}, Confidence={intent_analysis.confidence_score:.2f}")
    if intent_analysis.research_rationale:
        print(f"📝 Research rationale: {intent_analysis.research_rationale}")
    
    await stream_update(StreamingUpdate(
        update_type="status",
        agent_name="Orchestrator",
        message="Analyzing workflow dependencies and planning optimal execution"
    ))
    
    # Phase 1: Independent data collection agents (can run in parallel)
    phase1_tasks = []
    phase1_names = []
    
    if needs_youtube and "YouTubeAgent" not in ctx.deps.completed_agents:
        # Use LLM-extracted URL or fallback to pattern matching
        url = intent_analysis.youtube_url or extract_youtube_url(user_query)
        if url:
            phase1_tasks.append(dispatch_to_youtube_agent(ctx, url))
            phase1_names.append("YouTube")
    
    if needs_weather and "WeatherAgent" not in ctx.deps.completed_agents:
        # Use LLM-extracted location or fallback to heuristic extraction
        location = intent_analysis.weather_location
        if not location:
            # Fallback location extraction
            location = "New York"  # Default
            words = user_query.split()
            for i, word in enumerate(words):
                if word.lower() in ["weather", "in", "for"] and i + 1 < len(words):
                    potential_location = words[i + 1].strip(".,!?")
                    if len(potential_location) > 2:
                        location = potential_location
                        break
        phase1_tasks.append(dispatch_to_weather_agent(ctx, location))
        phase1_names.append("Weather")
    
    if needs_research and "ResearchAgents" not in ctx.deps.completed_agents:
        phase1_tasks.append(dispatch_to_research_agents(ctx, user_query, "both"))
        phase1_names.append("Research")
    
    # Execute Phase 1 (parallel data collection)
    phase1_results = []
    if phase1_tasks:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Phase 1: Parallel data collection ({len(phase1_tasks)} agents: {', '.join(phase1_names)})"
        ))
        
        phase1_results = await asyncio.gather(*phase1_tasks, return_exceptions=True)
        
        # Log Phase 1 results
        success_count = sum(1 for result in phase1_results if not isinstance(result, Exception))
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator", 
            message=f"Phase 1 completed: {success_count}/{len(phase1_tasks)} data agents succeeded"
        ))
    
    # Phase 2: Report generation (depends on Phase 1 data)
    phase2_result = ""
    if needs_report and "ReportWriterAgent" not in ctx.deps.completed_agents:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message="Phase 2: Generating report from collected data"
        ))
        
        try:
            # Determine quality level based on query complexity
            quality_level = "enhanced" if "comprehensive" in user_query.lower() else "standard"
            report_result = await dispatch_to_intelligent_report_writer(
                ctx, user_query, "comprehensive", quality_level
            )
            phase2_result = f" -> {report_result}"
        except Exception as e:
            phase2_result = f" -> Intelligent report generation failed: {str(e)}"
            ctx.deps.errors.append(f"Phase 2 Intelligent Report: {str(e)}")
    
    # Summary
    total_success = sum(1 for result in phase1_results if not isinstance(result, Exception))
    if phase2_result and "failed" not in phase2_result:
        total_success += 1
    
    return f"Optimal workflow executed: Phase 1 ({len(phase1_names)} parallel agents) -> Phase 2 (report). " \
           f"Total success: {total_success} agents{phase2_result}"

@orchestrator_agent.tool
async def generate_trace_analysis_report(ctx: RunContext[OrchestratorDeps], analysis_request: str) -> str:
    """Generate automated trace analysis report for system performance insights.
    
    Args:
        analysis_request: Request describing what type of analysis to perform
                         (e.g., "performance analysis last hour", "cost optimization", "error analysis")
    """
    try:
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message="Initiating trace analysis - gathering performance data"
        ))
        
        # Parse the analysis request to determine parameters
        request_lower = analysis_request.lower()
        
        # Determine analysis type
        if "cost" in request_lower or "optimization" in request_lower:
            analysis_type = "cost"
            time_range = 1440  # 24 hours for cost analysis
        elif "error" in request_lower or "failure" in request_lower:
            analysis_type = "error"
            time_range = 60
        elif "performance" in request_lower:
            analysis_type = "performance" 
            time_range = 60
        else:
            analysis_type = "comprehensive"
            time_range = 60
        
        # Extract time range if specified
        if "hour" in request_lower and "last" in request_lower:
            time_range = 60
        elif "day" in request_lower and "last" in request_lower:
            time_range = 1440
        elif "week" in request_lower and "last" in request_lower:
            time_range = 10080
        
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Running {analysis_type} analysis for last {time_range} minutes"
        ))
        
        # Import and run trace analyzer
        from agents.trace_analyzer_agent import analyze_traces
        
        trace_report = await analyze_traces(
            time_range_minutes=time_range,
            analysis_type=analysis_type,
            max_traces=100
        )
        
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator", 
            message="Trace analysis completed - generating insights"
        ))
        
        # Format results for user
        insights_summary = f"""
        📊 TRACE ANALYSIS RESULTS ({analysis_type.title()})
        
        📈 SYSTEM PERFORMANCE:
        • Total Traces Analyzed: {trace_report.total_traces_analyzed}
        • Success Rate: {trace_report.success_rate:.1%}
        • Average Job Time: {trace_report.average_job_time:.1f}s
        • Total API Calls: {trace_report.total_api_calls}
        
        🎯 KEY INSIGHTS:
        • Health Status: {trace_report.insights.overall_system_health.title()}
        • Critical Issues: {len(trace_report.insights.critical_issues)} found
        • Optimization Opportunities: {len(trace_report.insights.optimization_recommendations)}
        
        ⚡ IMMEDIATE ACTIONS:
        """
        
        for action in trace_report.immediate_actions[:3]:  # Top 3 actions
            insights_summary += f"• {action}\n        "
        
        if trace_report.cost_analysis:
            insights_summary += f"""
        💰 COST ANALYSIS:
        • Estimated Cost: ${trace_report.cost_analysis.estimated_cost_usd:.2f}
        • Optimization Potential: {len(trace_report.cost_analysis.optimization_opportunities)} opportunities
        """
        
        insights_summary += f"""
        
        🔧 STRATEGIC IMPROVEMENTS:
        """
        
        for improvement in trace_report.strategic_improvements[:2]:  # Top 2 improvements
            insights_summary += f"• {improvement}\n        "
        
        # Store the full report in state for later access if needed
        if ctx.deps.state_manager:
            # Store as a simplified dict for state management
            ctx.deps.agent_results["TraceAnalyzer"] = {
                'success': True,
                'data': {
                    'analysis_type': trace_report.analysis_type,
                    'total_traces': trace_report.total_traces_analyzed,
                    'success_rate': trace_report.success_rate,
                    'health_status': trace_report.insights.overall_system_health,
                    'summary': insights_summary
                }
            }
            ctx.deps.completed_agents.add("TraceAnalyzer")
            ctx.deps.agents_used.append("TraceAnalyzer")
        
        return f"Trace analysis completed successfully. Generated {analysis_type} analysis report with {len(trace_report.insights.optimization_recommendations)} optimization recommendations and {len(trace_report.immediate_actions)} immediate action items."
        
    except Exception as e:
        error_msg = f"Trace analysis failed: {str(e)}"
        ctx.deps.errors.append(error_msg)
        return error_msg

@orchestrator_agent.tool
async def dispatch_to_youtube_agent(ctx: RunContext[OrchestratorDeps], url: str) -> str:
    """Dispatch job to YouTube agent with AI-extracted and normalized URL."""
    agent_name = "YouTubeAgent"
    
    # Check if this agent has already been completed successfully
    if agent_name in ctx.deps.completed_agents:
        cached_result = ctx.deps.agent_results.get(agent_name)
        if cached_result and cached_result.get('success'):
            await stream_update(StreamingUpdate(
                update_type="status",
                agent_name="Orchestrator",
                message=f"Using cached YouTube result for: {url}"
            ))
            return f"YouTube agent already completed (cached). Retrieved transcript with {len(cached_result.get('data', {}).get('transcript', ''))} characters."
    
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
                agent_name=agent_name,
                success=True,
                data=result_data,
                error=None
            )
        except Exception as e:
            response = AgentResponse(
                agent_name=agent_name,
                success=False,
                data={},
                error=str(e)
            )
            ctx.deps.errors.append(f"YouTube: {str(e)}")
        
        # Cache the result regardless of success/failure
        ctx.deps.agent_results[agent_name] = {
            'success': response.success,
            'data': response.data,
            'error': response.error
        }
        
        if response.success:
            # Create YouTubeTranscriptModel from the response data
            youtube_model = YouTubeTranscriptModel(**response.data)
            # Store in centralized state for access by other agents
            if ctx.deps.state_manager:
                ctx.deps.state_manager.update_youtube_data(agent_name, youtube_model)
            
            # PERFORMANCE FIX: Mark as completed to prevent duplication - add to agents_used only once
            if agent_name not in ctx.deps.completed_agents:
                ctx.deps.completed_agents.add(agent_name)
                ctx.deps.agents_used.append(agent_name)
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
        # PERFORMANCE FIX: Only add ResearchAgents to agents_used once
        if "ResearchAgents" not in ctx.deps.agents_used:
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
        
        # Aggregate and combine ALL successful research results with cross-API deduplication
        all_research_results = []
        combined_sub_queries = []
        primary_query = query
        seen_urls = set()  # Track URLs to prevent duplicate scraping across APIs
        duplicate_count = 0
        
        for name, response in results:
            if response.success:
                research_model = ResearchPipelineModel(**response.data)
                
                # Add results with deduplication based on source_url
                for result in research_model.results:
                    if result.source_url and result.source_url in seen_urls:
                        duplicate_count += 1
                        print(f"🔄 DEDUPLICATION: Skipping duplicate URL from {name}: {result.source_url}")
                        continue
                    
                    # Track this URL and add the result
                    if result.source_url:
                        seen_urls.add(result.source_url)
                    all_research_results.append(result)
                
                combined_sub_queries.extend(research_model.sub_queries)
                primary_query = research_model.original_query  # Use last successful query
                
                # Store individual pipeline data in centralized state
                if ctx.deps.state_manager:
                    ctx.deps.state_manager.update_research_data(name, research_model)
        
        # Create combined research model with ALL results from ALL pipelines
        if all_research_results:
            print(f"✅ DEDUPLICATION: Prevented {duplicate_count} duplicate URLs from being processed")
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
async def dispatch_to_intelligent_report_writer(
    ctx: RunContext[OrchestratorDeps], 
    query: str, 
    style: str = "summary",
    quality_level: str = "standard"
) -> str:
    """Dispatch job to Intelligent Report Writer with adaptive templates and quality control."""
    agent_name = "IntelligentReportWriter"
    
    # Check if this agent has already been completed successfully
    if agent_name in ctx.deps.completed_agents:
        cached_result = ctx.deps.agent_results.get(agent_name)
        if cached_result and cached_result.get('success'):
            await stream_update(StreamingUpdate(
                update_type="status",
                agent_name="Orchestrator",
                message=f"Using cached intelligent report writer result"
            ))
            return f"Intelligent Report Writer already completed (cached). Report length: {len(cached_result.get('data', {}).get('final', ''))} characters."
    
    try:
        # Get unified data package from state manager
        universal_data = None
        if ctx.deps.state_manager:
            universal_data = ctx.deps.state_manager.get_universal_report_data()
        
        if not universal_data or not universal_data.has_data():
            return "Error: No data available for intelligent report generation"
        
        # Analyze query complexity to determine quality level if not specified
        if quality_level == "auto":
            query_lower = query.lower()
            if any(word in query_lower for word in ["comprehensive", "detailed", "thorough", "analysis"]):
                quality_level = "enhanced"
            elif any(word in query_lower for word in ["executive", "strategic", "leadership", "premium"]):
                quality_level = "premium"
            else:
                quality_level = "standard"
        
        await stream_update(StreamingUpdate(
            update_type="status",
            agent_name="Orchestrator",
            message=f"Generating {style} {quality_level}-quality report from {len(universal_data.get_data_types())} data sources"
        ))
        
        try:
            # Use new intelligent report generation system
            from agents.report_writer_agent import process_intelligent_report_request
            
            response = await process_intelligent_report_request(
                universal_data=universal_data,
                style=style,
                quality_level=quality_level
            )
        except Exception as e:
            response = AgentResponse(
                agent_name=agent_name,
                success=False,
                data={},
                error=str(e)
            )
            ctx.deps.errors.append(f"Intelligent Report Writer: {str(e)}")
        
        # Cache the result regardless of success/failure
        ctx.deps.agent_results[agent_name] = {
            'success': response.success,
            'data': response.data,
            'error': response.error
        }
        
        if response.success:
            # Store in state manager
            if ctx.deps.state_manager:
                from models import ReportGenerationModel
                report_model = ReportGenerationModel(**response.data)
                ctx.deps.state_manager.update_report_data(agent_name, report_model)
            
            # PERFORMANCE FIX: Mark as completed to prevent duplication
            if agent_name not in ctx.deps.completed_agents:
                ctx.deps.completed_agents.add(agent_name)
                ctx.deps.agents_used.append(agent_name)
            
            data_types = universal_data.get_data_types()
            word_count = response.data.get('word_count', 0)
            processing_time = response.processing_time or 0
            
            return f"Intelligent {style} report generated successfully! Quality: {quality_level}, " \
                   f"Sources: {', '.join(data_types)}, Length: {word_count} words, " \
                   f"Time: {processing_time:.1f}s"
        else:
            ctx.deps.errors.append(response.error)
            return f"Intelligent Report Writer failed: {response.error}"
        
    except Exception as e:
        ctx.deps.errors.append(str(e))
        return f"Error in intelligent report dispatch: {str(e)}"


# Legacy function maintained for backward compatibility
@orchestrator_agent.tool
async def dispatch_to_report_writer(ctx: RunContext[OrchestratorDeps], query: str, style: str = "summary") -> str:
    """Legacy Report Writer dispatch - maintained for backward compatibility."""
    # Use new intelligent system with standard quality
    return await dispatch_to_intelligent_report_writer(ctx, query, style, "standard")


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
