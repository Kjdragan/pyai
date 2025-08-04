#!/usr/bin/env python3
"""
Simple test script for the ResearchDataLogger that doesn't require external APIs.
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the logger and models
from research_logger import ResearchDataLogger
from models import (
    ResearchPipelineModel, YouTubeTranscriptModel, WeatherModel, 
    ReportGenerationModel, MasterOutputModel, JobRequest, 
    ResearchItem, AgentResponse
)
from pydantic import HttpUrl

def create_test_youtube_model():
    """Create a test YouTube transcript model with an HttpUrl."""
    return YouTubeTranscriptModel(
        url=HttpUrl("https://www.youtube.com/watch?v=test123"),
        transcript="This is a test transcript.",
        metadata={
            "video_id": "test123",
            "language": "en",
            "language_code": "en",
            "is_generated": True,
            "transcript_length": 25,
            "segments_count": 1,
            "is_translatable": True,
            "available_languages": ["en"],
            "translation_languages": [{"language": "English", "language_code": "en"}],
            "duration_seconds": 120.0,
            "first_segment_start": 0.0,
            "last_segment_end": 120.0
        },
        title="Test Video",
        duration="2:00",
        channel="Test Channel"
    )

def create_test_research_model():
    """Create a test research pipeline model."""
    return ResearchPipelineModel(
        original_query="test query",
        sub_queries=["test sub-query 1", "test sub-query 2"],
        pipeline_type="tavily",
        total_results=2,
        processing_time=1.5,
        results=[
            ResearchItem(
                query_variant="test sub-query 1",
                source_url=HttpUrl("https://example.com/1"),
                title="Test Result 1",
                snippet="This is test result 1",
                relevance_score=0.9,
                timestamp=datetime.now()
            ),
            ResearchItem(
                query_variant="test sub-query 2",
                source_url=HttpUrl("https://example.com/2"),
                title="Test Result 2",
                snippet="This is test result 2",
                relevance_score=0.8,
                timestamp=datetime.now()
            )
        ]
    )

def create_test_master_output():
    """Create a test master output model."""
    return MasterOutputModel(
        job_request=JobRequest(
            job_type="research",
            query="test query",
            report_style="concise"
        ),
        orchestrator_id="test-orchestrator",
        agents_used=["TavilyResearchAgent"],
        success=True,
        errors=[],
        total_processing_time=2.0
    )

def main():
    """Test the logger with mock data."""
    print("Testing ResearchDataLogger with mock data...")
    
    # Create the logger
    logger = ResearchDataLogger(log_dir="logs")
    
    # Create test models
    youtube_model = create_test_youtube_model()
    research_model = create_test_research_model()
    master_output = create_test_master_output()
    
    # Test logging YouTube model
    print("\nTesting YouTube model logging...")
    youtube_log_file = logger.log_youtube_state(youtube_model, master_output)
    print(f"YouTube log file: {youtube_log_file}")
    
    # Test logging Research model
    print("\nTesting Research model logging...")
    research_log_file = logger.log_research_state(research_model, master_output)
    print(f"Research log file: {research_log_file}")
    
    print("\nTest completed successfully!")
    print("Check the logs directory for the generated JSON files.")

if __name__ == "__main__":
    main()
