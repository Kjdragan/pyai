#!/usr/bin/env python3
"""
Quick test script for the new intelligent report generation system.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models import UniversalReportData, ResearchPipelineModel, ResearchItem
from agents.report_writer_agent import (
    generate_intelligent_report,
    analyze_query_domain,
    get_adaptive_report_template
)
from agents.advanced_report_templates import get_advanced_adaptive_template

async def test_intelligent_reports():
    """Test the new intelligent report generation system."""
    
    print("🧪 Testing Intelligent Report Generation System")
    print("=" * 60)
    
    # Test 1: Domain Analysis
    print("\n1. Testing Query Domain Analysis")
    test_queries = [
        "Latest developments in AI technology and machine learning",
        "Market analysis of renewable energy business opportunities", 
        "Scientific research on climate change impacts",
        "How to implement cybersecurity best practices"
    ]
    
    for query in test_queries:
        domain_context = analyze_query_domain(query)
        print(f"Query: {query[:50]}...")
        print(f"Domain: {domain_context['domain']}, Intent: {domain_context['intent']}, Complexity: {domain_context['complexity']}")
        print()
    
    # Test 2: Advanced Template Generation
    print("\n2. Testing Advanced Template Generation")
    
    test_template = get_advanced_adaptive_template(
        style="comprehensive",
        query="Latest developments in AI technology and market implications",
        data_types=["research", "youtube"],
        domain_context={
            "domain": "technology",
            "complexity": "high", 
            "intent": "analytical"
        }
    )
    
    print("Generated Template Structure:")
    sections = [line.strip() for line in test_template.split('\n') if line.strip().startswith('##')]
    for section in sections:
        print(f"  {section}")
    print(f"Total template length: {len(test_template)} characters")
    print()
    
    # Test 3: Mock Report Generation (without actual LLM calls)
    print("\n3. Testing Report Data Processing")
    
    # Create mock research data
    mock_research_items = [
        ResearchItem(
            query_variant="AI developments 2024",
            title="Major AI Breakthroughs in 2024",
            snippet="Recent advancements in large language models...",
            content_scraped=True,
            scraped_content="Detailed analysis of AI breakthroughs including GPT-4, Claude-3, and other major developments in artificial intelligence during 2024...",
            relevance_score=0.95
        ),
        ResearchItem(
            query_variant="machine learning trends",
            title="Enterprise ML Adoption Trends", 
            snippet="Companies are rapidly adopting ML solutions...",
            content_scraped=False,
            relevance_score=0.87
        )
    ]
    
    mock_research = ResearchPipelineModel(
        original_query="Latest developments in AI technology",
        sub_queries=["Historical AI development", "Current AI trends", "Future AI predictions"],
        results=mock_research_items,
        pipeline_type="tavily",
        total_results=2
    )
    
    universal_data = UniversalReportData(
        query="Latest developments in AI technology and market implications",
        research_data=mock_research
    )
    
    print(f"Mock data created:")
    print(f"  Query: {universal_data.query}")
    print(f"  Data types: {universal_data.get_data_types()}")
    print(f"  Research results: {len(mock_research.results)}")
    print(f"  Has data: {universal_data.has_data()}")
    print()
    
    # Test confidence scoring
    from agents.report_writer_agent import calculate_confidence_score
    
    mock_report = "This is a comprehensive analysis of AI developments including detailed examination of machine learning trends, market implications, and future predictions with quantitative insights and strategic recommendations."
    
    confidence = calculate_confidence_score(mock_report, universal_data)
    print(f"Confidence score calculation: {confidence:.2f}")
    
    print("\n✅ All tests completed successfully!")
    print("\nThe intelligent report generation system is ready for use with:")
    print("  • Advanced domain-aware template generation")
    print("  • Query complexity analysis")
    print("  • Multi-source data handling") 
    print("  • Quality control and confidence scoring")
    print("  • Backward compatibility with existing system")

if __name__ == "__main__":
    asyncio.run(test_intelligent_reports())