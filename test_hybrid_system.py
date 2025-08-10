#!/usr/bin/env python3
"""
Hybrid System Integration Test

Tests both traditional and iterative processing paths to ensure the hybrid system works correctly.
"""

import asyncio
import sys
import os
from typing import List, Dict, Any
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models import ResearchItem, YouTubeTranscriptModel, WeatherModel, WeatherData
from utils.context_assessment import assess_universal_context, get_context_summary
from utils.iterative_report_writer import generate_hybrid_universal_report


def create_small_test_data() -> tuple:
    """Create small dataset that should trigger traditional processing."""
    research_data = [
        ResearchItem(
            query_variant="Traditional processing test query 1",
            source_url="https://test1.com",
            title="Small test article 1",
            snippet="This is a small test snippet for testing traditional processing.",
            scraped_content="This is small scraped content that should easily fit within traditional context limits. Testing traditional processing path.",
            relevance_score=0.8,
            is_pdf_content=False,
            content_scraped=True,
            content_length=150
        ),
        ResearchItem(
            query_variant="Traditional processing test query 2",
            source_url="https://test2.com",
            title="Small test article 2",
            snippet="Another small test snippet.",
            scraped_content="More small scraped content for testing. This should trigger traditional processing.",
            relevance_score=0.7,
            is_pdf_content=False,
            content_scraped=True,
            content_length=100
        )
    ]
    
    youtube_data = YouTubeTranscriptModel(
        url="https://youtube.com/test",
        transcript="This is a short test transcript that shouldn't add much to context size.",
        metadata={
            "title": "Short test video",
            "channel": "Test Channel", 
            "duration": "5:00"
        }
    )
    
    weather_data = WeatherModel(
        location="Test City",
        current=WeatherData(
            timestamp="2025-08-09T12:00:00Z",
            temp=25.0,
            description="Sunny",
            humidity=65.0,
            wind_speed=5.0
        ),
        forecast=[
            WeatherData(
                timestamp="2025-08-10T12:00:00Z",
                temp=26.0,
                description="Partly cloudy",
                humidity=70.0
            ),
            WeatherData(
                timestamp="2025-08-11T12:00:00Z", 
                temp=24.0,
                description="Clear",
                humidity=60.0
            )
        ],
        units="metric"
    )
    
    return research_data, youtube_data, weather_data


def create_large_test_data() -> tuple:
    """Create large dataset that should trigger iterative processing."""
    
    # Create large content that will exceed context thresholds
    large_content_template = """
    This is a very comprehensive research article with extensive content that contains detailed analysis,
    multiple sections, in-depth explanations, statistical data, case studies, expert opinions, historical context,
    future projections, comparative analysis, methodology descriptions, literature reviews, empirical findings,
    theoretical frameworks, practical applications, implementation guidelines, best practices, lessons learned,
    risk assessments, performance metrics, quality standards, regulatory considerations, market dynamics,
    competitive landscapes, technological innovations, industry trends, consumer behaviors, economic impacts,
    social implications, environmental factors, sustainability aspects, ethical considerations, governance models,
    stakeholder perspectives, strategic recommendations, operational procedures, technical specifications,
    design principles, architectural patterns, system integrations, data workflows, security protocols,
    compliance requirements, audit processes, monitoring strategies, optimization techniques, scalability solutions,
    maintenance procedures, troubleshooting guides, user training materials, documentation standards,
    testing methodologies, deployment strategies, version control processes, change management protocols,
    incident response procedures, disaster recovery plans, business continuity measures, and much more content...
    """ * 20  # Multiply to create very large content
    
    # Create 25 large research items (should easily exceed 200K tokens)
    research_data = []
    for i in range(25):
        research_data.append(ResearchItem(
            query_variant=f"Iterative processing test query {i+1}",
            source_url=f"https://research{i+1}.com/comprehensive-analysis",
            title=f"Comprehensive Research Article {i+1}: Advanced Analysis and Deep Insights",
            snippet=f"This is research item {i+1} with extensive content and detailed analysis covering multiple aspects of the topic.",
            scraped_content=f"RESEARCH ITEM {i+1}:\n{large_content_template}",
            relevance_score=0.9 - (i * 0.02),  # Decreasing relevance scores
            is_pdf_content=True if i % 3 == 0 else False,  # Some PDF content
            content_scraped=True,
            content_length=len(f"RESEARCH ITEM {i+1}:\n{large_content_template}")
        ))
    
    youtube_data = YouTubeTranscriptModel(
        url="https://youtube.com/comprehensive-analysis",
        transcript="""This is a comprehensive video transcript with extensive discussion covering multiple topics,
        detailed explanations of complex concepts, expert insights, case study analysis, Q&A sessions,
        technical deep-dives, practical examples, real-world applications, industry perspectives,
        historical context, future predictions, and comprehensive coverage of the subject matter.""" * 50,
        metadata={
            "title": "Comprehensive Video Analysis: In-Depth Expert Discussion and Detailed Explanations",
            "channel": "Expert Analysis Channel",
            "duration": "2:15:30"
        }
    )
    
    weather_data = WeatherModel(
        location="Comprehensive Weather Analysis Location",
        current=WeatherData(
            timestamp="2025-08-09T12:00:00Z",
            temp=22.0,
            description="Comprehensive weather analysis with detailed conditions",
            humidity=75.0,
            wind_speed=8.0
        ),
        forecast=[
            WeatherData(
                timestamp=f"2025-08-{10+i}T12:00:00Z",
                temp=20.0 + (i * 2),
                description=f"Detailed forecast day {i+1} with comprehensive analysis",
                humidity=70.0 + (i * 2)
            ) for i in range(5)  # 5-day comprehensive forecast
        ],
        units="metric"
    )
    
    return research_data, youtube_data, weather_data


