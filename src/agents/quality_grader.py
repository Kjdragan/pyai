"""
Quality Grading System for Research Results
Implements multi-tier filtering to reduce expensive scraping/cleaning operations.
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

from models import ResearchItem
from utils.time_provider import now


class QualityGrader:
    """
    Multi-tier quality grading system for research results.
    Determines which results deserve expensive scraping and content cleaning.
    """
    
    def __init__(self):
        # High-quality domains that typically have good content
        self.premium_domains = {
            'arxiv.org', 'nature.com', 'science.org', 'acm.org', 'ieee.org',
            'mit.edu', 'stanford.edu', 'harvard.edu', 'berkeley.edu',
            'techcrunch.com', 'wired.com', 'arstechnica.com', 'theverge.com',
            'bloomberg.com', 'reuters.com', 'wsj.com', 'ft.com',
            'medium.com', 'substack.com', 'github.com'
        }
        
        # Low-quality domains to avoid scraping
        self.low_quality_domains = {
            'pinterest.com', 'quora.com', 'reddit.com', 'twitter.com', 'facebook.com',
            'linkedin.com', 'instagram.com', 'tiktok.com', 'youtube.com',
            'wikipedia.org',  # Good content but usually not needed for current research
            'stackoverflow.com'  # Good for code but not general research
        }
        
        # Quality indicators in titles/URLs
        self.quality_indicators = {
            'high': ['research', 'study', 'analysis', 'report', 'whitepaper', 'survey', 
                    'technical', 'implementation', 'framework', 'architecture', 'deep-dive'],
            'low': ['listicle', 'top 10', 'best of', 'quick tips', 'hacks', 'tricks', 
                   'viral', 'trending', 'clickbait', 'you need to know']
        }
    
    def calculate_serper_quality_score(
        self, 
        item: ResearchItem, 
        query: str, 
        position: int,
        snippet_length: int
    ) -> float:
        """
        Calculate quality score for Serper results (which don't have native scoring).
        
        Args:
            item: Research item from Serper
            query: Original search query
            position: Result position (1-based)
            snippet_length: Length of the snippet
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.5  # Base score
        
        # 1. Domain reputation (±0.25)
        domain = self._extract_domain(item.source_url)
        if domain in self.premium_domains:
            score += 0.25
        elif domain in self.low_quality_domains:
            score -= 0.25
        
        # 2. Position bonus (±0.15) - earlier results are typically better
        if position <= 3:
            score += 0.15
        elif position <= 7:
            score += 0.05
        elif position > 15:
            score -= 0.10
        
        # 3. Title quality (±0.15)
        title_score = self._analyze_title_quality(item.title, query)
        score += title_score * 0.15
        
        # 4. Snippet relevance (±0.10)
        snippet_score = self._analyze_snippet_relevance(item.snippet, query)
        score += snippet_score * 0.10
        
        # 5. Content length indicator (±0.05)
        if snippet_length > 150:  # Substantial snippet suggests good content
            score += 0.05
        elif snippet_length < 50:  # Very short snippet may indicate thin content
            score -= 0.05
        
        # 6. Recency bonus (±0.05) - if we can detect publication date
        if self._is_recent_content(item.title, item.snippet):
            score += 0.05
        
        # Clamp to valid range
        return max(0.0, min(1.0, score))
    
    def should_scrape_content(
        self, 
        item: ResearchItem, 
        pipeline_type: str,
        total_results: int
    ) -> bool:
        """
        Determine if we should perform expensive scraping and cleaning.
        
        Args:
            item: Research item to evaluate
            pipeline_type: "tavily" or "serper"
            total_results: Total number of results available
            
        Returns:
            True if content should be scraped and cleaned
        """
        relevance_score = item.relevance_score or 0.0
        
        # Always scrape top-tier results regardless of source
        if relevance_score >= 0.9:
            return True
            
        # For Tavily, use native quality scores with higher threshold
        if pipeline_type == "tavily":
            from config import config
            return relevance_score >= config.TAVILY_SCRAPING_THRESHOLD
        
        # For Serper, use our calculated quality scores
        if pipeline_type == "serper":
            # Use consistent 0.5 threshold with Tavily for more inclusive results
            return relevance_score >= 0.5
        
        # Use consistent 0.5 threshold for all sources
        return relevance_score >= 0.5
    
    def grade_result_batch(
        self, 
        results: List[ResearchItem], 
        query: str,
        pipeline_type: str,
        max_scrape_count: int = 8
    ) -> List[ResearchItem]:
        """
        Grade a batch of results and determine scraping strategy.
        
        Args:
            results: List of research items to grade
            query: Original search query
            pipeline_type: "tavily" or "serper" 
            max_scrape_count: Maximum number of items to scrape per batch
            
        Returns:
            List of results with updated quality scores and scraping flags
        """
        graded_results = []
        scrape_count = 0
        
        # For Serper results, calculate quality scores first
        if pipeline_type == "serper":
            for i, item in enumerate(results):
                # Calculate Serper quality score
                quality_score = self.calculate_serper_quality_score(
                    item, query, i + 1, len(item.snippet)
                )
                
                # Update the item with calculated score
                item.relevance_score = quality_score
        
        # Sort by relevance score (descending)
        sorted_results = sorted(results, key=lambda x: x.relevance_score or 0.0, reverse=True)
        
        for item in sorted_results:
            # Determine if we should scrape this item
            should_scrape = (
                scrape_count < max_scrape_count and 
                self.should_scrape_content(item, pipeline_type, len(results))
            )
            
            if should_scrape:
                scrape_count += 1
                # Mark for scraping - this will be used by the scraping logic
                item.metadata = getattr(item, 'metadata', {})
                item.metadata['should_scrape'] = True
                item.metadata['scrape_priority'] = scrape_count
            else:
                # Mark as snippet-only
                item.metadata = getattr(item, 'metadata', {})
                item.metadata['should_scrape'] = False
                item.metadata['skip_reason'] = f"Quality score {item.relevance_score:.2f} below threshold"
            
            graded_results.append(item)
        
        return graded_results
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    def _analyze_title_quality(self, title: str, query: str) -> float:
        """Analyze title quality and relevance. Returns -1.0 to 1.0."""
        if not title:
            return -0.5
            
        title_lower = title.lower()
        query_lower = query.lower()
        
        score = 0.0
        
        # Check for quality indicators
        for indicator in self.quality_indicators['high']:
            if indicator in title_lower:
                score += 0.2
                
        for indicator in self.quality_indicators['low']:
            if indicator in title_lower:
                score -= 0.3
        
        # Query term relevance
        query_words = set(query_lower.split())
        title_words = set(title_lower.split())
        
        if query_words:
            overlap = len(query_words.intersection(title_words)) / len(query_words)
            score += overlap * 0.5
        
        return max(-1.0, min(1.0, score))
    
    def _analyze_snippet_relevance(self, snippet: str, query: str) -> float:
        """Analyze snippet relevance to query. Returns -1.0 to 1.0."""
        if not snippet:
            return -0.5
            
        snippet_lower = snippet.lower()
        query_lower = query.lower()
        
        # Simple relevance based on query term overlap
        query_words = set(query_lower.split())
        snippet_words = set(snippet_lower.split())
        
        if not query_words:
            return 0.0
            
        overlap = len(query_words.intersection(snippet_words)) / len(query_words)
        
        # Bonus for exact query phrases
        if query_lower in snippet_lower:
            overlap += 0.3
        
        return min(1.0, overlap)
    
    def _is_recent_content(self, title: str, snippet: str) -> bool:
        """Detect if content appears to be recent (current and previous year)."""
        current_year = now().year
        text = f"{title} {snippet}".lower()
        
        # Look for current/recent year mentions
        recent_indicators = [
            str(current_year),
            str(current_year - 1),
            'latest', 'recent', 'new', 'current', 'updated'
        ]
        
        return any(indicator in text for indicator in recent_indicators)
    
    def get_quality_summary(self, results: List[ResearchItem]) -> Dict[str, Any]:
        """Generate summary statistics for quality grading."""
        if not results:
            return {}
        
        scores = [r.relevance_score for r in results if r.relevance_score is not None]
        scrape_count = sum(1 for r in results if getattr(r, 'metadata', {}).get('should_scrape', False))
        
        return {
            'total_results': len(results),
            'avg_quality_score': sum(scores) / len(scores) if scores else 0.0,
            'max_quality_score': max(scores) if scores else 0.0,
            'min_quality_score': min(scores) if scores else 0.0,
            'scheduled_for_scraping': scrape_count,
            'scraping_percentage': (scrape_count / len(results)) * 100 if results else 0.0
        }


# Global quality grader instance
quality_grader = QualityGrader()