#!/usr/bin/env python3
"""
Debug script to test invalid YouTube URL handling.
"""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.youtube_agent import extract_video_id
from agents.orchestrator_agent import extract_youtube_url


def test_invalid_url():
    """Test how the system handles invalid YouTube URLs."""
    
    invalid_urls = [
        "https://www.youtube.com/",
        "https://youtube.com/",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?",
        "not a url at all"
    ]
    
    print("🧪 Testing Invalid YouTube URL Handling")
    print("=" * 60)
    
    for url in invalid_urls:
        print(f"\n🔍 Testing URL: '{url}'")
        
        # Test orchestrator extraction
        orchestrator_result = extract_youtube_url(url)
        print(f"  Orchestrator extract: '{orchestrator_result}'")
        
        # Test video ID extraction  
        video_id = extract_video_id(orchestrator_result)
        print(f"  Video ID extracted: '{video_id}'")
        
        if not video_id:
            print(f"  ✅ Correctly identified as invalid")
        else:
            print(f"  ❌ Incorrectly thought '{video_id}' was valid")


if __name__ == "__main__":
    test_invalid_url()