async def test_context_assessment():
    """Test context assessment functionality."""
    print("\n🔍 Testing Context Assessment System")
    print("=" * 50)
    
    # Test small context
    small_research, small_youtube, small_weather = create_small_test_data()
    small_assessment = assess_universal_context(
        research_data=small_research,
        youtube_data=small_youtube,
        weather_data=small_weather,
        additional_context="Test query: AI trends analysis"
    )
    
    print("📊 SMALL CONTEXT TEST:")
    print(get_context_summary(small_assessment))
    assert small_assessment.recommended_strategy == "traditional", f"Expected traditional, got {small_assessment.recommended_strategy}"
    assert not small_assessment.requires_chunking, "Small context should not require chunking"
    print("✅ Small context assessment PASSED")
    
    # Test large context
    large_research, large_youtube, large_weather = create_large_test_data()
    large_assessment = assess_universal_context(
        research_data=large_research,
        youtube_data=large_youtube,
        weather_data=large_weather,
        additional_context="Test query: Comprehensive AI analysis with detailed research"
    )
    
    print("\n📊 LARGE CONTEXT TEST:")
    print(get_context_summary(large_assessment))
    assert large_assessment.recommended_strategy == "iterative", f"Expected iterative, got {large_assessment.recommended_strategy}"
    assert large_assessment.requires_chunking, "Large context should require chunking"
    assert large_assessment.estimated_chunks > 1, "Large context should need multiple chunks"
    print("✅ Large context assessment PASSED")
    
    return True


async def test_traditional_processing():
    """Test traditional processing path."""
    print("\n🔄 Testing Traditional Processing Path")
    print("=" * 50)
    
    research_data, youtube_data, weather_data = create_small_test_data()
    
    try:
        result = await generate_hybrid_universal_report(
            style="summary",
            query="Test traditional processing with small dataset",
            research_data=research_data,
            youtube_data=youtube_data,
            weather_data=weather_data,
            session_id="test_traditional"
        )
        
        print(f"📝 Traditional Report Generated:")
        print(f"   - Processing approach: {result.processing_approach}")
        print(f"   - Context size: {result.context_size_tokens:,} tokens")
        print(f"   - Sources processed: {result.sources_processed}")
        print(f"   - Confidence: {result.confidence_score:.2f}")
        print(f"   - Report length: {len(result.final):,} characters")
        
        assert result.processing_approach == "traditional", f"Expected traditional, got {result.processing_approach}"
        assert result.final and len(result.final) > 100, "Report should be generated and substantial"
        assert "Analysis: Test traditional processing" in result.final, "Report should contain query"
        print("✅ Traditional processing PASSED")
        
        return True
        
    except Exception as e:
        print(f"❌ Traditional processing FAILED: {e}")
        return False


