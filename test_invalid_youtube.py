#!/usr/bin/env python3
"""
Test the YouTube agent directly with invalid URL.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.youtube_agent import process_youtube_request


async def test_invalid_youtube():
    """Test YouTube agent with invalid URL."""
    
    print("🧪 Testing YouTube agent with invalid URL")
    print("=" * 60)
    
    invalid_url = "https://www.youtube.com/"
    
    print(f"Testing URL: {invalid_url}")
    
    result = await process_youtube_request(invalid_url)
    
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print(f"Data: {result.data}")


if __name__ == "__main__":
    asyncio.run(test_invalid_youtube())