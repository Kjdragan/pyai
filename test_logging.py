import asyncio
import sys
import os

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.orchestrator_agent import run_orchestrator_job
from models import JobRequest

async def test_research_logging():
    """Test the research logging functionality."""
    print("Testing research logging functionality...")
    
    # Create a simple research request
    test_query = "What are the latest advancements in quantum computing?"
    
    print(f"\nRunning research on: {test_query}")
    print("This will generate log files in the logs directory\n")
    
    # Run the orchestrator job
    async for update in run_orchestrator_job(f"research {test_query}"):
        if update.update_type == "status":
            print(f"[STATUS] {update.message}")
        elif update.update_type == "partial_result":
            print(f"[RESULT] {update.agent_name}: {update.message}")
        elif update.update_type == "error":
            print(f"[ERROR] {update.agent_name}: {update.message}")
        elif update.update_type == "final_result":
            print(f"[FINAL] {update.message}")
    
    print("\nTest completed. Check the logs directory for generated JSON files.")

if __name__ == "__main__":
    asyncio.run(test_research_logging())