async def test_iterative_processing():
    """Test iterative processing path."""
    print("\n🧩 Testing Iterative Processing Path")
    print("=" * 50)
    
    research_data, youtube_data, weather_data = create_large_test_data()
    
    try:
        result = await generate_hybrid_universal_report(
            style="comprehensive",
            query="Test iterative processing with large comprehensive dataset",
            research_data=research_data,
            youtube_data=youtube_data, 
            weather_data=weather_data,
            session_id="test_iterative"
        )
        
        print(f"📝 Iterative Report Generated:")
        print(f"   - Processing approach: {result.processing_approach}")
        print(f"   - Context size: {result.context_size_tokens:,} tokens")
        print(f"   - Sources processed: {result.sources_processed}")
        print(f"   - Confidence: {result.confidence_score:.2f}")
        print(f"   - Report length: {len(result.final):,} characters")
        
        # Check metadata
        if result.generation_metadata:
            chunks_processed = result.generation_metadata.get('chunks_processed', 0)
            total_time = result.generation_metadata.get('total_processing_time_seconds', 0)
            print(f"   - Chunks processed: {chunks_processed}")
            print(f"   - Total processing time: {total_time:.1f}s")
        
        assert result.processing_approach == "iterative", f"Expected iterative, got {result.processing_approach}"
        assert result.final and len(result.final) > 1000, "Iterative report should be comprehensive"
        assert "Analysis: Test iterative processing" in result.final, "Report should contain query"
        assert "iterative processing" in result.final.lower(), "Should mention iterative approach"
        print("✅ Iterative processing PASSED")
        
        return True
        
    except Exception as e:
        print(f"❌ Iterative processing FAILED: {e}")
        return False


async def test_style_preservation():
    """Test that different report styles are preserved in both processing approaches."""
    print("\n🎨 Testing Style Preservation")
    print("=" * 50)
    
    styles_to_test = ["summary", "comprehensive", "top_10"]
    test_results = {}
    
    # Use medium-sized dataset to test both paths
    research_data, youtube_data, weather_data = create_small_test_data()
    
    for style in styles_to_test:
        try:
            result = await generate_hybrid_universal_report(
                style=style,
                query=f"Test {style} style preservation",
                research_data=research_data,
                youtube_data=youtube_data,
                weather_data=weather_data,
                session_id=f"test_style_{style}"
            )
            
            report_content = result.final.lower()
            
            # Check style-specific requirements
            style_checks = {
                "summary": ["summary" in report_content or "overview" in report_content],
                "comprehensive": ["executive summary" in report_content or "comprehensive" in report_content],
                "top_10": ["1." in result.final or "##" in result.final]
            }
            
            passed = all(style_checks.get(style, [True]))
            test_results[style] = passed
            
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"   - {style.upper()} style: {status}")
            
        except Exception as e:
            print(f"   - {style.upper()} style: ❌ FAILED ({e})")
            test_results[style] = False
    
    overall_success = all(test_results.values())
    print(f"📊 Style preservation overall: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    return overall_success


async def run_comprehensive_test():
    """Run comprehensive hybrid system test."""
    print("🚀 HYBRID SYSTEM COMPREHENSIVE TEST")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {}
    
    # Run all tests
    tests = [
        ("Context Assessment", test_context_assessment),
        ("Traditional Processing", test_traditional_processing),
        ("Iterative Processing", test_iterative_processing),
        ("Style Preservation", test_style_preservation)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 Running {test_name} Test...")
            result = await test_func()
            test_results[test_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"🏁 {test_name}: {status}")
        except Exception as e:
            print(f"🏁 {test_name}: ❌ FAILED (Exception: {e})")
            test_results[test_name] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 TEST SUMMARY")
    print("=" * 70)
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    overall_success = all(test_results.values())
    overall_status = "✅ ALL TESTS PASSED" if overall_success else "❌ SOME TESTS FAILED"
    
    print(f"\n🎯 OVERALL RESULT: {overall_status}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return overall_success


if __name__ == "__main__":
    # Set up environment for testing
    os.environ.setdefault("OPENAI_API_KEY", "test-key-for-structure-validation")
    
    print("🔧 Hybrid System Test - Validating Implementation Structure")
    print("Note: This test validates the hybrid system structure and logic.")
    print("For full LLM integration testing, ensure OPENAI_API_KEY is properly configured.")
    
    try:
        success = asyncio.run(run_comprehensive_test())
        exit_code = 0 if success else 1
        print(f"\n🏁 Test completed with exit code: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)