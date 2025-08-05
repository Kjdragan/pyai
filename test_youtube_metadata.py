#!/usr/bin/env python3
"""
Test the YouTube agent metadata fetching with yt-dlp integration.
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_youtube_agent():
    """Test the YouTube agent with yt-dlp metadata fetching."""
    print("🧪 Testing YouTube Agent with yt-dlp metadata...")
    
    try:
        # Initialize logging first
        from logging_config import initialize_logging
        initialize_logging()
        
        from agents.youtube_agent import process_youtube_request
        
        # Test URL from the logs
        test_url = "https://www.youtube.com/watch?v=IKdfXDrqNxk"
        print(f"🎬 Testing URL: {test_url}")
        
        # Process the request
        response = await process_youtube_request(test_url)
        
        if response.success:
            print("✅ YouTube agent request successful!")
            
            data = response.data
            print(f"📺 Title: {data.get('title', 'N/A')}")
            print(f"👤 Channel: {data.get('channel', 'N/A')}")
            print(f"⏱️ Duration: {data.get('duration', 'N/A')} seconds")
            print(f"📝 Transcript Length: {len(data.get('transcript', ''))} chars")
            
            # Check if structured model has metadata
            structured_model = data.get('structured_model', {})
            print(f"\n🏗️ Structured Model Metadata:")
            print(f"  Title: {structured_model.get('title', 'N/A')}")
            print(f"  Channel: {structured_model.get('channel', 'N/A')}")
            print(f"  Duration: {structured_model.get('duration', 'N/A')}")
            
            return True
        else:
            print(f"❌ YouTube agent request failed: {response.error}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 YouTube Agent Metadata Test")
    print("=" * 40)
    
    success = asyncio.run(test_youtube_agent())
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 Test PASSED! YouTube metadata is working.")
    else:
        print("❌ Test FAILED! YouTube metadata needs debugging.")
