"""
YouTube Agent for fetching video transcripts and metadata.
"""

import asyncio
from typing import Optional, List, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, 
    NoTranscriptFound, 
    VideoUnavailable
)
# Note: Some error classes may not be available in all versions
from youtube_transcript_api.formatters import TextFormatter, JSONFormatter
import re
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from models import YouTubeTranscriptModel, AgentResponse
from config import config
from logging_config import get_agent_logger


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


async def fetch_youtube_transcript(video_id: str, languages: List[str] = None) -> tuple[str, dict]:
    """Get transcript using the new API. Simple."""
    try:
        # Use new instance-based API
        ytt_api = YouTubeTranscriptApi()
        transcript_data = ytt_api.fetch(video_id, languages=languages or ['en'])
        
        # Extract text from snippets
        transcript_text = " ".join([snippet.text for snippet in transcript_data.snippets])
        
        # Simple metadata
        metadata = {
            "video_id": transcript_data.video_id,
            "language": transcript_data.language,
            "language_code": transcript_data.language_code,
            "is_generated": transcript_data.is_generated,
            "transcript_length": len(transcript_text),
            "segments_count": len(transcript_data.snippets),
            "duration_seconds": sum(snippet.duration for snippet in transcript_data.snippets)
        }
        
        return transcript_text, metadata
        
    except Exception as e:
        raise ValueError(f"No transcript available for video {video_id}: {str(e)}")


# Create YouTube Agent
youtube_agent = Agent(
    model=OpenAIModel(config.YOUTUBE_MODEL),
    output_type=YouTubeTranscriptModel,
    deps_type=YouTubeAgentDeps,
    system_prompt="""
    You are a YouTube transcript analysis agent. You receive pre-fetched transcript data and create structured output.
    
    You will be provided with:
    - A YouTube URL
    - Video ID
    - Pre-fetched transcript text
    - Metadata about the transcript
    
    Your job is to create a structured YouTubeTranscriptModel with:
    - url: The YouTube URL (must be valid)
    - transcript: The full transcript text
    - metadata: The transcript metadata
    - title: Optional video title (leave None if not provided)
    - duration: Optional duration string (leave None if not provided) 
    - channel: Optional channel name (leave None if not provided)
    
    Always use the provided data to construct the model properly.
    """,
    retries=config.MAX_RETRIES
)


@youtube_agent.tool
async def get_youtube_transcript(ctx: RunContext[YouTubeAgentDeps], url: str, languages: str = "en,en-US,en-GB") -> str:
    """Tool to fetch YouTube transcript from URL with language preferences.
    
    Args:
        url: YouTube video URL
        languages: Comma-separated list of preferred languages (e.g., "en,de,fr")
    """
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return f"Error: Invalid YouTube URL format: {url}"
        
        # Parse language preferences
        language_list = [lang.strip() for lang in languages.split(',')]
        
        transcript, metadata = await fetch_youtube_transcript(video_id, language_list)
        
        return f"Successfully fetched transcript for video {video_id}:\n" \
               f"Language: {metadata['language']} ({metadata['language_code']})\n" \
               f"Type: {'Auto-generated' if metadata['is_generated'] else 'Manual'}\n" \
               f"Duration: {metadata['duration_seconds']:.1f} seconds\n" \
               f"Segments: {metadata['segments_count']}\n" \
               f"Transcript length: {len(transcript)} characters\n\n" \
               f"Transcript:\n{transcript}"
               
    except Exception as e:
        return f"Error fetching transcript for {url}: {str(e)}"


async def process_youtube_request(url: str) -> AgentResponse:
    """Process YouTube transcript request."""
    from logging_config import get_logging_manager
    
    logging_manager = get_logging_manager()
    with logging_manager.log_agent_execution("YouTubeAgent", f"Process YouTube URL: {url}") as agent_logger:
        try:
            # Extract video ID
            agent_logger.debug(f"Extracting video ID from URL: {url}")
            video_id = extract_video_id(url)
            if not video_id:
                agent_logger.warning(f"Invalid YouTube URL format: {url}")
                return AgentResponse(
                    success=False,
                    error=f"Invalid YouTube URL format: {url}"
                )
            
            agent_logger.info(f"Processing video ID: {video_id}")
            
            # Fetch transcript
            agent_logger.info("Fetching YouTube transcript...")
            transcript, metadata = await fetch_youtube_transcript(video_id)
            
            agent_logger.info(f"✅ Transcript fetched - Length: {len(transcript)} chars, Language: {metadata.get('language')}")
            
            # Create structured YouTube transcript model directly
            agent_logger.info("📋 Creating structured transcript model...")
            
            youtube_model = YouTubeTranscriptModel(
                url=url,
                transcript=transcript,
                metadata=metadata
            )
            
            response_data = {
                "video_id": video_id,
                "url": url,
                "transcript": transcript,
                "metadata": metadata,
                "structured_model": youtube_model.model_dump()
            }
            
            agent_logger.info(f"YouTube processing completed successfully for video {video_id}")
            
            return AgentResponse(
                agent_name="YouTubeAgent",
                success=True,
                data=response_data
            )
            
        except Exception as e:
            agent_logger.error(f"YouTube processing failed for URL {url}: {str(e)}")
            return AgentResponse(
                agent_name="YouTubeAgent",
                success=False,
                error=f"YouTube processing failed: {str(e)}"
            )
