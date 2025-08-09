#!/usr/bin/env python3
"""
Test PDF text extraction on various PDF types to validate our implementation.
This will help us understand what types of PDFs we can successfully process.
"""

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.pdf_extractor import extract_pdf_text_from_url, get_pdf_extraction_stats, clear_pdf_cache
from utils.intelligent_scraper import scrape_url_content_detailed

# Test PDFs from various sources and types
TEST_PDF_URLS = [
    # NREL PDFs (mentioned in evaluation - academic/research PDFs)
    "https://www.nrel.gov/docs/fy21osti/79597.pdf",
    "https://www.nrel.gov/docs/fy22osti/82237.pdf",
    
    # Academic papers from arXiv (high-quality text PDFs)
    "https://arxiv.org/pdf/2023.12345.pdf",  # This will likely 404, but tests error handling
    
    # Government reports (structured PDFs)
    "https://www.energy.gov/sites/default/files/2023/11/f5/hydrogen-program-plan-2020.pdf",
    
    # Simple test PDF (if available)
    "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
]

async def test_pdf_extraction():
    """Test PDF extraction on various PDF types."""
    print("🧪 Testing PDF Text Extraction Implementation")
    print("=" * 60)
    
    clear_pdf_cache()  # Start fresh
    
    successful_extractions = 0
    total_chars_extracted = 0
    
    for i, pdf_url in enumerate(TEST_PDF_URLS, 1):
        print(f"\n📄 Test {i}/{len(TEST_PDF_URLS)}: {pdf_url}")
        print("-" * 50)
        
        try:
            # Test direct PDF extraction
            result = await extract_pdf_text_from_url(pdf_url, max_size_mb=25)
            
            if result.success:
                successful_extractions += 1
                total_chars_extracted += result.text_length
                
                print(f"✅ SUCCESS: Extracted {result.text_length:,} chars from {result.page_count} pages")
                print(f"   Processing time: {result.processing_time:.2f}s")
                print(f"   PDF size: {result.pdf_size_bytes / 1024 / 1024:.1f}MB")
                print(f"   First 200 chars: {result.text_content[:200]}...")
                
                # Test if content looks reasonable
                if result.text_length > 1000:
                    print("   ✅ Good text extraction (>1000 chars)")
                elif result.text_length > 100:
                    print("   ⚠️  Limited text extraction (100-1000 chars)")
                else:
                    print("   ❌ Minimal text extraction (<100 chars)")
                    
            else:
                print(f"❌ FAILED: {result.error_reason}")
                print(f"   Processing time: {result.processing_time:.2f}s")
                
        except Exception as e:
            print(f"💥 EXCEPTION: {str(e)}")
    
    print(f"\n📊 EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Successful extractions: {successful_extractions}/{len(TEST_PDF_URLS)}")
    print(f"Total characters extracted: {total_chars_extracted:,}")
    print(f"Success rate: {successful_extractions/len(TEST_PDF_URLS)*100:.1f}%")
    
    # Show cache stats
    cache_stats = get_pdf_extraction_stats()
    print(f"Cache statistics: {cache_stats}")

async def test_integrated_scraper():
    """Test PDF extraction through the intelligent scraper."""
    print(f"\n🔄 Testing Integrated Scraper PDF Handling")
    print("=" * 60)
    
    # Test a PDF URL through the intelligent scraper
    test_pdf = "https://www.nrel.gov/docs/fy21osti/79597.pdf"
    print(f"Testing: {test_pdf}")
    
    try:
        result = await scrape_url_content_detailed(test_pdf, max_chars=20000)
        
        if result.success:
            print(f"✅ Integrated scraper SUCCESS: {len(result.content):,} chars")
            print(f"   Processing time: {result.processing_time:.2f}s") 
            print(f"   Content preview: {result.content[:200]}...")
        else:
            print(f"❌ Integrated scraper FAILED: {result.error_reason}")
            
    except Exception as e:
        print(f"💥 Integrated scraper EXCEPTION: {str(e)}")

if __name__ == "__main__":
    print("Starting PDF extraction tests...")
    
    # Run tests
    asyncio.run(test_pdf_extraction())
    asyncio.run(test_integrated_scraper())
    
    print("\n🎯 Test complete! Check results above to validate PDF processing capabilities.")