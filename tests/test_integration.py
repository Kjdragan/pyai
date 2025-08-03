"""
Integration tests for the Pydantic-AI Multi-Agent System.
Tests end-to-end workflows and agent coordination.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from pydantic_ai import capture_run_messages
from pydantic_ai.models.test import TestModel

from agents.orchestrator_agent import run_orchestrator_job, parse_job_request
from agents import (
    process_youtube_request, process_weather_request,
    process_tavily_research_request, process_duckduckgo_research_request,
    process_report_request
)
from models import (
    JobRequest, MasterOutputModel, StreamingUpdate,
    YouTubeTranscriptModel, WeatherModel, ResearchPipelineModel,
    ReportGenerationModel, ResearchItem
)


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @patch('agents.orchestrator_agent.process_tavily_research_request')
    @patch('agents.orchestrator_agent.process_duckduckgo_research_request')
    @patch('agents.orchestrator_agent.process_report_request')
    async def test_research_to_report_workflow(self, mock_report, mock_ddg, mock_tavily):
        """Test complete research-to-report workflow."""
        # Mock research pipeline responses
        research_data = {
            "original_query": "AI trends 2024",
            "sub_queries": ["AI history", "Current AI state", "Future AI trends"],
            "results": [
                {
                    "query_variant": "AI history",
                    "title": "History of AI",
                    "snippet": "AI development timeline",
                    "relevance_score": 0.9
                }
            ],
            "pipeline_type": "tavily",
            "total_results": 1,
            "processing_time": 2.5
        }
        
        from models import AgentResponse
        mock_tavily.return_value = AgentResponse(
            agent_name="TavilyResearchAgent",
            success=True,
            data=research_data,
            processing_time=2.5
        )
        
        mock_ddg.return_value = AgentResponse(
            agent_name="DuckDuckGoResearchAgent", 
            success=True,
            data=research_data,
            processing_time=2.0
        )
        
        # Mock report generation
        report_data = {
            "style": "summary",
            "prompt_template": "Test template",
            "draft": "Draft report content",
            "final": "Final report content",
            "source_type": "research",
            "word_count": 150,
            "generation_time": 3.0
        }
        
        mock_report.return_value = AgentResponse(
            agent_name="ReportWriterAgent",
            success=True,
            data=report_data,
            processing_time=3.0
        )
        
        # Execute workflow
        updates = []
        final_result = None
        
        async for update in run_orchestrator_job("Research AI trends 2024"):
            updates.append(update)
            if update.update_type == "final_result":
                final_result = update.data
                break
        
        # Verify workflow completion
        assert len(updates) > 0
        assert final_result is not None
        assert final_result["success"] is True
        assert "research_data" in final_result
        assert "report_data" in final_result
        
        # Verify agent calls
        mock_tavily.assert_called_once()
        mock_report.assert_called_once()
    
    @patch('agents.orchestrator_agent.process_youtube_request')
    @patch('agents.orchestrator_agent.process_report_request')
    async def test_youtube_to_report_workflow(self, mock_report, mock_youtube):
        """Test YouTube analysis to report workflow."""
        # Mock YouTube response
        youtube_data = {
            "url": "https://www.youtube.com/watch?v=test123",
            "transcript": "This is a test video transcript about AI",
            "metadata": {"video_id": "test123", "duration": "10:30"},
            "title": "AI Explained",
            "channel": "Tech Channel"
        }
        
        from models import AgentResponse
        mock_youtube.return_value = AgentResponse(
            agent_name="YouTubeAgent",
            success=True,
            data=youtube_data,
            processing_time=1.5
        )
        
        # Mock report generation
        report_data = {
            "style": "comprehensive",
            "prompt_template": "YouTube analysis template",
            "draft": "Draft YouTube analysis",
            "final": "Final YouTube analysis report",
            "source_type": "youtube",
            "word_count": 500,
            "generation_time": 4.0
        }
        
        mock_report.return_value = AgentResponse(
            agent_name="ReportWriterAgent",
            success=True,
            data=report_data,
            processing_time=4.0
        )
        
        # Execute workflow
        updates = []
        final_result = None
        
        async for update in run_orchestrator_job("Analyze YouTube video: https://www.youtube.com/watch?v=test123"):
            updates.append(update)
            if update.update_type == "final_result":
                final_result = update.data
                break
        
        # Verify workflow completion
        assert final_result is not None
        assert final_result["success"] is True
        assert "youtube_data" in final_result
        assert "report_data" in final_result
        
        # Verify correct agents were called
        mock_youtube.assert_called_once()
        mock_report.assert_called_once()
    
    @patch('agents.orchestrator_agent.process_weather_request')
    async def test_weather_workflow(self, mock_weather):
        """Test weather information workflow."""
        # Mock weather response
        weather_data = {
            "location": "New York",
            "current": {
                "timestamp": "2024-01-01T12:00:00",
                "temp": 20.5,
                "description": "sunny",
                "humidity": 65.0,
                "wind_speed": 5.2
            },
            "forecast": [
                {
                    "timestamp": "2024-01-02T12:00:00",
                    "temp": 18.0,
                    "description": "cloudy",
                    "humidity": 70.0,
                    "wind_speed": 4.0
                }
            ],
            "units": "metric"
        }
        
        from models import AgentResponse
        mock_weather.return_value = AgentResponse(
            agent_name="WeatherAgent",
            success=True,
            data=weather_data,
            processing_time=1.0
        )
        
        # Execute workflow
        updates = []
        final_result = None
        
        async for update in run_orchestrator_job("Weather forecast for New York"):
            updates.append(update)
            if update.update_type == "final_result":
                final_result = update.data
                break
        
        # Verify workflow completion
        assert final_result is not None
        assert final_result["success"] is True
        assert "weather_data" in final_result
        assert final_result["weather_data"]["location"] == "New York"
        
        # Verify weather agent was called
        mock_weather.assert_called_once()


class TestErrorHandlingIntegration:
    """Test error handling in integrated workflows."""
    
    @patch('agents.orchestrator_agent.process_tavily_research_request')
    @patch('agents.orchestrator_agent.process_duckduckgo_research_request')
    async def test_research_pipeline_fallback(self, mock_ddg, mock_tavily):
        """Test fallback between research pipelines when one fails."""
        # Mock Tavily failure
        from models import AgentResponse
        mock_tavily.return_value = AgentResponse(
            agent_name="TavilyResearchAgent",
            success=False,
            error="API key not configured",
            processing_time=0.5
        )
        
        # Mock DuckDuckGo success
        research_data = {
            "original_query": "test query",
            "sub_queries": ["q1", "q2", "q3"],
            "results": [],
            "pipeline_type": "duckduckgo",
            "total_results": 0,
            "processing_time": 2.0
        }
        
        mock_ddg.return_value = AgentResponse(
            agent_name="DuckDuckGoResearchAgent",
            success=True,
            data=research_data,
            processing_time=2.0
        )
        
        # Execute workflow
        updates = []
        error_updates = []
        final_result = None
        
        async for update in run_orchestrator_job("Research test topic"):
            updates.append(update)
            if update.update_type == "error":
                error_updates.append(update)
            elif update.update_type == "final_result":
                final_result = update.data
                break
        
        # Verify fallback behavior
        assert len(error_updates) > 0  # Should have error from Tavily
        assert final_result is not None
        assert "research_data" in final_result  # Should have DuckDuckGo results
        
        # Both agents should have been called
        mock_tavily.assert_called_once()
        mock_ddg.assert_called_once()
    
    async def test_complete_workflow_failure(self):
        """Test handling when all agents fail."""
        # This test simulates a complete system failure
        with patch('agents.orchestrator_agent.process_tavily_research_request') as mock_tavily:
            with patch('agents.orchestrator_agent.process_duckduckgo_research_request') as mock_ddg:
                # Mock both research pipelines failing
                from models import AgentResponse
                
                mock_tavily.return_value = AgentResponse(
                    agent_name="TavilyResearchAgent",
                    success=False,
                    error="Network error",
                    processing_time=0.1
                )
                
                mock_ddg.return_value = AgentResponse(
                    agent_name="DuckDuckGoResearchAgent",
                    success=False,
                    error="Service unavailable",
                    processing_time=0.1
                )
                
                # Execute workflow
                updates = []
                error_count = 0
                final_result = None
                
                async for update in run_orchestrator_job("Research test topic"):
                    updates.append(update)
                    if update.update_type == "error":
                        error_count += 1
                    elif update.update_type == "final_result":
                        final_result = update.data
                        break
                
                # Verify error handling
                assert error_count > 0
                assert final_result is not None
                assert final_result["success"] is False
                assert len(final_result["errors"]) > 0


class TestStreamingBehavior:
    """Test streaming update behavior."""
    
    @patch('agents.orchestrator_agent.process_weather_request')
    async def test_streaming_updates_order(self, mock_weather):
        """Test that streaming updates are sent in correct order."""
        # Mock weather response with delay to test streaming
        async def delayed_weather_response(location):
            await asyncio.sleep(0.1)  # Small delay
            from models import AgentResponse
            return AgentResponse(
                agent_name="WeatherAgent",
                success=True,
                data={"location": location, "current": {}, "forecast": []},
                processing_time=0.1
            )
        
        mock_weather.side_effect = delayed_weather_response
        
        # Collect all updates
        updates = []
        update_types = []
        
        async for update in run_orchestrator_job("Weather for Test City"):
            updates.append(update)
            update_types.append(update.update_type)
            if update.update_type == "final_result":
                break
        
        # Verify update order
        assert len(updates) > 0
        assert update_types[0] == "status"  # Should start with status
        assert update_types[-1] == "final_result"  # Should end with final result
        
        # Should have status updates before results
        status_indices = [i for i, t in enumerate(update_types) if t == "status"]
        result_indices = [i for i, t in enumerate(update_types) if t in ["partial_result", "final_result"]]
        
        if status_indices and result_indices:
            assert min(status_indices) < min(result_indices)
    
    async def test_streaming_update_content(self):
        """Test that streaming updates contain expected content."""
        updates = []
        
        # Collect a few updates
        async for update in run_orchestrator_job("Research AI"):
            updates.append(update)
            if len(updates) >= 3:  # Just collect first few updates
                break
        
        # Verify update structure
        for update in updates:
            assert hasattr(update, 'update_type')
            assert hasattr(update, 'agent_name')
            assert hasattr(update, 'message')
            assert hasattr(update, 'timestamp')
            
            # Verify update types are valid
            assert update.update_type in ["status", "partial_result", "final_result", "error"]
            
            # Verify agent names are strings
            assert isinstance(update.agent_name, str)
            assert len(update.agent_name) > 0
            
            # Verify messages are meaningful
            assert isinstance(update.message, str)
            assert len(update.message) > 0


class TestJobRequestParsing:
    """Test job request parsing and routing."""
    
    def test_job_type_detection(self):
        """Test that job types are correctly detected from queries."""
        test_cases = [
            # Research queries
            ("Research climate change", "research"),
            ("Find information about AI", "research"),
            ("Investigate blockchain technology", "research"),
            
            # YouTube queries
            ("Analyze YouTube video: https://youtube.com/watch?v=123", "youtube"),
            ("Get transcript from this video: https://youtu.be/abc", "youtube"),
            ("YouTube video analysis", "youtube"),
            
            # Weather queries
            ("Weather forecast for London", "weather"),
            ("What's the temperature in Tokyo?", "weather"),
            ("Current weather conditions", "weather"),
            
            # Report queries
            ("Generate report on renewable energy", "report"),
            ("Write a summary of the data", "report"),
            ("Create comprehensive analysis", "report"),
            
            # Default case
            ("What is machine learning?", "research")
        ]
        
        for query, expected_type in test_cases:
            job_request = parse_job_request(query)
            assert job_request.job_type == expected_type, f"Query '{query}' should be type '{expected_type}', got '{job_request.job_type}'"
    
    def test_report_style_detection(self):
        """Test that report styles are correctly detected."""
        test_cases = [
            ("Generate comprehensive report on AI", "comprehensive"),
            ("Create top 10 insights about climate", "top_10"),
            ("Write a summary of the research", "summary"),
            ("Analyze the data", "summary")  # Default
        ]
        
        for query, expected_style in test_cases:
            job_request = parse_job_request(query)
            assert job_request.report_style == expected_style, f"Query '{query}' should have style '{expected_style}', got '{job_request.report_style}'"


class TestSystemResilience:
    """Test system resilience and recovery."""
    
    async def test_partial_agent_failure_recovery(self):
        """Test system continues when some agents fail."""
        with patch('agents.orchestrator_agent.process_youtube_request') as mock_youtube:
            with patch('agents.orchestrator_agent.process_report_request') as mock_report:
                # Mock YouTube failure
                from models import AgentResponse
                mock_youtube.return_value = AgentResponse(
                    agent_name="YouTubeAgent",
                    success=False,
                    error="Video not found",
                    processing_time=0.1
                )
                
                # Mock report success (should still work without YouTube data)
                mock_report.return_value = AgentResponse(
                    agent_name="ReportWriterAgent",
                    success=True,
                    data={
                        "style": "summary",
                        "final": "Generated report without video data",
                        "source_type": "research"
                    },
                    processing_time=1.0
                )
                
                # Execute workflow
                updates = []
                final_result = None
                
                async for update in run_orchestrator_job("Analyze YouTube video and create report"):
                    updates.append(update)
                    if update.update_type == "final_result":
                        final_result = update.data
                        break
                
                # System should continue despite YouTube failure
                assert final_result is not None
                assert len(final_result["errors"]) > 0  # Should record YouTube error
                assert "report_data" in final_result  # Should still generate report
