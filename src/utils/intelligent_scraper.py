"""
Intelligent Web Scraper with Pre-Scrape Gating
Optimized for research agents to avoid blocked/slow sites and handle errors gracefully.
"""

import asyncio
import httpx
import time
from typing import Optional, Dict, List, Set, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
from dataclasses import dataclass
from bs4 import BeautifulSoup
import re
from collections import defaultdict, deque


@dataclass
class ScrapingResult:
    """Result of a scraping attempt with detailed metadata."""
    success: bool
    content: str
    error_reason: Optional[str] = None
    status_code: Optional[int] = None
    content_length: int = 0
    processing_time: float = 0.0
    was_blocked: bool = False
    block_reason: Optional[str] = None


class IntelligentScraper:
    """Advanced scraper with pre-flight checks and intelligent error handling."""
    
    # PERFORMANCE OPTIMIZATION: Blacklist known problematic domains
    BLOCKED_DOMAINS = {
        "statista.com",          # Always redirects to paywall/SSO
        "wsj.com",              # Wall Street Journal paywall  
        "ft.com",               # Financial Times paywall
        "nytimes.com",          # NYT paywall
        "sciencedirect.com",    # Academic paywall/institutional access
        "jstor.org",            # Academic paywall
        "springer.com",         # Academic paywall
        "wiley.com",            # Academic paywall
        "tandfonline.com",      # Academic paywall
    }
    
    # Content types to skip (non-text content)
    BLOCKED_CONTENT_TYPES = {
        "application/pdf",      # PDFs need special handling
        "application/msword", 
        "application/vnd.openxmlformats-officedocument",
        "image/",              # Any image type
        "video/",              # Any video type  
        "audio/",              # Any audio type
        "application/zip",
        "application/octet-stream",
    }
    
    # Paywall/SSO detection patterns
    PAYWALL_PATTERNS = [
        "please sign in to continue",
        "subscription required", 
        "access denied",
        "login required",
        "premium content",
        "register to read",
        "create account",
        "institutional access",
        "this content is restricted",
        "paywall",
        "subscribe now",
        "free trial",
    ]
    
    # Redirect patterns that indicate blocks
    BLOCK_REDIRECT_PATTERNS = [
        "login",
        "signin", 
        "auth",
        "paywall",
        "subscribe",
        "premium",
        "blocked",
        "access-denied",
    ]
    
    def __init__(self, timeout: float = 15.0):
        """Initialize scraper with optimized settings and rate limiting."""
        self.timeout = timeout
        self.session_urls: Set[str] = set()  # In-session URL deduplication
        self._user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        # ENHANCED RATE LIMITING: Cache failed domains/URLs to avoid retrying
        self.failed_domains: Set[str] = set()  # Domains that consistently fail
        self.failed_urls: Set[str] = set()     # Specific URLs that failed
        self.domain_request_times: Dict[str, deque] = defaultdict(deque)  # Track request times per domain
        self.min_request_interval = 1.0  # Minimum seconds between requests to same domain
        self.max_requests_per_minute = 10  # Maximum requests per domain per minute
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication (remove tracking params, etc.)."""
        try:
            parsed = urlparse(url.lower().strip())
            
            # Remove common tracking parameters
            query_params = parse_qs(parsed.query)
            cleaned_params = {
                k: v for k, v in query_params.items()
                if not any(tracker in k.lower() for tracker in [
                    'utm_', 'gclid', 'fbclid', 'ref', '_hsenc', '__hstc', 
                    'source', 'campaign', 'medium', 'mcid', 'cid'
                ])
            }
            
            # Reconstruct clean URL
            clean_query = '&'.join(f"{k}={v[0]}" for k, v in cleaned_params.items())
            
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" + (
                f"?{clean_query}" if clean_query else ""
            )
        except:
            return url.lower().strip()
    
    def should_skip_domain(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if domain should be skipped entirely."""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Check static blacklist
            for blocked_domain in self.BLOCKED_DOMAINS:
                if blocked_domain in domain:
                    return True, f"Domain blocked: {blocked_domain}"
            
            # ENHANCED RATE LIMITING: Check dynamic failure cache
            if domain in self.failed_domains:
                return True, f"Domain previously failed: {domain}"
            
            if url in self.failed_urls:
                return True, f"URL previously failed: {url}"
            
            return False, None
        except:
            return True, "Invalid URL format"
    
    async def apply_rate_limiting(self, url: str) -> None:
        """Apply rate limiting delays to prevent overwhelming domains."""
        try:
            domain = urlparse(url).netloc.lower()
            current_time = time.time()
            
            # Clean old request times (keep only last minute)
            domain_times = self.domain_request_times[domain]
            while domain_times and current_time - domain_times[0] > 60:
                domain_times.popleft()
            
            # Check if we've exceeded requests per minute limit
            if len(domain_times) >= self.max_requests_per_minute:
                oldest_request = domain_times[0]
                wait_time = 60 - (current_time - oldest_request)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
            
            # Ensure minimum interval between requests to same domain
            if domain_times:
                time_since_last = current_time - domain_times[-1]
                if time_since_last < self.min_request_interval:
                    await asyncio.sleep(self.min_request_interval - time_since_last)
                    current_time = time.time()
            
            # Record this request time
            self.domain_request_times[domain].append(current_time)
            
        except Exception:
            # If rate limiting fails, don't block the request
            pass
    
    def record_failure(self, url: str, failure_type: str) -> None:
        """Record failures for future quick failure."""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Record specific URL failure
            self.failed_urls.add(url)
            
            # Record domain failure for certain types of persistent issues
            persistent_failure_types = [
                "HTTP 403", "HTTP 401", "HTTP 404", 
                "Paywall", "Domain blocked", "Redirect to blocked pattern"
            ]
            
            if any(failure in failure_type for failure in persistent_failure_types):
                self.failed_domains.add(domain)
                
        except Exception:
            pass
    
    async def pre_flight_check(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Perform HEAD request to check if URL is accessible without full download.
        Returns (should_proceed, skip_reason).
        """
        try:
            headers = {'User-Agent': self._user_agent}
            
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                # Use HEAD request for fast pre-check
                response = await client.head(url, follow_redirects=False)
                
                # Check for problematic status codes
                if response.status_code in [401, 403, 404, 429]:
                    return False, f"HTTP {response.status_code}"
                
                # Check for redirects to blocked patterns
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('location', '')
                    if any(pattern in location.lower() for pattern in self.BLOCK_REDIRECT_PATTERNS):
                        return False, f"Redirect to blocked pattern: {location}"
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                for blocked_type in self.BLOCKED_CONTENT_TYPES:
                    if blocked_type in content_type:
                        return False, f"Blocked content type: {content_type}"
                
                return True, None
                
        except (httpx.TimeoutException, httpx.ConnectTimeout):
            return False, "Pre-flight timeout" 
        except Exception as e:
            return False, f"Pre-flight error: {str(e)}"
    
    def detect_paywall_content(self, content: str) -> Tuple[bool, Optional[str]]:
        """Detect if scraped content indicates a paywall or access restriction."""
        content_lower = content.lower()
        
        for pattern in self.PAYWALL_PATTERNS:
            if pattern in content_lower:
                return True, f"Paywall pattern: {pattern}"
        
        # Additional heuristics
        if len(content.strip()) < 100 and any(word in content_lower for word in ['login', 'subscribe', 'access']):
            return True, "Short content with access keywords"
        
        return False, None
    
    def _is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF file."""
        try:
            # Handle URLs with query parameters (like the GWEC example)
            path = urlparse(url or "").path.lower()
            return path.endswith(".pdf") or ".pdf" in path
        except Exception:
            return False
    
    async def _handle_pdf_extraction(self, pdf_url: str, start_time: float) -> ScrapingResult:
        """Handle PDF text extraction using dedicated PDF extractor."""
        try:
            # Import PDF extractor (lazy import to avoid circular dependencies)
            from utils.pdf_extractor import extract_pdf_text_from_url
            
            # Extract text from PDF
            pdf_result = await extract_pdf_text_from_url(pdf_url, max_size_mb=50)
            
            processing_time = time.time() - start_time
            
            if pdf_result.success:
                return ScrapingResult(
                    success=True,
                    content=pdf_result.text_content,
                    status_code=200,  # Assume successful PDF download
                    content_length=len(pdf_result.text_content),
                    processing_time=processing_time
                )
            else:
                return ScrapingResult(
                    success=False,
                    content="",
                    error_reason=f"PDF extraction failed: {pdf_result.error_reason}",
                    processing_time=processing_time
                )
        
        except Exception as e:
            return ScrapingResult(
                success=False,
                content="",
                error_reason=f"PDF processing error: {str(e)}",
                processing_time=time.time() - start_time
            )

    async def scrape_url_content(self, url: str, max_chars: int = 10000) -> ScrapingResult:
        """
        Enhanced scraping with pre-flight checks, intelligent error handling, rate limiting, and PDF support.
        """
        start_time = time.time()
        
        try:
            # Step 1: Check if this is a PDF URL
            if self._is_pdf_url(url):
                return await self._handle_pdf_extraction(url, start_time)
            
            # Step 2: Normalize URL and check for duplicates (non-PDFs only)
            normalized_url = self.normalize_url(url)
            if normalized_url in self.session_urls:
                return ScrapingResult(
                    success=False,
                    content="",
                    error_reason="Duplicate URL in session",
                    processing_time=time.time() - start_time
                )
            self.session_urls.add(normalized_url)
            
            # Step 3: Domain blacklist check (includes enhanced failure cache)
            should_skip, skip_reason = self.should_skip_domain(url)
            if should_skip:
                result = ScrapingResult(
                    success=False,
                    content="",
                    error_reason=skip_reason,
                    was_blocked=True,
                    block_reason=skip_reason,
                    processing_time=time.time() - start_time
                )
                # Don't record this as a new failure since it's already cached
                return result
            
            # Step 3.5: ENHANCED RATE LIMITING - Apply delays to prevent overwhelming domains
            await self.apply_rate_limiting(url)
            
            # Step 4: Pre-flight HEAD check
            should_proceed, preflight_reason = await self.pre_flight_check(url)
            if not should_proceed:
                result = ScrapingResult(
                    success=False, 
                    content="",
                    error_reason=f"Pre-flight failed: {preflight_reason}",
                    was_blocked=True,
                    block_reason=preflight_reason,
                    processing_time=time.time() - start_time
                )
                # Record failure for future quick failure
                self.record_failure(url, preflight_reason or "Pre-flight failed")
                return result
            
            # Step 5: Full content scraping (HTML/text)
            headers = {'User-Agent': self._user_agent}
            
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Parse HTML content
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script, style, and navigation elements
                for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    element.decompose()
                
                # Get text content
                text = soup.get_text()
                
                # Clean up text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                cleaned_text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Step 6: Paywall detection
                is_paywall, paywall_reason = self.detect_paywall_content(cleaned_text)
                if is_paywall:
                    result = ScrapingResult(
                        success=False,
                        content="",
                        error_reason=f"Paywall detected: {paywall_reason}",
                        status_code=response.status_code,
                        was_blocked=True,
                        block_reason=paywall_reason,
                        processing_time=time.time() - start_time
                    )
                    # Record paywall failure for future quick failure
                    self.record_failure(url, f"Paywall: {paywall_reason}")
                    return result
                
                # Step 7: Limit content length
                if len(cleaned_text) > max_chars:
                    cleaned_text = cleaned_text[:max_chars] + "..."
                
                return ScrapingResult(
                    success=True,
                    content=cleaned_text,
                    status_code=response.status_code,
                    content_length=len(cleaned_text),
                    processing_time=time.time() - start_time
                )
        
        except httpx.TimeoutException:
            result = ScrapingResult(
                success=False,
                content="",
                error_reason="Request timeout",
                processing_time=time.time() - start_time
            )
            # Record timeout failure for future quick failure
            self.record_failure(url, "Request timeout")
            return result
        except httpx.HTTPStatusError as e:
            result = ScrapingResult(
                success=False,
                content="",
                error_reason=f"HTTP {e.response.status_code}",
                status_code=e.response.status_code,
                processing_time=time.time() - start_time
            )
            # Record HTTP error for future quick failure
            self.record_failure(url, f"HTTP {e.response.status_code}")
            return result
        except Exception as e:
            result = ScrapingResult(
                success=False,
                content="",
                error_reason=f"Scraping error: {str(e)}",
                processing_time=time.time() - start_time
            )
            # Record general error (but don't cache domain since it might be transient)
            self.failed_urls.add(url)
            return result
    
    def get_session_stats(self) -> Dict[str, int]:
        """Get statistics about the current scraping session."""
        return {
            "urls_processed": len(self.session_urls),
            "failed_domains_cached": len(self.failed_domains),
            "failed_urls_cached": len(self.failed_urls),
            "domains_with_rate_limiting": len(self.domain_request_times),
        }
    
    def reset_session(self):
        """Reset session state (useful for new research queries)."""
        self.session_urls.clear()
        # Note: We intentionally keep failed domains/URLs cached across sessions
        # to maintain quick failure benefits across multiple research queries
        # Only clear domain request times for fresh rate limiting
        self.domain_request_times.clear()
    
    def clear_failure_cache(self):
        """Clear cached failures (useful for testing or manual reset)."""
        self.failed_domains.clear()
        self.failed_urls.clear()


# Global scraper instance for shared use across agents
_global_scraper = IntelligentScraper()

# Convenience functions for backward compatibility
async def scrape_url_content(url: str, max_chars: int = 10000) -> str:
    """Legacy compatibility function - returns just the content string."""
    result = await _global_scraper.scrape_url_content(url, max_chars)
    return result.content if result.success else ""

async def scrape_url_content_detailed(url: str, max_chars: int = 10000) -> ScrapingResult:
    """Enhanced function that returns detailed scraping results."""
    return await _global_scraper.scrape_url_content(url, max_chars)