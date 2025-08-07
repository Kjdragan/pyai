"""
YouTube Agent for fetching video transcripts and metadata.
"""

import asyncio
import time
import httpx
from typing import Optional, List, Dict, Any
import re
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

# Commenting out old API imports - replaced with YouTube Data API
# from youtube_transcript_api import YouTubeTranscriptApi
# from youtube_transcript_api._errors import (
#     TranscriptsDisabled, 
#     NoTranscriptFound, 
#     VideoUnavailable
# )
# from youtube_transcript_api.formatters import TextFormatter, JSONFormatter

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


# COMMENTED OUT: Old implementation using youtube-transcript-api and yt-dlp
# async def fetch_youtube_transcript(video_id: str, languages: List[str] = None) -> tuple[str, dict]:
#     """Get transcript using the old transcript API. REPLACED with YouTube Data API."""
#     try:
#         # Use old instance-based API
#         ytt_api = YouTubeTranscriptApi()
#         transcript_data = ytt_api.fetch(video_id, languages=languages or ['en'])
#         
#         # Extract text from snippets
#         transcript_text = " ".join([snippet.text for snippet in transcript_data.snippets])
#         
#         # Simple metadata
#         metadata = {
#             "video_id": transcript_data.video_id,
#             "language": transcript_data.language,
#             "language_code": transcript_data.language_code,
#             "is_generated": transcript_data.is_generated,
#             "transcript_length": len(transcript_text),
#             "segments_count": len(transcript_data.snippets),
#             "duration_seconds": sum(snippet.duration for snippet in transcript_data.snippets)
#         }
#         
#         return transcript_text, metadata
#         
#     except Exception as e:
#         raise ValueError(f"No transcript available for video {video_id}: {str(e)}")


