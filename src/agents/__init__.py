"""
Agent registry and initialization for the multi-agent system.
"""

from .youtube_agent import youtube_agent, process_youtube_request
from .weather_agent import weather_agent, process_weather_request
from .research_tavily_agent import tavily_research_agent, process_tavily_research_request
from .research_serper_agent import serper_research_agent, process_serper_research_request
from .report_writer_agent import report_writer_agent, process_report_request
from .orchestrator_agent import orchestrator_agent, run_orchestrator_job
from .trace_analyzer_agent import trace_analyzer_agent, analyze_traces

__all__ = [
    # Agents
    "youtube_agent",
    "weather_agent", 
    "tavily_research_agent",
    "serper_research_agent",
    "report_writer_agent",
    "orchestrator_agent",
    "trace_analyzer_agent",
    
    # Processing functions
    "process_youtube_request",
    "process_weather_request",
    "process_tavily_research_request", 
    "process_serper_research_request",
    "process_report_request",
    "run_orchestrator_job",
    "analyze_traces"
]


# Agent registry for dynamic dispatch
AGENT_REGISTRY = {
    "youtube": {
        "agent": youtube_agent,
        "processor": process_youtube_request,
        "description": "Fetch YouTube video transcripts and metadata"
    },
    "weather": {
        "agent": weather_agent,
        "processor": process_weather_request,
        "description": "Get current weather and 7-day forecasts"
    },
    "research_tavily": {
        "agent": tavily_research_agent,
        "processor": process_tavily_research_request,
        "description": "Research using Tavily API with query expansion"
    },
    "research_serper": {
        "agent": serper_research_agent,
        "processor": process_serper_research_request,
        "description": "Research using Google Search via Serper API with URL scraping"
    },
    "report_writer": {
        "agent": report_writer_agent,
        "processor": process_report_request,
        "description": "Generate comprehensive, top-10, or summary reports"
    },
    "orchestrator": {
        "agent": orchestrator_agent,
        "processor": run_orchestrator_job,
        "description": "Central coordinator for multi-agent workflows"
    },
    "trace_analyzer": {
        "agent": trace_analyzer_agent,
        "processor": analyze_traces,
        "description": "Automated performance analysis and optimization recommendations"
    }
}


def get_agent(agent_name: str):
    """Get agent by name from registry."""
    return AGENT_REGISTRY.get(agent_name, {}).get("agent")


def get_processor(agent_name: str):
    """Get processor function by agent name from registry."""
    return AGENT_REGISTRY.get(agent_name, {}).get("processor")


def list_available_agents():
    """List all available agents and their descriptions."""
    return {
        name: info["description"] 
        for name, info in AGENT_REGISTRY.items()
    }
