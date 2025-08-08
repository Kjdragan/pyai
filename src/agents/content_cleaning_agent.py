"""
Content Cleaning Agent for removing boilerplate text from scraped research content.
Uses fast nano model to efficiently clean navigation menus, ads, and irrelevant content.
"""

import asyncio
from typing import Optional
from datetime import datetime
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from config import config
from logging_config import get_agent_logger

def get_logger():
    """Lazy-load logger to avoid initialization issues during import."""
    return get_agent_logger("ContentCleaningAgent")

# Create Content Cleaning Agent with nano model for speed and cost efficiency
content_cleaning_agent = Agent(
    model=OpenAIModel(config.NANO_MODEL),  # Fast, cheap model perfect for this task
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt="""
    You are a content cleaning specialist. Your job is to extract only the main, relevant content from web-scraped text, removing all boilerplate, navigation, advertising, and irrelevant elements.

    REMOVE these types of content:
    - Navigation menus ("Menu", "Home", "About Us", etc.)
    - Headers and footers with site branding
    - Social media links and sharing buttons
    - Subscribe/newsletter prompts
    - Cookie notices and privacy banners  
    - Advertisement text and promotional content
    - "Skip to main content" and accessibility links
    - Breadcrumb navigation
    - Related articles sections that aren't about the main topic
    - Copyright notices and legal text
    - Comment sections and user-generated content
    - Site search forms and filters

    KEEP these types of content:
    - Main article or page content directly related to the topic
    - Headlines and subheadings about the subject
    - Key facts, statistics, and data points
    - Quotes from experts or officials
    - Technical details and explanations
    - Dates and specific information
    - Author bylines if relevant to credibility

    OUTPUT REQUIREMENTS:
    - Return only the cleaned, relevant content
    - Maintain the original structure and flow where possible  
    - Preserve important formatting like bullet points or numbered lists
    - Keep paragraph breaks for readability
    - Do NOT add your own commentary or explanations
    - Do NOT summarize - just remove the noise and keep the signal
    """,
    retries=2  # Quick retry on failure
)


async def clean_scraped_content(
    content: str, 
    topic: str, 
    source_url: str,
    max_chars: Optional[int] = None
) -> tuple[str, bool]:
    """
    Clean scraped content by removing boilerplate text and irrelevant elements.
    
    Args:
        content: Raw scraped content to clean
        topic: The research topic for context
        source_url: Source URL for debugging
        max_chars: Optional character limit (None = no limit due to cheap nano model)
    
    Returns:
        tuple[cleaned_content, success_flag]
    """
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Skip cleaning for very short content (likely already clean)
        if len(content) < 500:
            get_logger().debug(f"Skipping cleaning for short content from {source_url}: {len(content)} chars")
            return content, True
            
        get_logger().debug(f"🧹 Starting content cleaning for {source_url}: {len(content)} chars")
        
        # Prepare context-aware prompt
        prompt = f"""
        Clean this web-scraped content about "{topic}". Remove all navigation, ads, boilerplate, and irrelevant text.
        
        Keep only the main content that is directly related to: {topic}
        
        Source: {source_url}
        
        Raw content to clean:
        
        {content}
        """
        
        # Clean the content using the nano model
        result = await content_cleaning_agent.run(prompt)
        cleaned_content = result.data
        
        processing_time = asyncio.get_event_loop().time() - start_time
        original_length = len(content)
        cleaned_length = len(cleaned_content)
        reduction_pct = ((original_length - cleaned_length) / original_length) * 100 if original_length > 0 else 0
        
        get_logger().info(f"✅ Content cleaned from {source_url}: {original_length} → {cleaned_length} chars "
                   f"({reduction_pct:.1f}% reduction) in {processing_time:.2f}s")
        
        return cleaned_content, True
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        get_logger().error(f"❌ Content cleaning failed for {source_url}: {str(e)} (took {processing_time:.2f}s)")
        
        # Return original content on failure - don't break the pipeline
        return content, False


async def clean_multiple_contents_batched(
    content_items: list[tuple[str, str, str]], 
    batch_size: int = 4
) -> list[tuple[str, bool]]:
    """
    Clean multiple scraped contents using batch API calls for 4x speedup.
    
    Args:
        content_items: List of (content, topic, source_url) tuples
        batch_size: Number of items to process per API call
    
    Returns:
        List of (cleaned_content, success_flag) tuples in same order
    """
    if not content_items:
        return []
    
    get_logger().info(f"🧹 Starting batched cleaning of {len(content_items)} items (batch_size={batch_size})")
    start_time = asyncio.get_event_loop().time()
    
    # Process items in batches
    all_results = []
    for i in range(0, len(content_items), batch_size):
        batch = content_items[i:i+batch_size]
        batch_results = await _process_content_batch(batch)
        all_results.extend(batch_results)
    
    total_time = asyncio.get_event_loop().time() - start_time
    success_count = sum(1 for _, success in all_results if success)
    
    get_logger().info(f"✅ Batched cleaning completed: {success_count}/{len(content_items)} successful in {total_time:.2f}s")
    return all_results


