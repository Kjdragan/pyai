"""
Streamlit Chat UI for the Pydantic-AI Multi-Agent System.
Provides conversational interface for job submission and streaming responses.
"""

import streamlit as st
import asyncio
from typing import List, Dict, Any
import json
from datetime import datetime

# Import our agents and models
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Initialize logging system for Streamlit (ensure proper initialization)
try:
    from logging_config import get_logging_manager, get_logger, initialize_logging
    
    # Always initialize logging for Streamlit subprocess
    logging_manager = initialize_logging(
        logs_dir=os.path.join(os.path.dirname(__file__), "logs"),
        enable_logfire=False  # Disable Logfire in subprocess to avoid conflicts
    )
    
    streamlit_logger = get_logger("streamlit_app")
    streamlit_logger.info("Streamlit logging initialized successfully")
    
except Exception as e:
    # Fallback to basic logging if our system fails
    import logging
    logging.basicConfig(level=logging.INFO)
    streamlit_logger = logging.getLogger("streamlit_app")
    streamlit_logger.error(f"Failed to initialize comprehensive logging: {e}")
    print(f"Logging fallback: {e}")

from agents import run_orchestrator_job
from models import StreamingUpdate, JobRequest
from config import config


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    streamlit_logger.debug("Initializing Streamlit session state")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        streamlit_logger.debug("Initialized messages list")
    if "job_history" not in st.session_state:
        st.session_state.job_history = []
        streamlit_logger.debug("Initialized job history")
    if "current_job" not in st.session_state:
        st.session_state.current_job = None
        streamlit_logger.debug("Initialized current job state")
    
    streamlit_logger.info("Streamlit session state initialized successfully")


def display_streaming_update(update: StreamingUpdate):
    """Display a streaming update in the chat interface."""
    timestamp = update.timestamp.strftime("%H:%M:%S")
    
    if update.update_type == "status":
        st.info(f"🔄 [{timestamp}] **{update.agent_name}**: {update.message}")
    elif update.update_type == "partial_result":
        st.success(f"✅ [{timestamp}] **{update.agent_name}**: {update.message}")
        if update.data:
            with st.expander(f"View {update.agent_name} Results"):
                st.json(update.data)
    elif update.update_type == "final_result":
        st.success(f"🎉 [{timestamp}] **{update.agent_name}**: {update.message}")
        if update.data:
            with st.expander("View Complete Results"):
                st.json(update.data)
    elif update.update_type == "error":
        st.error(f"❌ [{timestamp}] **{update.agent_name}**: {update.message}")


def display_job_results(final_data: Dict[Any, Any]):
    """Display comprehensive job results in organized tabs."""
    if not final_data:
        return
    
    # Create tabs for different result types
    tabs = []
    tab_names = []
    
    if final_data.get("youtube_data"):
        tab_names.append("📺 YouTube")
        tabs.append("youtube")
    
    if final_data.get("weather_data"):
        tab_names.append("🌤️ Weather")
        tabs.append("weather")
    
    if final_data.get("research_data"):
        tab_names.append("🔍 Research")
        tabs.append("research")
    
    if final_data.get("report_data"):
        tab_names.append("📄 Report")
        tabs.append("report")
    
    if tabs:
        tab_objects = st.tabs(tab_names)
        
        for i, tab_type in enumerate(tabs):
            with tab_objects[i]:
                if tab_type == "youtube":
                    display_youtube_results(final_data["youtube_data"])
                elif tab_type == "weather":
                    display_weather_results(final_data["weather_data"])
                elif tab_type == "research":
                    display_research_results(final_data["research_data"])
                elif tab_type == "report":
                    display_report_results(final_data["report_data"])


