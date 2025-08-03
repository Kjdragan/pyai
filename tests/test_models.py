"""
Unit tests for Pydantic data models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from models import (
    YouTubeTranscriptModel, WeatherModel, WeatherData, ResearchItem,
    ResearchPipelineModel, ReportGenerationModel, JobRequest,
    AgentResponse, MasterOutputModel, StreamingUpdate
)


class TestYouTubeTranscriptModel:
    """Test YouTubeTranscriptModel validation and functionality."""
    
    def test_valid_youtube_model(self):
        """Test creating a valid YouTube transcript model."""
        model = YouTubeTranscriptModel(
            url="https://www.youtube.com/watch?v=test123",
            transcript="This is a test transcript",
            metadata={"video_id": "test123", "duration": "5:30"}
        )
        
        assert str(model.url) == "https://www.youtube.com/watch?v=test123"
        assert model.transcript == "This is a test transcript"
        assert model.metadata["video_id"] == "test123"
    
    def test_invalid_url(self):
        """Test that invalid URLs raise validation errors."""
        with pytest.raises(ValidationError):
            YouTubeTranscriptModel(
                url="not-a-valid-url",
                transcript="Test transcript",
                metadata={}
            )


class TestWeatherModel:
    """Test WeatherModel validation and functionality."""
    
    def test_valid_weather_model(self):
        """Test creating a valid weather model."""
        current_weather = WeatherData(
            timestamp="2024-01-01T12:00:00",
            temp=20.5,
            description="sunny",
            humidity=65.0,
            wind_speed=5.2
        )
        
        forecast = [
            WeatherData(
                timestamp="2024-01-02T12:00:00",
                temp=18.0,
                description="cloudy"
            )
        ]
        
        model = WeatherModel(
            location="Test City",
            current=current_weather,
            forecast=forecast,
            units="metric"
        )
        
        assert model.location == "Test City"
        assert model.current.temp == 20.5
        assert len(model.forecast) == 1
        assert model.units == "metric"


class TestResearchModels:
    """Test research-related models."""
    
    def test_research_item(self):
        """Test ResearchItem model."""
        item = ResearchItem(
            query_variant="test query",
            title="Test Title",
            snippet="Test snippet content",
            relevance_score=0.95
        )
        
        assert item.query_variant == "test query"
        assert item.title == "Test Title"
        assert item.relevance_score == 0.95
    
    def test_research_pipeline_model(self):
        """Test ResearchPipelineModel."""
        results = [
            ResearchItem(
                query_variant="test query",
                title="Result 1",
                snippet="Content 1"
            ),
            ResearchItem(
                query_variant="test query",
                title="Result 2", 
                snippet="Content 2"
            )
        ]
        
        model = ResearchPipelineModel(
            original_query="test research",
            sub_queries=["query 1", "query 2", "query 3"],
            results=results,
            pipeline_type="tavily",
            total_results=2
        )
        
        assert model.original_query == "test research"
        assert len(model.sub_queries) == 3
        assert len(model.results) == 2
        assert model.pipeline_type == "tavily"


class TestReportGenerationModel:
    """Test ReportGenerationModel validation."""
    
    def test_valid_report_model(self):
        """Test creating a valid report generation model."""
        model = ReportGenerationModel(
            style="comprehensive",
            prompt_template="Test template",
            draft="Draft content",
            final="Final content",
            source_type="research",
            word_count=100
        )
        
        assert model.style == "comprehensive"
        assert model.source_type == "research"
        assert model.word_count == 100
    
    def test_invalid_style(self):
        """Test that invalid styles raise validation errors."""
        with pytest.raises(ValidationError):
            ReportGenerationModel(
                style="invalid_style",
                prompt_template="Test template",
                draft="Draft",
                final="Final",
                source_type="research"
            )


class TestJobRequest:
    """Test JobRequest model validation."""
    
    def test_valid_job_requests(self):
        """Test creating valid job requests."""
        # Research job
        research_job = JobRequest(
            job_type="research",
            query="Test research query",
            report_style="summary"
        )
        assert research_job.job_type == "research"
        assert research_job.report_style == "summary"
        
        # YouTube job
        youtube_job = JobRequest(
            job_type="youtube",
            query="https://www.youtube.com/watch?v=test",
            report_style="comprehensive"
        )
        assert youtube_job.job_type == "youtube"
        assert youtube_job.report_style == "comprehensive"
    
    def test_invalid_job_type(self):
        """Test that invalid job types raise validation errors."""
        with pytest.raises(ValidationError):
            JobRequest(
                job_type="invalid_type",
                query="Test query"
            )


class TestAgentResponse:
    """Test AgentResponse model."""
    
    def test_successful_response(self):
        """Test creating a successful agent response."""
        response = AgentResponse(
            agent_name="TestAgent",
            success=True,
            data={"result": "test data"},
            processing_time=1.5
        )
        
        assert response.agent_name == "TestAgent"
        assert response.success is True
        assert response.data["result"] == "test data"
        assert response.processing_time == 1.5
    
    def test_error_response(self):
        """Test creating an error agent response."""
        response = AgentResponse(
            agent_name="TestAgent",
            success=False,
            error="Test error message",
            processing_time=0.5
        )
        
        assert response.success is False
        assert response.error == "Test error message"


class TestMasterOutputModel:
    """Test MasterOutputModel aggregation."""
    
    def test_complete_master_output(self):
        """Test creating a complete master output model."""
        job_request = JobRequest(
            job_type="research",
            query="Test query",
            report_style="summary"
        )
        
        youtube_data = YouTubeTranscriptModel(
            url="https://www.youtube.com/watch?v=test",
            transcript="Test transcript",
            metadata={}
        )
        
        research_data = ResearchPipelineModel(
            original_query="test",
            sub_queries=["q1", "q2", "q3"],
            results=[],
            pipeline_type="tavily",
            total_results=0
        )
        
        master_output = MasterOutputModel(
            job_request=job_request,
            orchestrator_id="test-id",
            youtube_data=youtube_data,
            research_data=research_data,
            agents_used=["YouTubeAgent", "ResearchAgent"],
            success=True,
            total_processing_time=5.0
        )
        
        assert master_output.job_request.job_type == "research"
        assert master_output.youtube_data is not None
        assert master_output.research_data is not None
        assert len(master_output.agents_used) == 2
        assert master_output.success is True


class TestStreamingUpdate:
    """Test StreamingUpdate model."""
    
    def test_streaming_updates(self):
        """Test creating different types of streaming updates."""
        # Status update
        status_update = StreamingUpdate(
            update_type="status",
            agent_name="TestAgent",
            message="Processing request"
        )
        assert status_update.update_type == "status"
        
        # Partial result update
        partial_update = StreamingUpdate(
            update_type="partial_result",
            agent_name="TestAgent",
            message="Partial results available",
            data={"partial": "data"}
        )
        assert partial_update.update_type == "partial_result"
        assert partial_update.data["partial"] == "data"
        
        # Error update
        error_update = StreamingUpdate(
            update_type="error",
            agent_name="TestAgent",
            message="An error occurred"
        )
        assert error_update.update_type == "error"
    
    def test_invalid_update_type(self):
        """Test that invalid update types raise validation errors."""
        with pytest.raises(ValidationError):
            StreamingUpdate(
                update_type="invalid_type",
                agent_name="TestAgent",
                message="Test message"
            )
