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
    """Fetch transcript and comprehensive metadata for a YouTube video using proper API patterns."""
    if languages is None:
        languages = ['en', 'en-US', 'en-GB']  # Default language preferences
    
    try:
        # Initialize YouTube Transcript API (proper pattern)
        ytt_api = YouTubeTranscriptApi()
        
        # List available transcripts first
        transcript_list = ytt_api.list(video_id)
        
        # Find the best available transcript
        try:
            # Try to find manually created transcript first
            transcript = transcript_list.find_manually_created_transcript(languages)
        except NoTranscriptFound:
            try:
                # Fall back to auto-generated transcript
                transcript = transcript_list.find_generated_transcript(languages)
            except NoTranscriptFound:
                # Try any available transcript
                transcript = transcript_list.find_transcript(languages)
        
        # Fetch the actual transcript data
        fetched_transcript = transcript.fetch()
        
        # Extract text using proper API methods
        transcript_text = " ".join([snippet.text for snippet in fetched_transcript])
        
        # Comprehensive metadata
        metadata = {
            "video_id": video_id,
            "language": fetched_transcript.language,
            "language_code": fetched_transcript.language_code,
            "is_generated": fetched_transcript.is_generated,
            "transcript_length": len(transcript_text),
            "segments_count": len(fetched_transcript),
            "is_translatable": transcript.is_translatable,
            "available_languages": [t.language_code for t in transcript_list],
            "translation_languages": transcript.translation_languages if hasattr(transcript, 'translation_languages') else [],
            "duration_seconds": sum(snippet.duration for snippet in fetched_transcript),
            "first_segment_start": fetched_transcript[0].start if fetched_transcript else 0,
            "last_segment_end": (fetched_transcript[-1].start + fetched_transcript[-1].duration) if fetched_transcript else 0
        }
        
        return transcript_text, metadata
        
    except VideoUnavailable as e:
        raise ValueError(f"Video unavailable: {str(e)}")
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise ValueError(f"No transcript available for video {video_id}. Available languages: {', '.join(languages)}. Error: {str(e)}")
    except Exception as e:
        error_msg = str(e)
        # Handle common YouTube API errors generically
        if "blocked" in error_msg.lower() or "ip" in error_msg.lower():
            raise ValueError(f"Request blocked by YouTube (possible IP ban): {error_msg}. Consider using proxy configuration.")
        elif "rate" in error_msg.lower() or "too many" in error_msg.lower():
            raise ValueError(f"Rate limit exceeded: {error_msg}. Please try again later.")
        else:
            raise ValueError(f"Unexpected error fetching transcript for video {video_id}: {error_msg}")


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
               f"Available languages: {', '.join(metadata['available_languages'])}\n" \
               f"Transcript length: {len(transcript)} characters\n\n" \
               f"Transcript:\n{transcript}"
               
    except Exception as e:
        return f"Error fetching transcript for {url}: {str(e)}"


async def process_youtube_request(url: str) -> AgentResponse:
    """Process YouTube transcript request."""
    logger = get_agent_logger("YouTubeAgent")
    
    with logger.logging_manager.log_agent_execution("YouTubeAgent", f"Process YouTube URL: {url}") as agent_logger:
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
            agent_logger.debug("Fetching YouTube transcript")
            transcript, metadata = await fetch_youtube_transcript(video_id)
            
            agent_logger.info(f"Transcript fetched successfully - Length: {len(transcript)} chars, Language: {metadata.get('language')}")
            
            # Create agent dependencies
            deps = YouTubeAgentDeps()
            
            # Run agent with transcript data
            agent_logger.debug("Running Pydantic AI agent for transcript analysis")
            agent_logger.log_model_call(config.YOUTUBE_MODEL, len(transcript))
            
            result = await youtube_agent.run(
                user_prompt=f"Extract and analyze transcript for video: {url}",
                deps=deps
            )
            
            response_data = {
                "video_id": video_id,
                "url": url,
                "transcript": transcript,
                "metadata": metadata,
                "analysis": result.data.model_dump() if result.data else None
            }
            
            agent_logger.info(f"YouTube processing completed successfully for video {video_id}")
            
            return AgentResponse(
                success=True,
                data=response_data
            )
            
        except Exception as e:
            agent_logger.error(f"YouTube processing failed for URL {url}: {str(e)}")
            return AgentResponse(
                success=False,
                error=f"YouTube processing failed: {str(e)}"
            )