def display_youtube_results(youtube_data: Dict[str, Any]):
    """Display YouTube transcript results."""
    st.subheader("YouTube Video Analysis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write(f"**URL:** {youtube_data.get('url', 'N/A')}")
        st.write(f"**Title:** {youtube_data.get('title', 'N/A')}")
        st.write(f"**Channel:** {youtube_data.get('channel', 'N/A')}")
    
    with col2:
        st.write(f"**Duration:** {youtube_data.get('duration', 'N/A')}")
        st.write(f"**Transcript Length:** {len(youtube_data.get('transcript', ''))} chars")
    
    with st.expander("View Full Transcript"):
        st.text_area(
            "Transcript",
            youtube_data.get('transcript', ''),
            height=300,
            disabled=True
        )


def display_weather_results(weather_data: Dict[str, Any]):
    """Display weather forecast results."""
    st.subheader(f"Weather for {weather_data.get('location', 'Unknown')}")
    
    # Current weather
    current = weather_data.get('current', {})
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Temperature", f"{current.get('temp', 'N/A')}°")
    with col2:
        st.metric("Humidity", f"{current.get('humidity', 'N/A')}%")
    with col3:
        st.metric("Wind Speed", f"{current.get('wind_speed', 'N/A')} m/s")
    
    st.write(f"**Conditions:** {current.get('description', 'N/A').title()}")
    
    # Forecast
    forecast = weather_data.get('forecast', [])
    if forecast:
        st.subheader("7-Day Forecast")
        
        for day in forecast[:7]:
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 2])
                with col1:
                    date = datetime.fromisoformat(day['timestamp']).strftime("%Y-%m-%d")
                    st.write(f"**{date}**")
                with col2:
                    st.write(f"{day['temp']}°")
                with col3:
                    st.write(day['description'].title())


def display_research_results(research_data: Dict[str, Any]):
    """Display research pipeline results."""
    st.subheader("Research Results")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pipeline", research_data.get('pipeline_type', 'Unknown').title())
    with col2:
        st.metric("Total Results", research_data.get('total_results', 0))
    with col3:
        processing_time = research_data.get('processing_time', 0)
        st.metric("Processing Time", f"{processing_time:.2f}s")
    
    st.write(f"**Original Query:** {research_data.get('original_query', 'N/A')}")
    
    # Sub-queries
    sub_queries = research_data.get('sub_queries', [])
    if sub_queries:
        st.write("**Sub-queries:**")
        for i, query in enumerate(sub_queries, 1):
            st.write(f"{i}. {query}")
    
    # Results
    results = research_data.get('results', [])
    if results:
        st.subheader("Research Findings")
        
        for i, result in enumerate(results[:10], 1):  # Show top 10
            with st.expander(f"{i}. {result.get('title', 'Untitled')}"):
                st.write(f"**Query:** {result.get('query_variant', 'N/A')}")
                st.write(f"**Snippet:** {result.get('snippet', 'N/A')}")
                if result.get('source_url'):
                    st.write(f"**Source:** {result['source_url']}")
                if result.get('relevance_score'):
                    st.write(f"**Relevance:** {result['relevance_score']:.2f}")


