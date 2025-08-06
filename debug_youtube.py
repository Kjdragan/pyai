#!/usr/bin/env python3
"""
Debug script to test YouTube transcript fetching.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.youtube_agent import fetch_youtube_transcript, extract_video_id
from youtube_transcript_api import YouTubeTranscriptApi


async def test_youtube_transcript():
    """Test YouTube transcript fetching with a known working video."""
    
    # Use a known video that should have transcripts
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - famous video
        "https://youtu.be/dQw4w9WgXcQ",                # Short URL format
    ]
    
    for url in test_urls:
        print(f"\n🧪 Testing URL: {url}")
        print("-" * 60)
        
        # Test video ID extraction
        video_id = extract_video_id(url)
        print(f"Extracted video ID: {video_id}")
        
        if not video_id:
            print("❌ Failed to extract video ID")
            continue
            
        try:
            # Test direct YouTube Transcript API
            print("📝 Testing direct YouTube Transcript API...")
            ytt_api = YouTubeTranscriptApi()
            
            # List available transcripts
            transcript_list = ytt_api.list(video_id)
            print(f"Available transcripts: {len(transcript_list)}")
            
            for transcript in transcript_list:
                print(f"  - Language: {transcript.language} ({transcript.language_code})")
                print(f"    Generated: {transcript.is_generated}")
                print(f"    Can translate: {transcript.is_translatable}")
            
            # Try to fetch transcript
            transcript_data = ytt_api.fetch(video_id)
            print(f"✅ Transcript fetched successfully!")
            print(f"   Language: {transcript_data.language}")
            print(f"   Segments: {len(transcript_data.snippets)}")
            print(f"   First few words: {transcript_data.snippets[0].text[:50] if transcript_data.snippets else 'No content'}")
            
        except Exception as e:
            print(f"❌ Direct API test failed: {str(e)}")
            print(f"   Error type: {type(e).__name__}")
            
        try:
            # Test our wrapper function
            print("\n🔧 Testing our wrapper function...")
            transcript, metadata = await fetch_youtube_transcript(video_id)
            print(f"✅ Wrapper function succeeded!")
            print(f"   Length: {len(transcript)} characters")
            print(f"   Metadata: {metadata}")
            
        except Exception as e:
            print(f"❌ Wrapper function failed: {str(e)}")
            print(f"   Error type: {type(e).__name__}")


if __name__ == "__main__":
    asyncio.run(test_youtube_transcript())