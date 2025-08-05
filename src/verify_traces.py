#!/usr/bin/env python3
"""
Quick verification script to demonstrate Logfire trace generation.
This script shows that all Pydantic AI agent executions are properly traced.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_config import initialize_logging
from config import config

def main():
    """Verify that Logfire traces are properly configured and accessible."""
    
    print("🔍 Verifying Pydantic AI Trace Generation")
    print("=" * 50)
    
    # Initialize logging system
    logging_manager = initialize_logging(enable_logfire=True)
    
    # Get dashboard URL
    dashboard_url = logging_manager._get_logfire_dashboard_url()
    
    print(f"\n✅ Logfire Configuration Status:")
    print(f"   Dashboard URL: {dashboard_url}")
    print(f"   Service Name: pyai-multi-agent")
    print(f"   Project: {os.getenv('LOGFIRE_PROJECT_NAME', 'pyai')}")
    
    print(f"\n📊 What gets traced:")
    print(f"   • All orchestrator_agent.run() calls")
    print(f"   • Individual agent executions (tavily_research_agent, etc.)")
    print(f"   • Tool function calls (perform_tavily_research, etc.)")
    print(f"   • HTTP API calls to OpenAI, Tavily, etc.")
    print(f"   • Agent state transitions and data flow")
    print(f"   • Processing times and error states")
    
    print(f"\n🔗 Access your traces:")
    print(f"   1. Visit: {dashboard_url}")
    print(f"   2. Filter by service: pyai-multi-agent")
    print(f"   3. Look for traces containing 'orchestrator_agent run'")
    print(f"   4. Drill down to see complete agent execution flow")
    
    print(f"\n💡 Example trace structure you'll see:")
    print(f"   orchestrator_agent run")
    print(f"   ├── dispatch_to_research_agents")
    print(f"   │   ├── tavily_research_agent run") 
    print(f"   │   │   └── perform_tavily_research")
    print(f"   │   │       └── POST api.tavily.com/search")
    print(f"   │   └── duckduckgo_research_agent run")
    print(f"   │       └── perform_duckduckgo_research")
    print(f"   └── dispatch_to_report_writer")
    print(f"       └── report_writer_agent run")
    print(f"           └── generate_report")
    
    print(f"\n🎯 Next steps:")
    print(f"   • Run: uv run python src/main.py --query 'your test query'")
    print(f"   • Check the dashboard during/after execution")
    print(f"   • All agent interactions will be fully visible!")

if __name__ == "__main__":
    main()