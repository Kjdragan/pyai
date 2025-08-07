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


async def clean_multiple_contents(
    content_items: list[tuple[str, str, str]]
) -> list[tuple[str, bool]]:
    """
    Clean multiple scraped contents in parallel for efficiency.
    
    Args:
        content_items: List of (content, topic, source_url) tuples
    
    Returns:
        List of (cleaned_content, success_flag) tuples in same order
    """
    get_logger().info(f"🧹 Starting parallel cleaning of {len(content_items)} content items")
    start_time = asyncio.get_event_loop().time()
    
    # Process all content cleaning operations in parallel
    cleaning_tasks = [
        clean_scraped_content(content, topic, source_url)
        for content, topic, source_url in content_items
    ]
    
    results = await asyncio.gather(*cleaning_tasks, return_exceptions=True)
    
    # Handle any exceptions that occurred during parallel processing
    cleaned_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            get_logger().error(f"Exception in parallel cleaning #{i}: {str(result)}")
            # Return original content for failed items
            original_content = content_items[i][0]
            cleaned_results.append((original_content, False))
        else:
            cleaned_results.append(result)
    
    total_time = asyncio.get_event_loop().time() - start_time
    success_count = sum(1 for _, success in cleaned_results if success)
    
    get_logger().info(f"✅ Parallel content cleaning completed: {success_count}/{len(content_items)} successful "
               f"in {total_time:.2f}s")
    
    return cleaned_results


# Utility function for integration
async def clean_research_item_content(research_item, topic: str) -> None:
    """
    Clean the scraped content of a single research item in-place.
    
    Args:
        research_item: ResearchItem with scraped_content to clean
        topic: Research topic for context
    """
    if not research_item.scraped_content or not research_item.content_scraped:
        return  # Nothing to clean
        
    original_content = research_item.scraped_content
    cleaned_content, success = await clean_scraped_content(
        original_content, 
        topic, 
        research_item.source_url or "unknown"
    )
    
    # Update the research item with cleaned content
    research_item.scraped_content = cleaned_content
    
    # Add metadata about the cleaning process
    if hasattr(research_item, 'content_cleaned'):
        research_item.content_cleaned = success
    if hasattr(research_item, 'original_content_length'):
        research_item.original_content_length = len(original_content)
    if hasattr(research_item, 'cleaned_content_length'):
        research_item.cleaned_content_length = len(cleaned_content)