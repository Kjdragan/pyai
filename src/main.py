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

# Run hygiene cleanup tasks at startup
from hygiene import run_hygiene_tasks
run_hygiene_tasks()

# Initialize comprehensive logging system
from logging_config import initialize_logging, get_logger
logging_manager = initialize_logging(
    logs_dir=os.path.join(os.path.dirname(__file__), "logs"),
    enable_logfire=True
)
system_logger = get_logger("main")

from config import config
from agents import run_orchestrator_job
from models import StreamingUpdate


async def main_cli(query: Optional[str] = None):
    """Command-line interface for the multi-agent system."""
    system_logger.info("Starting Pydantic-AI Multi-Agent System CLI")
    
    print("🤖 Pydantic-AI Multi-Agent System")
    print("=" * 50)
    
    # Validate configuration
    system_logger.debug("Validating configuration")
    missing_keys = config.validate_required_keys()
    if missing_keys:
        system_logger.error(f"Missing required API keys: {missing_keys}")
        print(f"❌ Missing required API keys: {', '.join(missing_keys)}")
        print("Please set the following environment variables:")
        for key in missing_keys:
            print(f"  - {key}")
        return
    
    system_logger.info("Configuration validation successful")
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
            system_logger.info("No query provided, exiting CLI")
            print("No query provided. Exiting.")
            return
    
    system_logger.info(f"Processing user query: {query}")
    print(f"Processing: {query}")
    print("-" * 50)
    
    try:
        # Process through orchestrator
        system_logger.debug("Starting orchestrator job execution")
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
                system_logger.error(f"Agent error - {update.agent_name}: {update.message}")
                print(f"❌ [{timestamp}] {update.agent_name}: {update.message}")
    
    except KeyboardInterrupt:
        system_logger.info("CLI process interrupted by user")
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        system_logger.exception(f"Unexpected error in CLI: {str(e)}")
        print(f"❌ Error: {str(e)}")
    
    system_logger.info("CLI session completed")


def run_streamlit():
    """Launch the Streamlit web interface."""
    import subprocess
    import sys
    import os
    
    system_logger.info(f"Launching Streamlit web interface on {config.STREAMLIT_HOST}:{config.STREAMLIT_PORT}")
    print("🚀 Launching Streamlit web interface...")
    
    try:
        # Determine correct path to streamlit_app.py
        current_dir = os.getcwd()
        if current_dir.endswith('/src'):
            streamlit_path = "streamlit_app.py"
        else:
            streamlit_path = "src/streamlit_app.py"
        
        system_logger.debug(f"Current directory: {current_dir}")
        system_logger.debug(f"Streamlit app path: {streamlit_path}")
        
        # Verify file exists
        if not os.path.exists(streamlit_path):
            error_msg = f"Streamlit app not found at: {streamlit_path}"
            system_logger.error(error_msg)
            print(f"❌ {error_msg}")
            return
        
        # Run streamlit app with output capture
        system_logger.info("Starting Streamlit subprocess with output capture")
        
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", 
            streamlit_path,
            "--server.port", str(config.STREAMLIT_PORT),
            "--server.address", config.STREAMLIT_HOST
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
        
        # Stream output in real-time
        import threading
        
        def log_output(pipe, log_func, prefix):
            """Log subprocess output line by line."""
            try:
                for line in iter(pipe.readline, ''):
                    if line.strip():
                        log_func(f"[{prefix}] {line.strip()}")
            except Exception as e:
                system_logger.error(f"Error reading {prefix}: {e}")
            finally:
                pipe.close()
        
        # Start threads to capture stdout and stderr
        stdout_thread = threading.Thread(
            target=log_output, 
            args=(process.stdout, system_logger.info, "streamlit-stdout")
        )
        stderr_thread = threading.Thread(
            target=log_output, 
            args=(process.stderr, system_logger.error, "streamlit-stderr")
        )
        
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process completion
        return_code = process.wait()
        
        # Wait for logging threads to finish
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        
        system_logger.info(f"Streamlit process completed with return code: {return_code}")
    except Exception as e:
        system_logger.exception(f"Error launching Streamlit: {str(e)}")
        print(f"❌ Error launching Streamlit: {str(e)}")
        raise


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