def display_report_results(report_data: Dict[str, Any]):
    """Display generated report results."""
    st.subheader(f"{report_data.get('style', 'Unknown').title()} Report")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Style", report_data.get('style', 'Unknown').title())
    with col2:
        st.metric("Word Count", report_data.get('word_count', 0))
    with col3:
        generation_time = report_data.get('generation_time', 0)
        st.metric("Generation Time", f"{generation_time:.2f}s")
    
    st.write(f"**Source Type:** {report_data.get('source_type', 'Unknown').title()}")
    
    # Final report
    final_report = report_data.get('final', '')
    if final_report:
        st.subheader("Generated Report")
        st.markdown(final_report)
        
        # Download button
        st.download_button(
            label="Download Report",
            data=final_report,
            file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
    
    # Show draft if different
    draft = report_data.get('draft', '')
    if draft and draft != final_report:
        with st.expander("View Draft Version"):
            st.markdown(draft)


async def process_user_input(user_input: str):
    """Process user input through the orchestrator."""
    streamlit_logger.info(f"Processing user input: {user_input}")
    
    # Create placeholder for streaming updates
    status_placeholder = st.empty()
    updates_container = st.container()
    
    final_result = None
    
    try:
        streamlit_logger.debug("Starting orchestrator job with streaming")
        
        # Run orchestrator job with streaming
        async for update in run_orchestrator_job(user_input):
            streamlit_logger.debug(f"Received update: {update.update_type} from {update.agent_name}")
            
            with updates_container:
                display_streaming_update(update)
            
            # Update status
            with status_placeholder:
                if update.update_type == "final_result":
                    st.success("✅ Job completed successfully!")
                    final_result = update.data
                    streamlit_logger.info("Job completed successfully")
                elif update.update_type == "error" and update.agent_name == "Orchestrator":
                    st.error("❌ Job failed")
                    streamlit_logger.error(f"Job failed: {update.message}")
                else:
                    st.info(f"🔄 {update.agent_name}: {update.message}")
        
        # Display final results
        if final_result:
            st.subheader("📊 Complete Results")
            display_job_results(final_result)
            
            # Add to job history
            st.session_state.job_history.append({
                "timestamp": datetime.now(),
                "query": user_input,
                "result": final_result
            })
    
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        streamlit_logger.exception(error_msg)
        st.error(error_msg)


def main():
    """Main Streamlit application."""
    try:
        streamlit_logger.info("Starting Streamlit application")
        
        st.set_page_config(
            page_title="Pydantic-AI Multi-Agent System",
            page_icon="🤖",
            layout="wide"
        )
        
        st.title("🤖 Pydantic-AI Multi-Agent System")
        st.markdown("*Conversational AI with specialized agents for YouTube, Weather, Research, and Report Generation*")
        
        streamlit_logger.debug("Streamlit UI components initialized")
        
        # Initialize session state
        initialize_session_state()
        
    except Exception as e:
        error_msg = f"Error initializing Streamlit app: {str(e)}"
        streamlit_logger.exception(error_msg)
        st.error(f"❌ Application Error: {error_msg}")
        st.error("Please check the logs for detailed error information.")
        return
    
    # Sidebar with configuration and history
    try:
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # API Key status
            try:
                missing_keys = config.validate_required_keys()
                if missing_keys:
                    st.error(f"Missing API keys: {', '.join(missing_keys)}")
                    st.info("Please set the required environment variables.")
                    streamlit_logger.warning(f"Missing API keys: {missing_keys}")
                else:
                    st.success("✅ All required API keys configured")
                    streamlit_logger.info("All required API keys configured")
            except Exception as e:
                error_msg = f"Error validating API keys: {str(e)}"
                streamlit_logger.exception(error_msg)
                st.error(f"❌ {error_msg}")
            
            # Agent status
            st.header("🤖 Available Agents")
            agents = [
                "📺 YouTube Agent",
                "🌤️ Weather Agent", 
                "🔍 Tavily Research",
                "🔍 DuckDuckGo Research",
                "📄 Report Writer",
                "🎯 Orchestrator"
            ]
            for agent in agents:
                st.write(f"✅ {agent}")
            
            # Job history
            if st.session_state.job_history:
                st.header("📋 Job History")
                for i, job in enumerate(reversed(st.session_state.job_history[-5:]), 1):
                    with st.expander(f"Job {len(st.session_state.job_history) - i + 1}"):
                        st.write(f"**Query:** {job['query']}")
                        st.write(f"**Time:** {job['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                        
    except Exception as e:
        error_msg = f"Error in sidebar configuration: {str(e)}"
        streamlit_logger.exception(error_msg)
        st.sidebar.error(f"❌ {error_msg}")
    
    # Main chat interface
    try:
        st.header("💬 Chat Interface")
        streamlit_logger.debug("Rendering chat interface")
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
    except Exception as e:
        error_msg = f"Error rendering chat interface: {str(e)}"
        streamlit_logger.exception(error_msg)
        st.error(f"❌ {error_msg}")
    
    # Chat input
    if prompt := st.chat_input("Enter your request (e.g., 'Research AI trends', 'Weather in New York', 'Analyze YouTube video: URL')"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process request and display response with loading spinner
        with st.chat_message("assistant"):
            with st.spinner("🤖 Processing your request... Please wait while agents work on your task."):
                # Run async function in Streamlit
                asyncio.run(process_user_input(prompt))
        
        # Add assistant response to chat history
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"Processed request: {prompt}"
        })
    
    # Example queries
    st.header("💡 Example Queries")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Research & Reports")
        if st.button("🔍 Research AI trends in 2024"):
            with st.spinner("Adding query to chat..."):
                st.session_state.messages.append({"role": "user", "content": "Research AI trends in 2024"})
                st.rerun()
        
        if st.button("📊 Generate comprehensive report on climate change"):
            with st.spinner("Adding query to chat..."):
                st.session_state.messages.append({"role": "user", "content": "Generate comprehensive report on climate change"})
                st.rerun()
    
    with col2:
        st.subheader("Weather & YouTube")
        if st.button("🌤️ Weather forecast for San Francisco"):
            with st.spinner("Adding query to chat..."):
                st.session_state.messages.append({"role": "user", "content": "Weather forecast for San Francisco"})
                st.rerun()
        
        if st.button("📺 Analyze YouTube video"):
            with st.spinner("Adding query to chat..."):
                st.session_state.messages.append({"role": "user", "content": "Analyze YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
            st.rerun()


if __name__ == "__main__":
    main()
