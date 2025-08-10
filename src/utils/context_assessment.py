"""
Context Assessment and Token Management Utilities

Provides intelligent context size assessment and routing decisions for the hybrid report generation system.
Supports both traditional report generation (small contexts) and iterative chunking (large contexts).
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from models import ResearchItem, YouTubeTranscriptModel, WeatherModel

# Context thresholds for routing decisions
SMALL_CONTEXT_THRESHOLD = 180000  # Tokens - safe margin under 200K context window
LARGE_CONTEXT_THRESHOLD = 200000  # Tokens - absolute limit for single pass
MAX_CHUNK_SIZE = 150000           # Tokens - target size for each iterative chunk

@dataclass
class ContextAssessment:
    """Assessment result for context size and routing strategy."""
    total_estimated_tokens: int
    recommended_strategy: str  # "traditional" or "iterative"
    requires_chunking: bool
    estimated_chunks: int
    content_breakdown: Dict[str, int]  # Token count by content type
    reasoning: str


def estimate_tokens_from_text(text: str) -> int:
    """
    Estimate token count from text using approximation method.
    
    Uses approximation: ~4 characters per token for English text.
    This is conservative and accounts for variation in tokenization.
    """
    if not text or not isinstance(text, str):
        return 0
    
    # Basic character count approach
    char_count = len(text)
    
    # Account for different text types
    if text.count('\n') > char_count * 0.1:  # Lots of line breaks (structured data)
        estimated_tokens = int(char_count / 3.5)  # More dense tokenization
    else:  # Regular prose
        estimated_tokens = int(char_count / 4.0)  # Standard approximation
    
    return max(estimated_tokens, 1)  # Minimum 1 token


def estimate_research_tokens(research_items: List[ResearchItem]) -> Tuple[int, Dict[str, int]]:
    """
    Estimate total tokens for research content with detailed breakdown.
    
    Returns:
        Tuple of (total_tokens, breakdown_dict)
    """
    breakdown = {
        "scraped_content": 0,
        "snippets": 0,  
        "titles": 0,
        "metadata": 0
    }
    
    for item in research_items:
        # Scraped content (main contributor)
        if item.scraped_content:
            breakdown["scraped_content"] += estimate_tokens_from_text(item.scraped_content)
        
        # Snippets (fallback if no scraped content)
        elif item.snippet:
            breakdown["snippets"] += estimate_tokens_from_text(item.snippet)
        
        # Titles and metadata
        if item.title:
            breakdown["titles"] += estimate_tokens_from_text(item.title)
        
        # Metadata overhead (small but adds up)
        breakdown["metadata"] += 50  # Approximate tokens for URLs, scores, etc.
    
    total_tokens = sum(breakdown.values())
    return total_tokens, breakdown


def estimate_youtube_tokens(youtube_data: YouTubeTranscriptModel) -> Tuple[int, Dict[str, int]]:
    """Estimate tokens for YouTube transcript data."""
    breakdown = {
        "transcript": 0,
        "title": 0,
        "metadata": 0
    }
    
    if youtube_data.transcript:
        breakdown["transcript"] = estimate_tokens_from_text(youtube_data.transcript)
    
    if youtube_data.title:
        breakdown["title"] = estimate_tokens_from_text(youtube_data.title)
    
    # Metadata: channel, duration, URL, etc.
    breakdown["metadata"] = 100
    
    total_tokens = sum(breakdown.values())
    return total_tokens, breakdown


def estimate_weather_tokens(weather_data: WeatherModel) -> Tuple[int, Dict[str, int]]:
    """Estimate tokens for weather data (typically very small)."""
    breakdown = {
        "current_weather": 100,  # Current conditions
        "forecast": 200,         # 5-day forecast
        "metadata": 50          # Location, timestamps, etc.
    }
    
    total_tokens = sum(breakdown.values())
    return total_tokens, breakdown


def assess_universal_context(
    research_data: Optional[List[ResearchItem]] = None,
    youtube_data: Optional[YouTubeTranscriptModel] = None, 
    weather_data: Optional[WeatherModel] = None,
    additional_context: str = ""
) -> ContextAssessment:
    """
    Comprehensive context assessment for universal report data.
    
    Analyzes all available data sources and recommends optimal processing strategy.
    """
    total_tokens = 0
    content_breakdown = {}
    
    # Assess research data (typically the largest component)
    if research_data:
        research_tokens, research_breakdown = estimate_research_tokens(research_data)
        total_tokens += research_tokens
        content_breakdown["research"] = research_tokens
        content_breakdown.update(research_breakdown)
    
    # Assess YouTube data
    if youtube_data:
        youtube_tokens, youtube_breakdown = estimate_youtube_tokens(youtube_data)
        total_tokens += youtube_tokens
        content_breakdown["youtube"] = youtube_tokens  
        content_breakdown.update({f"youtube_{k}": v for k, v in youtube_breakdown.items()})
    
    # Assess weather data (typically minimal)
    if weather_data:
        weather_tokens, weather_breakdown = estimate_weather_tokens(weather_data) 
        total_tokens += weather_tokens
        content_breakdown["weather"] = weather_tokens
        content_breakdown.update({f"weather_{k}": v for k, v in weather_breakdown.items()})
    
    # Additional context (prompts, system instructions, etc.)
    if additional_context:
        additional_tokens = estimate_tokens_from_text(additional_context)
        total_tokens += additional_tokens
        content_breakdown["additional"] = additional_tokens
    
    # Add overhead for system prompts, formatting, etc.
    system_overhead = 5000  # Conservative estimate for prompts and formatting
    total_tokens += system_overhead
    content_breakdown["system_overhead"] = system_overhead
    
    # Determine strategy and chunking requirements
    if total_tokens <= SMALL_CONTEXT_THRESHOLD:
        strategy = "traditional"
        requires_chunking = False
        estimated_chunks = 1
        reasoning = f"Context size ({total_tokens:,} tokens) is within traditional processing limits"
    else:
        strategy = "iterative"
        requires_chunking = True
        estimated_chunks = max(2, int(total_tokens / MAX_CHUNK_SIZE) + 1)
        reasoning = f"Context size ({total_tokens:,} tokens) exceeds threshold, requires {estimated_chunks} chunks"
    
    return ContextAssessment(
        total_estimated_tokens=total_tokens,
        recommended_strategy=strategy,
        requires_chunking=requires_chunking,
        estimated_chunks=estimated_chunks,
        content_breakdown=content_breakdown,
        reasoning=reasoning
    )


def chunk_research_items_intelligently(
    research_items: List[ResearchItem], 
    max_tokens_per_chunk: int = MAX_CHUNK_SIZE
) -> List[List[ResearchItem]]:
    """
    Intelligently chunk research items while preserving item integrity.
    
    Ensures no individual research item is split across chunks while maximizing
    token utilization within each chunk.
    """
    if not research_items:
        return []
    
    # Sort by authority/relevance (high-quality sources in early chunks)
    sorted_items = sorted(
        research_items, 
        key=lambda x: (
            x.relevance_score or 0,
            1 if x.is_pdf_content else 0,  # PDFs get priority
            -(len(x.scraped_content or "") + len(x.snippet or ""))  # Longer content later
        ),
        reverse=True
    )
    
    chunks = []
    current_chunk = []
    current_chunk_tokens = 0
    
    for item in sorted_items:
        # Estimate tokens for this item
        item_tokens = 0
        if item.scraped_content:
            item_tokens += estimate_tokens_from_text(item.scraped_content)
        elif item.snippet:
            item_tokens += estimate_tokens_from_text(item.snippet)
        
        if item.title:
            item_tokens += estimate_tokens_from_text(item.title)
        
        item_tokens += 50  # Metadata overhead
        
        # Check if we can add this item to current chunk
        if current_chunk_tokens + item_tokens <= max_tokens_per_chunk:
            current_chunk.append(item)
            current_chunk_tokens += item_tokens
        else:
            # Current chunk is full, start new chunk
            if current_chunk:  # Don't add empty chunks
                chunks.append(current_chunk)
            
            # Handle very large single items that exceed chunk size
            if item_tokens > max_tokens_per_chunk:
                # Large item goes in its own chunk (will be handled specially)
                chunks.append([item])
                current_chunk = []
                current_chunk_tokens = 0
            else:
                # Start new chunk with this item
                current_chunk = [item]
                current_chunk_tokens = item_tokens
    
    # Add final chunk if not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def get_context_summary(assessment: ContextAssessment) -> str:
    """Generate human-readable summary of context assessment."""
    summary_parts = [
        f"📊 Context Assessment: {assessment.total_estimated_tokens:,} tokens",
        f"🎯 Strategy: {assessment.recommended_strategy.title()}",
        f"📝 Reasoning: {assessment.reasoning}"
    ]
    
    if assessment.requires_chunking:
        summary_parts.append(f"🧩 Chunks: {assessment.estimated_chunks} chunks needed")
    
    # Add breakdown of major content sources
    major_sources = {k: v for k, v in assessment.content_breakdown.items() 
                    if v > 1000 and k in ["research", "youtube", "scraped_content"]}
    if major_sources:
        breakdown_str = ", ".join([f"{k}: {v:,}" for k, v in major_sources.items()])
        summary_parts.append(f"📈 Major sources: {breakdown_str}")
    
    return "\n".join(summary_parts)


# Configuration and thresholds
CONTEXT_CONFIG = {
    "small_threshold": SMALL_CONTEXT_THRESHOLD,
    "large_threshold": LARGE_CONTEXT_THRESHOLD, 
    "max_chunk_size": MAX_CHUNK_SIZE,
    "system_overhead": 5000,
    "token_per_char_ratio": 4.0
}