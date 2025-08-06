#!/usr/bin/env python3
"""
Test the YouTube agent tool directly.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.youtube_agent import get_youtube_transcript, YouTubeAgentDeps
from pydantic_ai import RunContext


async def test_youtube_tool():
    """Test YouTube agent tool with invalid URL."""
    
    print("🧪 Testing YouTube tool with invalid URL")
    print("=" * 60)
    
    invalid_url = "https://www.youtube.com/"
    
    print(f"Testing URL: {invalid_url}")
    
    # Create mock context
    deps = YouTubeAgentDeps()
    ctx = RunContext(deps=deps, usage=None)
    
    result = await get_youtube_transcript(ctx, invalid_url)
    
    print(f"Tool result: {result}")


if __name__ == "__main__":
    asyncio.run(test_youtube_tool())