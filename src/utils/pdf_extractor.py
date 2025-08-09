"""
Fast PDF Text Extraction Utility
Uses PyMuPDF for high-performance, local PDF text extraction without LLM dependency.
Designed to handle various PDF types and provide raw text for downstream LLM cleaning.
"""

import asyncio
import httpx
import fitz  # PyMuPDF
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
from urllib.parse import urlparse
import hashlib
import logging

logger = logging.getLogger(__name__)

@dataclass
class PDFExtractionResult:
    """Result of PDF text extraction with detailed metadata."""
    success: bool
    text_content: str
    error_reason: Optional[str] = None
    page_count: int = 0
    text_length: int = 0
    processing_time: float = 0.0
    pdf_size_bytes: int = 0
    extraction_method: str = "pymupdf"


class PDFTextExtractor:
    """High-performance PDF text extractor using PyMuPDF."""
    
    def __init__(self, timeout: float = 30.0):
        """Initialize PDF extractor with optimized settings."""
        self.timeout = timeout
        self.extraction_cache: Dict[str, PDFExtractionResult] = {}  # URL hash -> result
        self._user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    
    def _get_url_hash(self, url: str) -> str:
        """Generate consistent hash for URL-based caching."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def extract_text_from_bytes(self, pdf_bytes: bytes, source_identifier: str = "unknown") -> PDFExtractionResult:
        """
        Extract text from PDF bytes using PyMuPDF.
        Fast, local processing without LLM dependency.
        """
        start_time = time.time()
        
        try:
            # Open PDF document from bytes
            doc = fitz.open("pdf", pdf_bytes)
            
            # Extract text from all pages
            text_parts = []
            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_text = page.get_text()
                
                # Basic cleanup - remove excessive whitespace
                cleaned_page_text = " ".join(page_text.split())
                if cleaned_page_text.strip():
                    text_parts.append(cleaned_page_text)
            
            # Combine all pages
            full_text = " ".join(text_parts)
            doc.close()
            
            processing_time = time.time() - start_time
            
            if not full_text.strip():
                return PDFExtractionResult(
                    success=False,
                    text_content="",
                    error_reason="No extractable text found (may be scanned/image-based PDF)",
                    page_count=doc.page_count,
                    processing_time=processing_time,
                    pdf_size_bytes=len(pdf_bytes)
                )
            
            return PDFExtractionResult(
                success=True,
                text_content=full_text,
                page_count=doc.page_count,
                text_length=len(full_text),
                processing_time=processing_time,
                pdf_size_bytes=len(pdf_bytes)
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"PDF extraction failed: {str(e)}"
            logger.error(f"PDF extraction error for {source_identifier}: {error_msg}")
            
            return PDFExtractionResult(
                success=False,
                text_content="",
                error_reason=error_msg,
                processing_time=processing_time,
                pdf_size_bytes=len(pdf_bytes)
            )
    
    async def extract_text_from_url(self, pdf_url: str, max_size_mb: int = 50) -> PDFExtractionResult:
        """
        Download and extract text from PDF URL.
        Includes size limits and caching for efficiency.
        """
        start_time = time.time()
        url_hash = self._get_url_hash(pdf_url)
        
        # Check cache first
        if url_hash in self.extraction_cache:
            logger.info(f"📄 Using cached PDF extraction for {pdf_url}")
            return self.extraction_cache[url_hash]
        
        try:
            # Download PDF with size limit
            headers = {'User-Agent': self._user_agent}
            
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
                # Stream download to check size before processing
                async with client.stream('GET', pdf_url) as response:
                    response.raise_for_status()
                    
                    # Check content length
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > max_size_mb * 1024 * 1024:
                        return PDFExtractionResult(
                            success=False,
                            text_content="",
                            error_reason=f"PDF too large: {int(content_length) / 1024 / 1024:.1f}MB > {max_size_mb}MB limit",
                            processing_time=time.time() - start_time
                        )
                    
                    # Download content
                    pdf_bytes = b""
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        pdf_bytes += chunk
                        
                        # Check size during download
                        if len(pdf_bytes) > max_size_mb * 1024 * 1024:
                            return PDFExtractionResult(
                                success=False,
                                text_content="",
                                error_reason=f"PDF download exceeded {max_size_mb}MB limit",
                                processing_time=time.time() - start_time
                            )
            
            # Extract text from downloaded bytes
            result = self.extract_text_from_bytes(pdf_bytes, pdf_url)
            
            # Cache successful results
            if result.success:
                self.extraction_cache[url_hash] = result
                logger.info(f"📄 Successfully extracted {result.text_length:,} chars from {result.page_count} pages: {pdf_url}")
            else:
                logger.warning(f"📄 Failed to extract text from PDF: {pdf_url} - {result.error_reason}")
            
            return result
            
        except httpx.TimeoutException:
            return PDFExtractionResult(
                success=False,
                text_content="",
                error_reason="PDF download timeout",
                processing_time=time.time() - start_time
            )
        except httpx.HTTPStatusError as e:
            return PDFExtractionResult(
                success=False,
                text_content="",
                error_reason=f"HTTP {e.response.status_code} downloading PDF",
                processing_time=time.time() - start_time
            )
        except Exception as e:
            return PDFExtractionResult(
                success=False,
                text_content="",
                error_reason=f"PDF processing error: {str(e)}",
                processing_time=time.time() - start_time
            )
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about the extraction cache."""
        successful_extractions = sum(1 for result in self.extraction_cache.values() if result.success)
        total_text_chars = sum(result.text_length for result in self.extraction_cache.values() if result.success)
        
        return {
            "cached_pdfs": len(self.extraction_cache),
            "successful_extractions": successful_extractions,
            "total_extracted_chars": total_text_chars,
            "cache_hit_rate": len(self.extraction_cache) / max(1, len(self.extraction_cache))
        }
    
    def clear_cache(self):
        """Clear the extraction cache (useful for new research sessions)."""
        self.extraction_cache.clear()
        logger.info("📄 PDF extraction cache cleared")


# Global PDF extractor instance
_global_pdf_extractor = PDFTextExtractor()

# Convenience functions for easy integration
async def extract_pdf_text_from_url(pdf_url: str, max_size_mb: int = 50) -> PDFExtractionResult:
    """Extract text from PDF URL using global extractor instance."""
    return await _global_pdf_extractor.extract_text_from_url(pdf_url, max_size_mb)

def extract_pdf_text_from_bytes(pdf_bytes: bytes, source_name: str = "unknown") -> PDFExtractionResult:
    """Extract text from PDF bytes using global extractor instance."""
    return _global_pdf_extractor.extract_text_from_bytes(pdf_bytes, source_name)

def get_pdf_extraction_stats() -> Dict[str, int]:
    """Get global PDF extraction statistics."""
    return _global_pdf_extractor.get_cache_stats()

def clear_pdf_cache():
    """Clear global PDF extraction cache."""
    _global_pdf_extractor.clear_cache()