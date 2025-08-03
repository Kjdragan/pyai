"""
YouTube Agent for fetching video transcripts and metadata.
"""

import asyncio
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from models import YouTubeTranscriptModel, AgentResponse
from config import config


class YouTubeAgentDeps:
    """Dependencies for YouTube Agent."""
    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def fetch_youtube_transcript(video_id: str) -> tuple[str, dict]:
    """Fetch transcript and basic metadata for a YouTube video."""
    try:
        # Get transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([item['text'] for item in transcript_list])
        
        # Basic metadata (limited without YouTube API)
        metadata = {
            "video_id": video_id,
            "transcript_length": len(transcript_text),
            "segments_count": len(transcript_list)
        }
        
        return transcript_text, metadata
        
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise ValueError(f"Transcript not available: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error fetching transcript: {str(e)}")


# Create YouTube Agent
youtube_agent = Agent(
    model=OpenAIModel(config.YOUTUBE_MODEL),
    output_type=YouTubeTranscriptModel,
    deps_type=YouTubeAgentDeps,
    system_prompt="""
    You are a YouTube transcript extraction agent. Your job is to:
    1. Extract video ID from YouTube URLs
    2. Fetch video transcripts using the YouTube Transcript API
    3. Return structured data with transcript and metadata
    
    Always validate URLs and handle errors gracefully.
    Return comprehensive transcript data in the specified format.
    """,
    retries=config.MAX_RETRIES
)


@youtube_agent.tool
async def get_youtube_transcript(ctx: RunContext[YouTubeAgentDeps], url: str) -> str:
    """Tool to fetch YouTube transcript from URL."""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return f"Error: Invalid YouTube URL format: {url}"
        
        transcript, metadata = await fetch_youtube_transcript(video_id)
        
        return f"Successfully fetched transcript for video {video_id}. " \
               f"Transcript length: {len(transcript)} characters. " \
               f"Metadata: {metadata}"
               
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"


async def process_youtube_request(url: str) -> AgentResponse:
    """Process YouTube transcript request."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Extract video ID
        video_id = extract_video_id(url)
        if not video_id:
            return AgentResponse(
                agent_name="YouTubeAgent",
                success=False,
                error="Invalid YouTube URL format"
            )
        
        # Fetch transcript and metadata
        transcript, metadata = await fetch_youtube_transcript(video_id)
        
        # Create result model
        result = YouTubeTranscriptModel(
            url=url,
            transcript=transcript,
            metadata=metadata,
            title=metadata.get("title"),
            duration=metadata.get("duration"),
            channel=metadata.get("channel")
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return AgentResponse(
            agent_name="YouTubeAgent",
            success=True,
            data=result.model_dump(),
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="YouTubeAgent",
            success=False,
            error=str(e),
            processing_time=processing_time
        )