async def fetch_youtube_hybrid_api(video_id: str, languages: List[str] = None) -> tuple[str, dict, dict]:
    """
    HYBRID IMPLEMENTATION: Use YouTube Data API for metadata + youtube-transcript-api for transcripts.
    This gives us the best of both worlds: fast official metadata + reliable transcript access.
    Returns: (transcript_text, metadata, performance_timing)
    """
    start_time = time.time()
    performance_timing = {
        "total_time": 0,
        "metadata_fetch_time": 0,
        "transcript_fetch_time": 0,
        "api_calls_count": 1,  # One API call to Data API
        "method": "hybrid_youtube_data_api_plus_transcript_api"
    }
    
    if not config.YOUTUBE_DATA_API_KEY:
        raise ValueError("YouTube Data API key not configured")
    
    # PARALLEL EXECUTION: Run both metadata and transcript fetches concurrently for maximum speed!
    async def fetch_metadata():
        """Fetch video metadata using YouTube Data API"""
        metadata_start = time.time()
        async with httpx.AsyncClient() as client:
            try:
                video_url = "https://www.googleapis.com/youtube/v3/videos"
                video_params = {
                    "part": "snippet,contentDetails,statistics",
                    "id": video_id,
                    "key": config.YOUTUBE_DATA_API_KEY
                }
                
                video_response = await client.get(video_url, params=video_params)
                video_response.raise_for_status()
                video_data = video_response.json()
                fetch_time = time.time() - metadata_start
                
                if not video_data.get("items"):
                    raise ValueError(f"Video not found: {video_id}")
                
                video_info = video_data["items"][0]
                return {
                    "snippet": video_info["snippet"],
                    "content_details": video_info["contentDetails"],
                    "statistics": video_info.get("statistics", {}),
                    "fetch_time": fetch_time
                }
                
            except httpx.HTTPStatusError as e:
                raise ValueError(f"YouTube Data API metadata error: {e.response.status_code} - {e.response.text}")
    
    async def fetch_transcript():
        """Fetch transcript using youtube-transcript-api"""
        transcript_start = time.time()
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            ytt_api = YouTubeTranscriptApi()
            preferred_langs = languages or ['en', 'en-US', 'en-GB']
            transcript_data = ytt_api.fetch(video_id, languages=preferred_langs)
            
            # Extract text from snippets
            transcript_text = " ".join([snippet.text for snippet in transcript_data.snippets])
            
            return {
                "transcript_text": transcript_text,
                "language": transcript_data.language,
                "language_code": transcript_data.language_code,
                "is_generated": transcript_data.is_generated,
                "segments_count": len(transcript_data.snippets),
                "transcript_duration": sum(snippet.duration for snippet in transcript_data.snippets),
                "fetch_time": time.time() - transcript_start
            }
            
        except Exception as e:
            return {
                "transcript_text": f"[Transcript not available: {str(e)}]",
                "language": "en",
                "language_code": "en",
                "is_generated": False,
                "segments_count": 0,
                "transcript_duration": 0,
                "fetch_time": time.time() - transcript_start,
                "error": str(e)
            }
    
    # Execute both operations in parallel using asyncio.gather
    metadata_result, transcript_result = await asyncio.gather(
        fetch_metadata(),
        fetch_transcript(),
        return_exceptions=True
    )
    
    # Handle any exceptions from parallel execution
    if isinstance(metadata_result, Exception):
        performance_timing["total_time"] = time.time() - start_time
        raise metadata_result
    
    if isinstance(transcript_result, Exception):
        # If transcript fails, continue with empty transcript
        transcript_result = {
            "transcript_text": f"[Transcript fetch failed: {str(transcript_result)}]",
            "language": "en",
            "language_code": "en", 
            "is_generated": False,
            "segments_count": 0,
            "transcript_duration": 0,
            "fetch_time": 0,
            "error": str(transcript_result)
        }
    
    # Update performance timing with parallel execution results
    performance_timing["metadata_fetch_time"] = metadata_result["fetch_time"]
    performance_timing["transcript_fetch_time"] = transcript_result["fetch_time"]
    
    # Extract results
    snippet = metadata_result["snippet"]
    content_details = metadata_result["content_details"]
    statistics = metadata_result["statistics"]
    
    transcript_text = transcript_result["transcript_text"]
    transcript_language = transcript_result["language"]
    transcript_language_code = transcript_result["language_code"]
    is_generated = transcript_result["is_generated"]
    segments_count = transcript_result["segments_count"]
    transcript_duration = transcript_result["transcript_duration"]
    
    # Step 3: Combine metadata from both sources
    duration_seconds = parse_iso_duration(content_details.get("duration", "PT0S"))
    
    # Create comprehensive metadata combining YouTube Data API + transcript info
    metadata = {
        "video_id": video_id,
        "language": transcript_language,
        "language_code": transcript_language_code,
        "is_generated": is_generated,
        "transcript_length": len(transcript_text),
        "segments_count": segments_count,
        "duration_seconds": duration_seconds,
        "transcript_duration_seconds": transcript_duration,
        # Enhanced metadata from YouTube Data API (MUCH faster than yt-dlp!)
        "title": snippet.get("title"),
        "channel": snippet.get("channelTitle"),
        "channel_id": snippet.get("channelId"),
        "published_at": snippet.get("publishedAt"),
        "description": snippet.get("description", "")[:500],  # Truncate description
        "view_count": int(statistics.get("viewCount", 0)),
        "like_count": int(statistics.get("likeCount", 0)),
        "comment_count": int(statistics.get("commentCount", 0)),
        "category_id": snippet.get("categoryId"),
        "tags": snippet.get("tags", [])[:10],  # Limit tags
        "default_language": snippet.get("defaultLanguage"),
        "default_audio_language": snippet.get("defaultAudioLanguage"),
    }
    
    performance_timing["total_time"] = time.time() - start_time
    
    return transcript_text, metadata, performance_timing


def parse_srt_to_text(srt_content: str) -> str:
    """Parse SRT subtitle content and extract just the text."""
    lines = srt_content.strip().split('\n')
    text_parts = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip subtitle number lines (digits only)
        if line.isdigit():
            i += 1
            continue
        
        # Skip timestamp lines (contains " --> ")
        if " --> " in line:
            i += 1
            continue
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # This should be subtitle text
        text_parts.append(line)
        i += 1
    
    return " ".join(text_parts)


def parse_iso_duration(duration: str) -> float:
    """Parse ISO 8601 duration (PT4M13S) to seconds."""
    import re
    
    # Match PT4M13S format
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', duration)
    if not match:
        return 0.0
    
    hours, minutes, seconds = match.groups()
    total_seconds = 0.0
    
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += float(seconds)
    
    return total_seconds


