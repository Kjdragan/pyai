"""
Main entry point for the Pydantic-AI Multi-Agent System.
Single Python entrypoint under OpenAI SDK that drives the OrchestratorAgent.
"""

import asyncio
import sys
import os
from typing import Optional

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from agents import run_orchestrator_job
from models import StreamingUpdate


async def main_cli(query: Optional[str] = None):
    """Command-line interface for the multi-agent system."""
    print("🤖 Pydantic-AI Multi-Agent System")
    print("=" * 50)
    
    # Validate configuration
    missing_keys = config.validate_required_keys()
    if missing_keys:
        print(f"❌ Missing required API keys: {', '.join(missing_keys)}")
        print("Please set the following environment variables:")
        for key in missing_keys:
            print(f"  - {key}")
        return
    
    print("✅ Configuration validated")
    print()
    
    # Get query from user if not provided
    if not query:
        print("Available job types:")
        print("  📺 YouTube: 'Analyze YouTube video: <URL>'")
        print("  🌤️ Weather: 'Weather forecast for <location>'")
        print("  🔍 Research: 'Research <topic>'")
        print("  📄 Report: 'Generate <style> report on <topic>'")
        print()
        
        query = input("Enter your request: ").strip()
        if not query:
            print("No query provided. Exiting.")
            return
    
    print(f"Processing: {query}")
    print("-" * 50)
    
    try:
        # Process through orchestrator
        async for update in run_orchestrator_job(query):
            timestamp = update.timestamp.strftime("%H:%M:%S")
            
            if update.update_type == "status":
                print(f"🔄 [{timestamp}] {update.agent_name}: {update.message}")
            elif update.update_type == "partial_result":
                print(f"✅ [{timestamp}] {update.agent_name}: {update.message}")
            elif update.update_type == "final_result":
                print(f"🎉 [{timestamp}] {update.agent_name}: {update.message}")
                print()
                print("=" * 50)
                print("📊 FINAL RESULTS")
                print("=" * 50)
                
                if update.data:
                    result = update.data
                    
                    # Display summary
                    print(f"Job Type: {result.get('job_request', {}).get('job_type', 'Unknown')}")
                    print(f"Query: {result.get('job_request', {}).get('query', 'Unknown')}")
                    print(f"Agents Used: {', '.join(result.get('agents_used', []))}")
                    print(f"Processing Time: {result.get('total_processing_time', 0):.2f}s")
                    print(f"Success: {'✅' if result.get('success') else '❌'}")
                    
                    if result.get('errors'):
                        print(f"Errors: {', '.join(result['errors'])}")
                    
                    print()
                    
                    # Display specific results
                    if result.get('youtube_data'):
                        print("📺 YouTube Results:")
                        yt_data = result['youtube_data']
                        print(f"  URL: {yt_data.get('url')}")
                        print(f"  Transcript Length: {len(yt_data.get('transcript', ''))} characters")
                        print()
                    
                    if result.get('weather_data'):
                        print("🌤️ Weather Results:")
                        weather = result['weather_data']
                        current = weather.get('current', {})
                        print(f"  Location: {weather.get('location')}")
                        print(f"  Current: {current.get('temp')}° - {current.get('description')}")
                        print(f"  Forecast: {len(weather.get('forecast', []))} days")
                        print()
                    
                    if result.get('research_data'):
                        print("🔍 Research Results:")
                        research = result['research_data']
                        print(f"  Pipeline: {research.get('pipeline_type')}")
                        print(f"  Original Query: {research.get('original_query')}")
                        print(f"  Sub-queries: {len(research.get('sub_queries', []))}")
                        print(f"  Total Results: {research.get('total_results')}")
                        print()
                    
                    if result.get('report_data'):
                        print("📄 Report Results:")
                        report = result['report_data']
                        print(f"  Style: {report.get('style')}")
                        print(f"  Source Type: {report.get('source_type')}")
                        print(f"  Word Count: {report.get('word_count')}")
                        print()
                        print("Generated Report:")
                        print("-" * 30)
                        print(report.get('final', 'No report content'))
                        print("-" * 30)
                
            elif update.update_type == "error":
                print(f"❌ [{timestamp}] {update.agent_name}: {update.message}")
    
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def run_streamlit():
    """Launch the Streamlit web interface."""
    import subprocess
    import sys
    
    print("🚀 Launching Streamlit web interface...")
    
    # Run streamlit app
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        "src/streamlit_app.py",
        "--server.port", str(config.STREAMLIT_PORT),
        "--server.address", config.STREAMLIT_HOST
    ])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pydantic-AI Multi-Agent System")
    parser.add_argument("--web", action="store_true", help="Launch Streamlit web interface")
    parser.add_argument("--query", type=str, help="Query to process (CLI mode)")
    
    args = parser.parse_args()
    
    if args.web:
        run_streamlit()
    else:
        asyncio.run(main_cli(args.query))
