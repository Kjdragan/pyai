"""
Content Cleaning Agent for removing boilerplate text from scraped research content.
Uses fast nano model to efficiently clean navigation menus, ads, and irrelevant content.
"""

import asyncio
from typing import Optional
from urllib.parse import urlparse
from datetime import datetime
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from config import config
from logging_config import get_agent_logger
from telemetry.run_summary import run_summary  # dev-only tracing summary

def get_logger():
    """Lazy-load logger to avoid initialization issues during import."""
    return get_agent_logger("ContentCleaningAgent")

# Create Content Cleaning Agent with nano model for speed and cost efficiency
content_cleaning_agent = Agent(
    model=OpenAIModel(config.NANO_MODEL),  # Fast, cheap model perfect for this task
    output_type=str,  # CRITICAL FIX: Return cleaned content as string
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

def _is_pdf_url(url: str) -> bool:
    """Best-effort check if URL path ends with .pdf (ignores query params)."""
    try:
        path = urlparse(url or "").path.lower()
        return path.endswith(".pdf")
    except Exception:
        return False


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
        # Use a PDF-aware cleaning hint: keep main body text, only remove obvious site chrome
        is_pdf = _is_pdf_url(source_url)
        if is_pdf and config.CLEANING_SKIP_PDFS:
            get_logger().info(f"📄 PDF detected for cleaning (non-batched): {source_url}")

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
        
        {'IMPORTANT: This appears to be a PDF report. Do NOT remove report body text; only remove obvious site chrome (headers/footers, menus). If unsure, keep the text.' if is_pdf else ''}
        
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
        try:
            run_summary.observe_cleaning(chars_in=original_length, chars_out=cleaned_length, success=True)
        except Exception:
            pass
        
        return cleaned_content, True
        
    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        get_logger().error(f"❌ Content cleaning failed for {source_url}: {str(e)} (took {processing_time:.2f}s)")
        try:
            run_summary.observe_cleaning(chars_in=len(content), chars_out=len(content), success=False)
        except Exception:
            pass
        
        # Return original content on failure - don't break the pipeline
        return content, False


async def clean_multiple_contents_batched(
    content_items: list[tuple[str, str, str]], 
    batch_size: int = 4
) -> list[tuple[str, bool]]:
    """
    Clean multiple scraped contents using batch API calls for 4x speedup.
    Automatically handles large content (>250K chars) with parallel chunking.
    
    Args:
        content_items: List of (content, topic, source_url) tuples
        batch_size: Number of items to process per API call (ignored for chunked content)
    
    Returns:
        List of (cleaned_content, success_flag) tuples in same order
    """
    if not content_items:
        return []
    
    get_logger().info(f"🧹 Starting batched cleaning of {len(content_items)} items (batch_size={batch_size})")
    start_time = asyncio.get_event_loop().time()
    
    # Separate small and large content items
    small_items = []
    large_items = []
    item_indices = {}  # Track original positions
    
    CHUNK_THRESHOLD = 250000
    
    for idx, (content, topic, source_url) in enumerate(content_items):
        if len(content) > CHUNK_THRESHOLD:
            large_items.append((content, topic, source_url))
            item_indices[len(large_items) - 1 + 1000] = idx  # Offset large items by 1000
            get_logger().info(f"📄 Large content detected: {source_url} ({len(content):,} chars) - will process with chunking")
        else:
            small_items.append((content, topic, source_url))
            item_indices[len(small_items) - 1] = idx
    
    # Process items based on parallelization strategy
    all_tasks = []
    
    if config.MAX_PARALLEL_CLEANING:
        # MAXIMUM PARALLELIZATION: Send every item as individual LLM call
        get_logger().info(f"🚀 MAXIMUM PARALLELIZATION ENABLED: Processing {len(small_items)} small items individually")
        
        # Process each small item individually (no batching)
        for idx, (content, topic, source_url) in enumerate(small_items):
            task = clean_scraped_content(content, topic, source_url)  # Direct individual cleaning
            all_tasks.append(('individual_small', idx, task))
            
        # Large items still use chunking (already optimally parallel)
        for idx, (content, topic, source_url) in enumerate(large_items):
            task = _process_chunked_content(content, topic, source_url)
            all_tasks.append(('large_item', idx, task))
    else:
        # BATCH PROCESSING: Use batches for small items (original behavior)
        for i in range(0, len(small_items), batch_size):
            batch = small_items[i:i+batch_size]
            task = _process_content_batch(batch)
            all_tasks.append(('small_batch', i // batch_size, task))
        
        # Add large item chunking tasks (each item gets its own parallel processing)
        for idx, (content, topic, source_url) in enumerate(large_items):
            task = _process_chunked_content(content, topic, source_url)
            all_tasks.append(('large_item', idx, task))
    
    if config.MAX_PARALLEL_CLEANING:
        individual_count = len([t for t in all_tasks if t[0] == 'individual_small'])
        chunked_count = len([t for t in all_tasks if t[0] == 'large_item'])
        get_logger().info(f"🚀 MAXIMUM PARALLELIZATION: Launching {len(all_tasks)} individual LLM calls ({individual_count} individual + {chunked_count} chunked)")
    else:
        batch_count = len([t for t in all_tasks if t[0] == 'small_batch'])
        chunked_count = len([t for t in all_tasks if t[0] == 'large_item'])
        get_logger().info(f"🚀 Launching {len(all_tasks)} parallel processing tasks ({batch_count} batches + {chunked_count} chunked items)")
    
    # Execute ALL tasks in parallel - no sequential waiting!
    task_results = await asyncio.gather(*[task for _, _, task in all_tasks], return_exceptions=True)
    
    # Reconstruct results in original order
    final_results = [None] * len(content_items)
    
    # Process small item results (batch or individual)
    for task_type, task_idx, _ in all_tasks:
        if task_type == 'small_batch':
            # Handle batched results (original behavior)
            batch_results = task_results[all_tasks.index((task_type, task_idx, _))]
            if isinstance(batch_results, Exception):
                get_logger().error(f"❌ Small batch {task_idx} failed: {batch_results}")
                # Fill with failure results
                batch_start = task_idx * batch_size
                batch_end = min(batch_start + batch_size, len(small_items))
                for i in range(batch_start, batch_end):
                    original_idx = item_indices[i]
                    final_results[original_idx] = (content_items[original_idx][0], False)
            else:
                # Distribute batch results
                batch_start = task_idx * batch_size
                for i, result in enumerate(batch_results):
                    if batch_start + i < len(small_items):
                        original_idx = item_indices[batch_start + i]
                        final_results[original_idx] = result
                        
        elif task_type == 'individual_small':
            # Handle individual results (maximum parallelization)
            result = task_results[all_tasks.index((task_type, task_idx, _))]
            original_idx = item_indices[task_idx]
            if isinstance(result, Exception):
                get_logger().error(f"❌ Individual small item {task_idx} failed: {result}")
                final_results[original_idx] = (content_items[original_idx][0], False)
            else:
                final_results[original_idx] = result
    
    # Process large item results
    for task_type, task_idx, _ in all_tasks:
        if task_type == 'large_item':
            result = task_results[all_tasks.index((task_type, task_idx, _))]
            original_idx = item_indices[task_idx + 1000]  # Remove offset
            if isinstance(result, Exception):
                get_logger().error(f"❌ Large item {task_idx} failed: {result}")
                final_results[original_idx] = (content_items[original_idx][0], False)
            else:
                final_results[original_idx] = result
    
    total_time = asyncio.get_event_loop().time() - start_time
    success_count = sum(1 for result in final_results if result and result[1])
    
    get_logger().info(f"✅ PARALLEL cleaning completed: {success_count}/{len(content_items)} successful in {total_time:.2f}s")
    
    if config.MAX_PARALLEL_CLEANING:
        get_logger().info(f"📊 MAXIMUM PARALLELIZATION: {len(small_items)} individual LLM calls + {len(large_items)} large items with chunking")
        get_logger().info(f"🚀 LLM THROUGHPUT: {len(content_items)} simultaneous API calls (no batching limits)")
    else:
        get_logger().info(f"📊 BATCH PROCESSING: {len(small_items)} regular items in batches + {len(large_items)} large items with chunking")
    
    return final_results


def _chunk_large_content(content: str, max_chunk_size: int = 250000) -> list[str]:
    """
    Split large content into chunks of approximately max_chunk_size characters.
    Tries to break at sentence boundaries when possible to preserve context.
    """
    if len(content) <= max_chunk_size:
        return [content]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(content):
        # Calculate chunk end position
        chunk_end = current_pos + max_chunk_size
        
        if chunk_end >= len(content):
            # Last chunk - take everything remaining
            chunks.append(content[current_pos:])
            break
        
        # Try to find a good breaking point (sentence end) within the last 10% of the chunk
        search_start = max(current_pos + int(max_chunk_size * 0.9), current_pos + 1000)
        search_text = content[search_start:chunk_end]
        
        # Look for sentence endings (periods, exclamation, question marks)
        sentence_breaks = []
        for i, char in enumerate(search_text):
            if char in '.!?' and i < len(search_text) - 1:
                # Check if next char is whitespace or end of content
                next_char = search_text[i + 1] if i + 1 < len(search_text) else ' '
                if next_char in ' \n\t':
                    sentence_breaks.append(search_start + i + 1)
        
        if sentence_breaks:
            # Use the last sentence break found
            actual_end = sentence_breaks[-1]
        else:
            # No good break point found, just cut at max_chunk_size
            actual_end = chunk_end
        
        chunks.append(content[current_pos:actual_end])
        current_pos = actual_end
    
    return chunks


async def _process_chunked_content(content: str, topic: str, source_url: str) -> tuple[str, bool]:
    """
    Process large content by chunking it and processing chunks in parallel.
    
    Args:
        content: Large content to process
        topic: Topic for context
        source_url: Source URL for logging
        
    Returns:
        Tuple of (cleaned_content, success_flag)
    """
    CHUNK_SIZE = 250000  # 250K characters per chunk
    
    if len(content) <= CHUNK_SIZE:
        # Content is small enough, process normally
        return await clean_scraped_content(content, topic, source_url)
    
    get_logger().info(f"📄 Large content detected ({len(content):,} chars) from {source_url} - chunking into {CHUNK_SIZE:,} char pieces")
    
    # Split into chunks
    chunks = _chunk_large_content(content, CHUNK_SIZE)
    get_logger().info(f"✂️ Content split into {len(chunks)} chunks - processing ALL IN PARALLEL")
    
    # Process ALL chunks in parallel (no batching, no sequential waiting)
    chunk_tasks = []
    for i, chunk in enumerate(chunks):
        get_logger().debug(f"🚀 Launching parallel processing for chunk {i+1}/{len(chunks)} ({len(chunk):,} chars)")
        task = clean_scraped_content(chunk, f"{topic} (Part {i+1}/{len(chunks)})", f"{source_url}#chunk{i+1}")
        chunk_tasks.append(task)
    
    # Wait for ALL chunks to complete in parallel
    chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
    
    # Reassemble results
    cleaned_chunks = []
    success_count = 0
    
    for i, result in enumerate(chunk_results):
        if isinstance(result, Exception):
            get_logger().error(f"❌ Chunk {i+1} failed with exception: {result}")
            # Use original chunk on failure
            cleaned_chunks.append(chunks[i])
        else:
            cleaned_content, success = result
            if success:
                cleaned_chunks.append(cleaned_content)
                success_count += 1
            else:
                get_logger().warning(f"⚠️ Chunk {i+1} cleaning failed, using original")
                cleaned_chunks.append(chunks[i])
    
    # Combine all chunks
    final_content = " ".join(cleaned_chunks)
    overall_success = success_count >= len(chunks) * 0.5  # Success if at least 50% of chunks succeeded
    
    get_logger().info(f"✅ Chunked processing complete: {success_count}/{len(chunks)} chunks succeeded ({len(content):,} → {len(final_content):,} chars)")
    
    return final_content, overall_success


async def _process_content_batch(batch: list[tuple[str, str, str]]) -> list[tuple[str, bool]]:
    """Process a batch of content items in a single API call."""
    if len(batch) == 1:
        # Single item - use regular cleaning
        content, topic, source_url = batch[0]
        get_logger().info(f"🔄 Processing single item batch: {source_url}")
        return [await clean_scraped_content(content, topic, source_url)]
    
    get_logger().info(f"🚀 Processing batch of {len(batch)} items using batched API call")
    
    # Process all items in batch (PDFs now handled by scraper, so no special logic needed)
    try:
        batch_prompt = _create_batch_prompt(batch)
        get_logger().debug(f"📝 Batch prompt created, length: {len(batch_prompt)} chars")
        
        result = await content_cleaning_agent.run(batch_prompt)
        get_logger().debug(f"✅ LLM response received, length: {len(result.data)} chars")
        
        cleaned_contents = _parse_batch_response(result.data, len(batch))
        get_logger().info(f"🎯 Batch parsing successful: {len(cleaned_contents)} items parsed from response")
        
        # Apply results back in correct order
        results = []
        for idx, (original_content, topic, source_url) in enumerate(batch):
            if idx < len(cleaned_contents) and cleaned_contents[idx].strip():
                cleaned = cleaned_contents[idx].strip()
                results.append((cleaned, True))
                
                # Log metrics (less verbose)
                reduction = ((len(original_content) - len(cleaned)) / len(original_content)) * 100
                get_logger().debug(f"✅ Batch cleaned {source_url}: {len(original_content)} → {len(cleaned)} chars ({reduction:.1f}% reduction)")
                try:
                    run_summary.observe_cleaning(chars_in=len(original_content), chars_out=len(cleaned), success=True)
                except Exception:
                    pass
            else:
                # Fallback to original content
                results.append((original_content, False))
                get_logger().warning(f"⚠️ Batch cleaning failed for {source_url}, using original content")
                try:
                    run_summary.observe_cleaning(chars_in=len(original_content), chars_out=len(original_content), success=False)
                except Exception:
                    pass
        
        get_logger().info(f"✅ Batch processing complete: {len([r for r in results if r[1]])} successes, {len([r for r in results if not r[1]])} failures")
        return results
        
    except Exception as e:
        get_logger().error(f"💥 CRITICAL: Batch processing completely failed: {e}")
        get_logger().error(f"💥 Falling back to individual processing for {len(batch)} items - THIS CAUSES SEQUENTIAL API CALLS!")
        
        # Emergency fallback to individual processing
        results = []
        for content, topic, source_url in batch:
            get_logger().warning(f"🔄 Individual fallback processing: {source_url}")
            individual_result = await clean_scraped_content(content, topic, source_url)
            results.append(individual_result)
        return results


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
        # Limit content per item to keep prompt sizes bounded; PDFs are handled outside batch path
        prompt_parts.append(f"Content:\n{content[:5000]}...")
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