async def fetch_youtube_fallback(video_id: str, agent_logger=None) -> dict:
    """
    FALLBACK: Use old implementation (youtube-transcript-api + yt-dlp) with performance timing.
    Returns: dict with transcript, metadata, and performance_timing for comparison
    """
    start_time = time.time()
    performance_timing = {
        "total_time": 0,
        "transcript_fetch_time": 0,
        "metadata_fetch_time": 0,
        "method": "fallback_old_apis"
    }
    
    try:
        # Step 1: Fetch transcript using old API
        transcript_start = time.time()
        
        # Import old APIs when needed
        from youtube_transcript_api import YouTubeTranscriptApi
        
        ytt_api = YouTubeTranscriptApi()
        transcript_data = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        
        # Extract text from snippets
        transcript = " ".join([snippet.text for snippet in transcript_data.snippets])
        
        # Basic transcript metadata
        transcript_metadata = {
            "video_id": transcript_data.video_id,
            "language": transcript_data.language,
            "language_code": transcript_data.language_code,
            "is_generated": transcript_data.is_generated,
            "transcript_length": len(transcript),
            "segments_count": len(transcript_data.snippets),
            "duration_seconds": sum(snippet.duration for snippet in transcript_data.snippets)
        }
        
        performance_timing["transcript_fetch_time"] = time.time() - transcript_start
        if agent_logger:
            agent_logger.info(f"📝 Transcript fetch: {performance_timing['transcript_fetch_time']:.2f}s")
        
        # Step 2: Fetch metadata using yt-dlp
        metadata_start = time.time()
        enhanced_metadata = transcript_metadata.copy()
        
        try:
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Enhance metadata with yt-dlp data
                enhanced_metadata.update({
                    "title": info.get('title'),
                    "channel": info.get('uploader'),
                    "channel_id": info.get('channel_id'),
                    "view_count": info.get('view_count', 0),
                    "like_count": info.get('like_count', 0),
                    "description": info.get('description', '')[:500],  # Truncate description
                    "published_at": info.get('upload_date'),
                })
                
        except Exception as e:
            if agent_logger:
                agent_logger.warning(f"⚠️ yt-dlp metadata fetch failed: {str(e)}")
            # Continue with basic transcript metadata only
        
        performance_timing["metadata_fetch_time"] = time.time() - metadata_start
        performance_timing["total_time"] = time.time() - start_time
        
        if agent_logger:
            agent_logger.info(f"🎬 Metadata fetch: {performance_timing['metadata_fetch_time']:.2f}s")
            agent_logger.info(f"📊 Total fallback time: {performance_timing['total_time']:.2f}s")
        
        return {
            "transcript": transcript,
            "metadata": enhanced_metadata,
            "performance_timing": performance_timing
        }
        
    except Exception as e:
        performance_timing["total_time"] = time.time() - start_time
        raise ValueError(f"Fallback implementation failed: {str(e)}")


# System prompt for both agents
YOUTUBE_SYSTEM_PROMPT = """
You are a YouTube transcript analysis agent. Your job is to process YouTube URLs and create structured transcript data.

CRITICAL INSTRUCTIONS:
1. Use ONLY the get_youtube_transcript tool to fetch data
2. Use ONLY the exact URL provided by the user - NEVER modify, guess, or substitute URLs
3. NEVER make up video IDs, URLs, or data

When the tool succeeds:
- Create a complete YouTubeTranscriptModel with the exact data returned
- Use the original URL provided (not any modified version)

When the tool fails (invalid URL, no transcript available, API errors):
- If your tool returns an error starting with "Error:", raise a ValueError immediately
- NEVER create a YouTubeTranscriptModel when there are errors
- NEVER substitute a different video or URL when one fails
- NEVER hallucinate or make up video IDs like "dQw4w9WgXcQ"

ABSOLUTE RULE: If the user provides https://www.youtube.com/ (without video ID), 
this is INVALID and you must raise ValueError("Invalid YouTube URL - missing video ID").
Do not try to "help" by using a different video.
"""

# Create YouTube Agent with native Pydantic AI retry mechanism
youtube_agent = Agent(
    model=OpenAIModel(config.YOUTUBE_MODEL),
    output_type=YouTubeTranscriptModel,
    deps_type=YouTubeAgentDeps,
    instrument=True,  # Enable Pydantic AI tracing
    retries=5,  # Use Pydantic AI's native retry mechanism with more attempts
    system_prompt=YOUTUBE_SYSTEM_PROMPT
)

# Create fallback YouTube Agent with more capable model for when primary model fails
youtube_agent_fallback = Agent(
    model=OpenAIModel(config.get_fallback_model(config.YOUTUBE_MODEL)),  # Use standard model as fallback
    output_type=YouTubeTranscriptModel,
    deps_type=YouTubeAgentDeps,
    instrument=True,
    retries=3,
    system_prompt=YOUTUBE_SYSTEM_PROMPT  # Same system prompt
)