async def _process_content_batch(batch: list[tuple[str, str, str]]) -> list[tuple[str, bool]]:
    """Process a batch of content items in a single API call."""
    if len(batch) == 1:
        # Single item - use regular cleaning
        content, topic, source_url = batch[0]
        return [await clean_scraped_content(content, topic, source_url)]
    
    # Multi-item batch processing
    batch_prompt = _create_batch_prompt(batch)
    
    try:
        result = await content_cleaning_agent.run(batch_prompt)
        cleaned_contents = _parse_batch_response(result.data, len(batch))
        
        # Validate and return results
        results = []
        for i, (original_content, topic, source_url) in enumerate(batch):
            if i < len(cleaned_contents) and cleaned_contents[i].strip():
                cleaned = cleaned_contents[i].strip()
                results.append((cleaned, True))
                
                # Log metrics
                reduction = ((len(original_content) - len(cleaned)) / len(original_content)) * 100
                get_logger().info(f"✅ Batch cleaned {source_url}: {len(original_content)} → {len(cleaned)} chars ({reduction:.1f}% reduction)")
            else:
                # Fallback to original content
                results.append((original_content, False))
                get_logger().error(f"❌ Batch cleaning failed for {source_url}, using original")
        
        return results
        
    except Exception as e:
        get_logger().error(f"❌ Batch processing failed: {e}, falling back to individual processing")
        
        # Fallback to individual processing
        individual_results = []
        for content, topic, source_url in batch:
            individual_results.append(await clean_scraped_content(content, topic, source_url))
        return individual_results


def _create_batch_prompt(batch: list[tuple[str, str, str]]) -> str:
    """Create batch prompt for multiple content items."""
    prompt_parts = [
        "Clean the following web-scraped content items. For each item, remove boilerplate, navigation, ads, and irrelevant text.",
        "Return the cleaned content for each item separated by '---ITEM-SEPARATOR---'.",
        f"Process {len(batch)} items in order:\n"
    ]
    
    for i, (content, topic, source_url) in enumerate(batch, 1):
        prompt_parts.append(f"ITEM {i} - Topic: {topic}")
        prompt_parts.append(f"Source: {source_url}")
        prompt_parts.append(f"Content:\n{content[:5000]}...")  # Limit content per item
        prompt_parts.append("")
    
    prompt_parts.append("Return only the cleaned content for each item, separated by '---ITEM-SEPARATOR---'.")
    return "\n".join(prompt_parts)


def _parse_batch_response(response: str, expected_count: int) -> list[str]:
    """Parse batch response into individual cleaned contents."""
    if "---ITEM-SEPARATOR---" not in response:
        # Single response - split by rough estimation
        parts = response.split("\n\n")
        return parts[:expected_count] if len(parts) >= expected_count else [response]
    
    # Split by separator
    parts = response.split("---ITEM-SEPARATOR---")
    return [part.strip() for part in parts[:expected_count]]


async def clean_multiple_contents(
    content_items: list[tuple[str, str, str]]
) -> list[tuple[str, bool]]:
    """
    Clean multiple scraped contents - now uses batched processing by default.
    
    Args:
        content_items: List of (content, topic, source_url) tuples
    
    Returns:
        List of (cleaned_content, success_flag) tuples in same order
    """
    # Use batched processing for better performance
    return await clean_multiple_contents_batched(content_items, batch_size=4)


# Utility function for integration
async def clean_research_item_content(research_item, topic: str) -> None:
    """
    Clean the scraped content of a single research item in-place.
    
    Args:
        research_item: ResearchItem with scraped_content to clean
        topic: Research topic for context
    """
    if not research_item.scraped_content or not research_item.content_scraped:
        get_logger().debug(f"⏭️ Skipping cleaning for item without scraped content: {research_item.source_url}")
        return  # Nothing to clean
    
    start_time = asyncio.get_event_loop().time()
    source_url = research_item.source_url or "unknown"
    original_length = len(research_item.scraped_content)
    
    get_logger().debug(f"🧹 Starting content cleaning for {source_url}: {original_length} chars")
        
    original_content = research_item.scraped_content

    # Preserve raw content if not already set
    try:
        if getattr(research_item, "raw_content", None) in (None, ""):
            research_item.raw_content = original_content
            research_item.raw_content_length = original_length
    except Exception:
        # Best-effort; don't fail cleaning on attribute issues
        pass

    # Quote metrics before cleaning
    def _count_quote_chars(text: str) -> int:
        if not text:
            return 0
        quote_chars = ['"', "'", '“', '”', '‘', '’']
        return sum(text.count(ch) for ch in quote_chars)

    quote_chars_before = _count_quote_chars(original_content)
    cleaned_content, success = await clean_scraped_content(
        original_content, 
        topic, 
        source_url
    )
    
    # Calculate metrics
    processing_time = asyncio.get_event_loop().time() - start_time
    cleaned_length = len(cleaned_content)
    reduction_pct = ((original_length - cleaned_length) / original_length) * 100 if original_length > 0 else 0
    
    # Update the research item with cleaned content and metadata
    research_item.scraped_content = cleaned_content
    research_item.content_cleaned = success
    research_item.original_content_length = original_length
    research_item.cleaned_content_length = cleaned_length

    # Quote metrics after cleaning
    quote_chars_after = _count_quote_chars(cleaned_content)
    try:
        if not getattr(research_item, "metadata", None):
            research_item.metadata = {}
        research_item.metadata.setdefault("quote_metrics", {})
        research_item.metadata["quote_metrics"].update({
            "quote_chars_before": quote_chars_before,
            "quote_chars_after": quote_chars_after,
            "quote_chars_delta": quote_chars_after - quote_chars_before,
        })
    except Exception:
        # Non-fatal if metadata isn't available
        pass
    
    # Log performance metrics
    status = "✅ SUCCESS" if success else "❌ FAILED"
    get_logger().info(
        f"{status} Content cleaning for {source_url}: {original_length} → {cleaned_length} chars "
        f"({reduction_pct:.1f}% reduction) in {processing_time:.2f}s | "
        f"quotes: {quote_chars_before} → {quote_chars_after}"
    )