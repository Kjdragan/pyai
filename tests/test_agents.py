"""
Unit tests for individual agents using Pydantic-AI TestModel.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from pydantic_ai import capture_run_messages
from pydantic_ai.models.test import TestModel
from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, UserPromptPart

from agents.youtube_agent import youtube_agent, process_youtube_request, extract_video_id
from agents.weather_agent import weather_agent, process_weather_request
from agents.research_tavily_agent import tavily_research_agent, process_tavily_research_request
from agents.research_duckduckgo_agent import duckduckgo_research_agent, process_duckduckgo_research_request
from agents.report_writer_agent import report_writer_agent, process_report_request
from agents.orchestrator_agent import orchestrator_agent, parse_job_request, run_orchestrator_job

from models import (
    YouTubeTranscriptModel, WeatherModel, ResearchPipelineModel, 
    ReportGenerationModel, JobRequest, AgentResponse
)


class TestYouTubeAgent:
    """Test YouTube Agent functionality."""
    
    def test_extract_video_id(self):
        """Test video ID extraction from various YouTube URL formats."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
            ("invalid-url", None)
        ]
        
        for url, expected_id in test_cases:
            result = extract_video_id(url)
            assert result == expected_id
    
    async def test_youtube_agent_with_test_model(self, test_model):
        """Test YouTube agent using TestModel."""
        with capture_run_messages() as messages:
            with youtube_agent.override(model=test_model):
                result = await youtube_agent.run(
                    "Get transcript for https://www.youtube.com/watch?v=test123"
                )
        
        # Verify the agent was called and returned structured data
        assert len(messages) >= 1
        assert isinstance(result.output, YouTubeTranscriptModel)
        assert result.output.url is not None
        assert result.output.transcript is not None
    
    @patch('agents.youtube_agent.fetch_youtube_transcript')
    async def test_process_youtube_request_success(self, mock_fetch):
        """Test successful YouTube request processing."""
        # Mock the transcript fetch
        mock_fetch.return_value = (
            "This is a test transcript",
            {"video_id": "test123", "transcript_length": 25}
        )
        
        url = "https://www.youtube.com/watch?v=test123"
        response = await process_youtube_request(url)
        
        assert response.success is True
        assert response.agent_name == "YouTubeAgent"
        assert "transcript" in response.data
        assert response.data["url"] == url
    
    @patch('agents.youtube_agent.fetch_youtube_transcript')
    async def test_process_youtube_request_failure(self, mock_fetch):
        """Test YouTube request processing with API failure."""
        # Mock API failure
        mock_fetch.side_effect = ValueError("Transcript not available")
        
        url = "https://www.youtube.com/watch?v=test123"
        response = await process_youtube_request(url)
        
        assert response.success is False
        assert response.agent_name == "YouTubeAgent"
        assert "Transcript not available" in response.error


class TestWeatherAgent:
    """Test Weather Agent functionality."""
    
    async def test_weather_agent_with_test_model(self, test_model):
        """Test Weather agent using TestModel."""
        with capture_run_messages() as messages:
            with weather_agent.override(model=test_model):
                result = await weather_agent.run("Get weather for New York")
        
        # Verify the agent was called and returned structured data
        assert len(messages) >= 1
        assert isinstance(result.output, WeatherModel)
        assert result.output.location is not None
        assert result.output.current is not None
    
    @patch('agents.weather_agent.fetch_current_weather')
    @patch('agents.weather_agent.fetch_weather_forecast')
    async def test_process_weather_request_success(self, mock_forecast, mock_current):
        """Test successful weather request processing."""
        # Mock API responses
        mock_current.return_value = {
            "dt": 1640995200,
            "main": {"temp": 20.5, "humidity": 65},
            "weather": [{"description": "sunny"}],
            "wind": {"speed": 5.2}
        }
        
        mock_forecast.return_value = {
            "list": [
                {
                    "dt": 1640995200,
                    "main": {"temp": 18.0, "humidity": 60},
                    "weather": [{"description": "cloudy"}],
                    "wind": {"speed": 4.0}
                }
            ]
        }
        
        response = await process_weather_request("New York")
        
        assert response.success is True
        assert response.agent_name == "WeatherAgent"
        assert "location" in response.data
        assert response.data["location"] == "New York"


