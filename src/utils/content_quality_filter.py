"""
Advanced Content Quality Filtering System
Programmatically filters garbage content before expensive LLM processing.
"""

import re
import statistics
from typing import List, Tuple, Dict, Any
from collections import Counter
from urllib.parse import urlparse

try:
    import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False

try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True  
except ImportError:
    NEWSPAPER_AVAILABLE = False

class ContentQualityFilter:
    """
    Multi-stage content quality filter to remove garbage before LLM processing.
    Uses heuristic analysis to detect keyword spam, navigation dumps, and low-value content.
    """
    
    def __init__(self):
        # Patterns that indicate low-quality content
        self.spam_patterns = [
            r'\b\w+\s*,\s*\w+\s*,\s*\w+\s*,\s*\w+\s*,',  # Excessive comma-separated keywords
            r'(\b\w{2,6}\b\s*){20,}',  # Too many short words in sequence
            r'(Click|Menu|Home|About|Contact|Login|Subscribe|Privacy|Terms)\s+',  # Navigation text
            r'\b(\w+)\s+\1\s+\1\b',  # Word repeated 3+ times
        ]
        
        # Domains known for low-quality content aggregation
        self.low_quality_domains = {
            'pinterest.com', 'quora.com', 'reddit.com', 'stackoverflow.com',
            'twitter.com', 'facebook.com', 'linkedin.com', 'instagram.com',
            'tiktok.com', 'youtube.com', 'wikipedia.org'
        }
        
        # Keywords that often indicate spam/aggregator content
        self.spam_keywords = {
            'seo', 'keywords', 'meta', 'tags', 'categories', 'advertisement',
            'sponsored', 'affiliate', 'marketing', 'optimization', 'ranking'
        }
    
    def analyze_content_quality(self, content: str, url: str = "", title: str = "") -> Dict[str, Any]:
        """
        Comprehensive content quality analysis using multiple heuristics.
        
        Returns:
            Dict with quality scores and flags for different aspects
        """
        analysis = {
            'content_length': len(content),
            'word_count': len(content.split()),
            'unique_word_ratio': self._calculate_unique_word_ratio(content),
            'sentence_count': len(re.findall(r'[.!?]+', content)),
            'avg_sentence_length': 0,
            'repetition_score': self._calculate_repetition_score(content),
            'navigation_ratio': self._calculate_navigation_ratio(content),
            'spam_pattern_score': self._detect_spam_patterns(content),
            'domain_quality': self._analyze_domain_quality(url),
            'readability_score': self._calculate_readability(content),
            'content_structure_score': self._analyze_content_structure(content),
            'keyword_density_score': self._calculate_keyword_density(content),
            'overall_quality_score': 0.0,
            'is_garbage': False,
            'garbage_reasons': []
        }
        
        # Calculate average sentence length
        if analysis['sentence_count'] > 0:
            analysis['avg_sentence_length'] = analysis['word_count'] / analysis['sentence_count']
        
        # Calculate overall quality score (0-1, higher is better)
        analysis['overall_quality_score'] = self._calculate_overall_score(analysis)
        
        # Determine if content is garbage
        analysis['is_garbage'], analysis['garbage_reasons'] = self._is_garbage_content(analysis)
        
        return analysis
    
    def should_filter_content(self, content: str, url: str = "", title: str = "", 
                            quality_threshold: float = 0.4) -> Tuple[bool, str]:
        """
        Determine if content should be filtered out before LLM processing.
        
        Args:
            content: Raw scraped content
            url: Source URL
            title: Content title
            quality_threshold: Minimum quality score (0-1)
            
        Returns:
            Tuple of (should_filter, reason)
        """
        # Quick length check
        if len(content) < 200:
            return True, "Content too short (< 200 chars)"
        
        if len(content) > 50000:
            return True, "Content too long (> 50k chars) - likely aggregator dump"
        
        # Comprehensive analysis
        analysis = self.analyze_content_quality(content, url, title)
        
        if analysis['is_garbage']:
            reasons = "; ".join(analysis['garbage_reasons'])
            return True, f"Garbage content detected: {reasons}"
        
        if analysis['overall_quality_score'] < quality_threshold:
            return True, f"Quality score too low: {analysis['overall_quality_score']:.2f} < {quality_threshold}"
        
        return False, ""
    
    def _calculate_unique_word_ratio(self, content: str) -> float:
        """Calculate ratio of unique words to total words."""
        words = content.lower().split()
        if not words:
            return 0.0
        unique_words = set(words)
        return len(unique_words) / len(words)
    
    def _calculate_repetition_score(self, content: str) -> float:
        """Calculate content repetition score (0-1, higher = more repetitive)."""
        words = content.lower().split()
        if len(words) < 10:
            return 0.0
        
        word_counts = Counter(words)
        total_repetitions = sum(count - 1 for count in word_counts.values() if count > 1)
        return min(1.0, total_repetitions / len(words))
    
    def _calculate_navigation_ratio(self, content: str) -> float:
        """Calculate ratio of navigation/menu text to total content."""
        nav_keywords = [
            'menu', 'home', 'about', 'contact', 'login', 'register', 'subscribe',
            'privacy', 'terms', 'cookies', 'skip to', 'navigation', 'breadcrumb',
            'footer', 'header', 'sidebar', 'search', 'categories', 'tags'
        ]
        
        content_lower = content.lower()
        nav_matches = sum(content_lower.count(keyword) for keyword in nav_keywords)
        
        # Rough estimate of navigation content
        return min(1.0, nav_matches * 10 / len(content.split()))
    
    def _detect_spam_patterns(self, content: str) -> float:
        """Detect common spam patterns in content."""
        spam_score = 0.0
        
        for pattern in self.spam_patterns:
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            spam_score += matches * 0.1
        
        return min(1.0, spam_score)
    
    def _analyze_domain_quality(self, url: str) -> float:
        """Analyze domain quality (0-1, higher is better)."""
        if not url:
            return 0.5
        
        try:
            domain = urlparse(url).netloc.lower()
            domain = domain.replace('www.', '')
            
            if domain in self.low_quality_domains:
                return 0.2
            
            # Check for spam indicators in domain
            if any(spam_word in domain for spam_word in ['seo', 'marketing', 'ads', 'spam']):
                return 0.3
            
            # News and educational domains get higher scores
            if any(tld in domain for tld in ['.edu', '.gov', '.org']):
                return 0.9
            
            if any(news_word in domain for news_word in ['news', 'journal', 'times', 'post']):
                return 0.8
            
            return 0.6  # Default for unknown domains
            
        except Exception:
            return 0.5
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate content readability score using textstat if available."""
        if not TEXTSTAT_AVAILABLE or len(content) < 100:
            return 0.5
        
        try:
            # Flesch Reading Ease: 0-100, higher is more readable
            flesch_score = textstat.flesch_reading_ease(content)
            # Convert to 0-1 scale
            return max(0.0, min(1.0, flesch_score / 100))
        except Exception:
            return 0.5
    
    def _analyze_content_structure(self, content: str) -> float:
        """Analyze content structure quality."""
        # Check for proper sentence structure
        sentences = re.findall(r'[.!?]+', content)
        if len(sentences) < 3:
            return 0.2
        
        # Check for paragraph breaks
        paragraphs = content.split('\n\n')
        if len(paragraphs) < 2:
            return 0.4
        
        # Check for balanced sentence lengths
        words = content.split()
        if len(words) < 50:
            return 0.3
        
        sentence_lengths = []
        current_sentence = []
        
        for word in words:
            current_sentence.append(word)
            if word.endswith('.') or word.endswith('!') or word.endswith('?'):
                sentence_lengths.append(len(current_sentence))
                current_sentence = []
        
        if sentence_lengths:
            avg_length = statistics.mean(sentence_lengths)
            # Good articles have 10-25 words per sentence on average
            if 10 <= avg_length <= 25:
                return 0.8
            elif 5 <= avg_length <= 35:
                return 0.6
            else:
                return 0.3
        
        return 0.5
    
    def _calculate_keyword_density(self, content: str) -> float:
        """Calculate keyword density score (0-1, lower is better for natural content)."""
        words = content.lower().split()
        if len(words) < 20:
            return 0.5
        
        word_counts = Counter(words)
        most_common = word_counts.most_common(5)
        
        # Calculate density of top keywords
        total_density = 0
        for word, count in most_common:
            if len(word) > 3:  # Skip very short words
                density = count / len(words)
                total_density += density
        
        # Natural content has lower keyword density
        return 1.0 - min(1.0, total_density)
    
    def _calculate_overall_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate weighted overall quality score."""
        weights = {
            'unique_word_ratio': 0.2,
            'domain_quality': 0.15,
            'readability_score': 0.15,
            'content_structure_score': 0.2,
            'keyword_density_score': 0.1,
            'navigation_ratio': -0.1,  # Negative weight
            'spam_pattern_score': -0.15,  # Negative weight
            'repetition_score': -0.05   # Negative weight
        }
        
        score = 0.5  # Base score
        for metric, weight in weights.items():
            if metric in analysis:
                score += analysis[metric] * weight
        
        return max(0.0, min(1.0, score))
    
    def _is_garbage_content(self, analysis: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Determine if content is garbage based on analysis."""
        reasons = []
        
        # Critical failure conditions
        if analysis['unique_word_ratio'] < 0.3:
            reasons.append(f"Low unique word ratio: {analysis['unique_word_ratio']:.2f}")
        
        if analysis['repetition_score'] > 0.4:
            reasons.append(f"High repetition: {analysis['repetition_score']:.2f}")
        
        if analysis['navigation_ratio'] > 0.3:
            reasons.append(f"Mostly navigation text: {analysis['navigation_ratio']:.2f}")
        
        if analysis['spam_pattern_score'] > 0.2:
            reasons.append(f"Spam patterns detected: {analysis['spam_pattern_score']:.2f}")
        
        if analysis['avg_sentence_length'] > 50 or analysis['avg_sentence_length'] < 3:
            reasons.append(f"Abnormal sentence length: {analysis['avg_sentence_length']:.1f}")
        
        if analysis['domain_quality'] < 0.3:
            reasons.append("Low-quality domain")
        
        # Keyword dump detection
        if analysis['word_count'] > 200 and analysis['sentence_count'] < 5:
            reasons.append("Likely keyword dump - too few sentences")
        
        return len(reasons) >= 2, reasons  # Need multiple red flags

# Global filter instance
content_filter = ContentQualityFilter()