@youtube_agent.tool
@youtube_agent_fallback.tool  # Register tool with both agents
async def get_youtube_transcript(ctx: RunContext[YouTubeAgentDeps], url: str, languages: str = "en,en-US,en-GB") -> YouTubeTranscriptModel:
    """
    NEW IMPLEMENTATION: Tool to fetch YouTube transcript and metadata using official YouTube Data API.
    
    Args:
        url: YouTube video URL  
        languages: Comma-separated list of preferred languages (e.g., "en,de,fr")
    
    Returns:
        YouTubeTranscriptModel with complete transcript data and metadata, plus performance timing
    """
    try:
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError(f"Invalid YouTube URL format: {url}")
        
        # Parse language preferences
        language_list = [lang.strip() for lang in languages.split(',')]
        
        # NEW: Try YouTube Data API first, fallback to old implementation if needed
        logger = get_agent_logger("YouTubeAgent")
        logger.info("🚀 Attempting YouTube Data API...")
        
        try:
            transcript, metadata, performance_timing = await fetch_youtube_hybrid_api(video_id, language_list)
            logger.info("✅ Hybrid YouTube API successful!")
        except Exception as api_error:
            logger.warning(f"⚠️ YouTube Data API failed: {str(api_error)}")
            logger.info("🔄 Falling back to old implementation (transcript API + yt-dlp)...")
            
            # Fallback to old implementation for performance comparison
            fallback_data = await fetch_youtube_fallback(video_id, logger)
            transcript = fallback_data.get("transcript", "")
            metadata = fallback_data.get("metadata", {})
            performance_timing = fallback_data.get("performance_timing", {})
        
        # Log performance metrics (handles hybrid, YouTube Data API, and fallback)
        method = performance_timing.get('method', 'youtube_data_api')
        logger.info(f"📊 Performance Results ({method}):")
        logger.info(f"   Total time: {performance_timing['total_time']:.2f}s")
        
        if 'hybrid' in method:
            # Hybrid method with parallel execution
            logger.info(f"   🚀 Metadata fetch (Data API): {performance_timing['metadata_fetch_time']:.2f}s")
            logger.info(f"   📝 Transcript fetch (youtube-transcript-api): {performance_timing['transcript_fetch_time']:.2f}s")
            logger.info(f"   🔗 Total API calls: {performance_timing['api_calls_count']}")
            logger.info(f"   ⚡ Parallel execution speedup: {max(performance_timing['metadata_fetch_time'], performance_timing['transcript_fetch_time']):.2f}s vs {performance_timing['metadata_fetch_time'] + performance_timing['transcript_fetch_time']:.2f}s sequential")
        elif method == 'youtube_data_api':
            logger.info(f"   Metadata fetch: {performance_timing['metadata_fetch_time']:.2f}s")
            logger.info(f"   Captions list: {performance_timing['captions_list_time']:.2f}s")
            logger.info(f"   Captions download: {performance_timing['captions_download_time']:.2f}s")
            logger.info(f"   Total API calls: {performance_timing['api_calls_count']}")
        else:
            logger.info(f"   Transcript fetch: {performance_timing['transcript_fetch_time']:.2f}s")
            logger.info(f"   Metadata fetch: {performance_timing['metadata_fetch_time']:.2f}s")
        
        # COMMENTED OUT: Old yt-dlp implementation - replaced with YouTube Data API
        # try:
        #     import yt_dlp
        #     
        #     ydl_opts = {
        #         'quiet': True,
        #         'no_warnings': True,
        #     }
        #     
        #     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #         info = ydl.extract_info(url, download=False)
        #         
        #         title = info.get('title')
        #         channel = info.get('uploader')
        #         duration_seconds = info.get('duration')
        #         duration = str(duration_seconds) if duration_seconds is not None else None
        #         
        # except Exception as e:
        #     # Continue without additional metadata - transcript metadata is sufficient
        #     pass
        
        # Create and return structured YouTube transcript model with enhanced metadata
        youtube_model = YouTubeTranscriptModel(
            url=url,
            transcript=transcript,
            metadata=metadata,  # Now includes comprehensive YouTube Data API metadata + performance timing
            title=metadata.get("title"),
            channel=metadata.get("channel"),
            duration=str(int(metadata.get("duration_seconds", 0))) if metadata.get("duration_seconds") else None
        )
        
        return youtube_model
               
    except Exception as e:
        raise ValueError(f"Error fetching YouTube data via API: {str(e)}")


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
            
            # NEW: Try Hybrid YouTube API first, fallback to old implementation if needed
            agent_logger.info("🚀 Attempting Hybrid YouTube API (Data API + Transcript API)...")
            try:
                transcript, metadata, performance_timing = await fetch_youtube_hybrid_api(video_id)
                agent_logger.info("✅ Hybrid YouTube API successful!")
            except Exception as api_error:
                agent_logger.warning(f"⚠️ YouTube Data API failed: {str(api_error)}")
                agent_logger.info("🔄 Falling back to old implementation (transcript API + yt-dlp)...")
                
                # Fallback to old implementation for performance comparison
                performance_timing = await fetch_youtube_fallback(video_id, agent_logger)
                transcript = performance_timing.get("transcript", "")
                metadata = performance_timing.get("metadata", {})
                performance_timing = performance_timing.get("performance_timing", {})
            
            # Log detailed performance metrics (handles both YouTube Data API and fallback)
            method = performance_timing.get('method', 'youtube_data_api')
            agent_logger.info(f"✅ YouTube fetch completed using: {method}")
            agent_logger.info(f"   📊 Total time: {performance_timing['total_time']:.2f}s")
            
            if method == 'youtube_data_api':
                agent_logger.info(f"   📺 Metadata fetch: {performance_timing['metadata_fetch_time']:.2f}s") 
                agent_logger.info(f"   🎬 Captions list: {performance_timing['captions_list_time']:.2f}s")
                agent_logger.info(f"   📝 Captions download: {performance_timing['captions_download_time']:.2f}s")
                agent_logger.info(f"   🔗 Total API calls: {performance_timing['api_calls_count']}")
            else:
                agent_logger.info(f"   📝 Transcript fetch: {performance_timing['transcript_fetch_time']:.2f}s")
                agent_logger.info(f"   🎬 Metadata fetch: {performance_timing['metadata_fetch_time']:.2f}s")
            
            agent_logger.info(f"   📄 Transcript length: {len(transcript)} chars")
            agent_logger.info(f"   🗣️ Language: {metadata.get('language')}")
            agent_logger.info(f"   🎯 Title: {metadata.get('title', 'N/A')[:50]}...")
            agent_logger.info(f"   📺 Channel: {metadata.get('channel', 'N/A')}")
            
            # COMMENTED OUT: Old implementation using separate APIs
            # agent_logger.info("Fetching YouTube transcript...")
            # transcript, metadata = await fetch_youtube_transcript(video_id)
            # 
            # agent_logger.info(f"✅ Transcript fetched - Length: {len(transcript)} chars, Language: {metadata.get('language')}")
            # 
            # # Fetch video metadata using yt-dlp (more reliable than pytube)
            # title = None
            # channel = None
            # duration = None
            # 
            # try:
            #     agent_logger.info("🎬 Fetching video metadata using yt-dlp...")
            #     import yt_dlp
            #     
            #     ydl_opts = {
            #         'quiet': True,
            #         'no_warnings': True,
            #     }
            #     
            #     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            #         info = ydl.extract_info(url, download=False)
            #         
            #         title = info.get('title')
            #         channel = info.get('uploader')
            #         duration_seconds = info.get('duration')  # Duration in seconds
            #         duration = str(duration_seconds) if duration_seconds is not None else None
            #     
            #     agent_logger.info(f"✅ Video metadata fetched - Title: {title[:50] if title else 'N/A'}..., Channel: {channel}, Duration: {duration}s")
            #     
            # except Exception as e:
            #     agent_logger.warning(f"⚠️ Failed to fetch video metadata: {str(e)}")
            #     # Continue without metadata - don't fail the entire request
            
            # Create structured YouTube transcript model with enhanced metadata from YouTube Data API
            agent_logger.info("📋 Creating structured transcript model...")
            
            youtube_model = YouTubeTranscriptModel(
                url=url,
                transcript=transcript,
                metadata=metadata,  # Now includes comprehensive YouTube Data API metadata
                title=metadata.get("title"),
                channel=metadata.get("channel"),
                duration=str(int(metadata.get("duration_seconds", 0))) if metadata.get("duration_seconds") else None
            )
            
            response_data = {
                "video_id": video_id,
                "url": url,
                "transcript": transcript,
                "metadata": metadata,  # Enhanced with YouTube Data API metadata
                "title": metadata.get("title"),
                "channel": metadata.get("channel"),
                "duration": str(int(metadata.get("duration_seconds", 0))) if metadata.get("duration_seconds") else None,
                "structured_model": youtube_model.model_dump(),
                "performance_timing": performance_timing  # Include performance metrics in response
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