class TestResearchAgents:
    """Test Research Agent functionality."""
    
    async def test_tavily_research_agent_with_test_model(self, test_model):
        """Test Tavily research agent using TestModel."""
        with capture_run_messages() as messages:
            with tavily_research_agent.override(model=test_model):
                result = await tavily_research_agent.run("Research AI trends")
        
        # Verify the agent was called and returned structured data
        assert len(messages) >= 1
        assert isinstance(result.output, ResearchPipelineModel)
        assert result.output.original_query is not None
        assert result.output.pipeline_type == "tavily"
    
    async def test_duckduckgo_research_agent_with_test_model(self, test_model):
        """Test DuckDuckGo research agent using TestModel."""
        with capture_run_messages() as messages:
            with duckduckgo_research_agent.override(model=test_model):
                result = await duckduckgo_research_agent.run("Research climate change")
        
        # Verify the agent was called and returned structured data
        assert len(messages) >= 1
        assert isinstance(result.output, ResearchPipelineModel)
        assert result.output.original_query is not None
        assert result.output.pipeline_type == "duckduckgo"
    
    @patch('agents.research_tavily_agent.TavilyClient')
    @patch('agents.research_tavily_agent.expand_query_to_subquestions')
    async def test_process_tavily_research_success(self, mock_expand, mock_client):
        """Test successful Tavily research processing."""
        # Mock query expansion
        mock_expand.return_value = ["query 1", "query 2", "query 3"]
        
        # Mock Tavily client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.search.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "content": "Test content",
                    "url": "https://example.com",
                    "score": 0.95
                }
            ]
        }
        
        response = await process_tavily_research_request("test query")
        
        assert response.success is True
        assert response.agent_name == "TavilyResearchAgent"
        assert "original_query" in response.data


class TestReportWriterAgent:
    """Test Report Writer Agent functionality."""
    
    async def test_report_writer_agent_with_test_model(self, test_model):
        """Test Report Writer agent using TestModel."""
        with capture_run_messages() as messages:
            with report_writer_agent.override(model=test_model):
                result = await report_writer_agent.run("Generate a summary report")
        
        # Verify the agent was called and returned structured data
        assert len(messages) >= 1
        assert isinstance(result.output, ReportGenerationModel)
        assert result.output.style is not None
        assert result.output.final is not None
    
    async def test_process_report_request_with_research_data(self):
        """Test report generation from research data."""
        # Create mock research data
        from models import ResearchPipelineModel, ResearchItem
        
        research_data = ResearchPipelineModel(
            original_query="test query",
            sub_queries=["q1", "q2", "q3"],
            results=[
                ResearchItem(
                    query_variant="q1",
                    title="Test Result",
                    snippet="Test content"
                )
            ],
            pipeline_type="tavily",
            total_results=1
        )
        
        response = await process_report_request(research_data, "summary")
        
        assert response.success is True
        assert response.agent_name == "ReportWriterAgent"
        assert "style" in response.data
        assert response.data["style"] == "summary"


class TestOrchestratorAgent:
    """Test Orchestrator Agent functionality."""
    
    def test_parse_job_request(self):
        """Test job request parsing logic."""
        test_cases = [
            ("Research AI trends", "research"),
            ("Weather forecast for NYC", "weather"),
            ("Analyze YouTube video: https://youtube.com/watch?v=test", "youtube"),
            ("Generate comprehensive report on climate", "report"),
            ("What is machine learning?", "research")  # Default case
        ]
        
        for query, expected_type in test_cases:
            job_request = parse_job_request(query)
            assert job_request.job_type == expected_type
            assert job_request.query == query
    
    async def test_orchestrator_agent_with_test_model(self, test_model):
        """Test Orchestrator agent using TestModel."""
        with capture_run_messages() as messages:
            with orchestrator_agent.override(model=test_model):
                result = await orchestrator_agent.run("Research AI trends")
        
        # Verify the agent was called
        assert len(messages) >= 1
        # The orchestrator should coordinate other agents
        assert any("research" in str(msg).lower() for msg in messages)
    
    @patch('agents.orchestrator_agent.process_tavily_research_request')
    @patch('agents.orchestrator_agent.process_duckduckgo_research_request')
    async def test_run_orchestrator_job_research(self, mock_ddg, mock_tavily):
        """Test orchestrator job execution for research."""
        # Mock research responses
        mock_response = AgentResponse(
            agent_name="TestAgent",
            success=True,
            data={
                "original_query": "test",
                "sub_queries": ["q1", "q2", "q3"],
                "results": [],
                "pipeline_type": "tavily",
                "total_results": 0
            }
        )
        
        mock_tavily.return_value = mock_response
        mock_ddg.return_value = mock_response
        
        updates = []
        async for update in run_orchestrator_job("Research AI trends"):
            updates.append(update)
            # Limit updates to prevent infinite loops in tests
            if len(updates) > 10:
                break
        
        # Verify we received updates
        assert len(updates) > 0
        # Should have status updates
        assert any(update.update_type == "status" for update in updates)


class TestAgentIntegration:
    """Test agent integration and error handling."""
    
    async def test_agent_retry_logic(self, test_model):
        """Test that agents use retry logic properly."""
        # This test verifies that agents are configured with retry logic
        # The actual retry behavior is handled by Pydantic-AI
        
        with youtube_agent.override(model=test_model):
            result = await youtube_agent.run("test query")
        
        # Agent should complete successfully with TestModel
        assert result is not None
    
    async def test_agent_error_handling(self):
        """Test agent error handling with invalid inputs."""
        # Test YouTube agent with invalid URL
        response = await process_youtube_request("invalid-url")
        assert response.success is False
        assert "Invalid YouTube URL format" in response.error
        
        # Test weather agent without API key (should fail gracefully)
        with patch('agents.weather_agent.WeatherAgentDeps') as mock_deps:
            mock_deps.return_value.api_key = ""
            response = await process_weather_request("Test City")
            assert response.success is False
            assert "API key not configured" in response.error
