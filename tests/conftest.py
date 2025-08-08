"""
Pytest configuration and fixtures for the Pydantic-AI Multi-Agent System tests.
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import pydantic-ai testing utilities
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

# Enable real model requests for integration and agent tests
models.ALLOW_MODEL_REQUESTS = True

# Mark all tests as async by default
pytestmark = pytest.mark.anyio


@pytest.fixture
def test_model():
    """Provide a TestModel instance for testing."""
    return TestModel()


@pytest.fixture
def mock_youtube_api():
    """Mock YouTube API responses."""
    mock = MagicMock()
    mock.get_transcript.return_value = [
        {"text": "This is a test transcript", "start": 0.0, "duration": 5.0},
        {"text": "with multiple segments", "start": 5.0, "duration": 3.0}
    ]
    return mock


@pytest.fixture
def mock_weather_api():
    """Mock OpenWeather API responses."""
    return {
        "current": {
            "dt": 1640995200,
            "main": {"temp": 20.5, "humidity": 65},
            "weather": [{"description": "partly cloudy"}],
            "wind": {"speed": 5.2}
        },
        "forecast": {
            "list": [
                {
                    "dt": 1640995200 + i * 86400,
                    "main": {"temp": 18.0 + i, "humidity": 60 + i},
                    "weather": [{"description": f"day {i} weather"}],
                    "wind": {"speed": 4.0 + i}
                }
                for i in range(7)
            ]
        }
    }


@pytest.fixture
def mock_tavily_api():
    """Mock Tavily API responses."""
    return {
        "results": [
            {
                "title": "Test Research Result 1",
                "content": "This is test content for research result 1",
                "url": "https://example.com/1",
                "score": 0.95
            },
            {
                "title": "Test Research Result 2", 
                "content": "This is test content for research result 2",
                "url": "https://example.com/2",
                "score": 0.87
            }
        ]
    }


@pytest.fixture
def mock_serper_api():
    """Mock Serper API responses."""
    return {
        "organic": [
            {
                "title": "Test Search Result 1",
                "link": "https://example.com/result1",
                "snippet": "This is a test search result snippet with relevant information."
            },
            {
                "title": "Test Search Result 2", 
                "link": "https://example.com/result2",
                "snippet": "Another test search result with different content and details."
            }
        ],
        "searchParameters": {
            "q": "test query",
            "num": 10,
            "hl": "en",
            "gl": "us"
        }
    }


@pytest.fixture
def sample_job_requests():
    """Sample job requests for testing."""
    from models import JobRequest
    
    return [
        JobRequest(
            job_type="research",
            query="Test research query",
            report_style="summary"
        ),
        JobRequest(
            job_type="youtube",
            query="https://www.youtube.com/watch?v=test123",
            report_style="comprehensive"
        ),
        JobRequest(
            job_type="weather",
            query="Weather forecast for Test City",
            report_style="summary"
        ),
        JobRequest(
            job_type="report",
            query="Generate report on test topic",
            report_style="top_10"
        )
    ]


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    class MockConfig:
        OPENAI_API_KEY = "test-key"
        DEFAULT_MODEL = "test-model"
        ORCHESTRATOR_MODEL = "test-orchestrator-model"
        MAX_RETRIES = 2
        REQUEST_TIMEOUT = 10
        MAX_RESEARCH_RESULTS = 5
        RESEARCH_TIMEOUT = 30
        
        @classmethod
        def validate_required_keys(cls):
            return []  # No missing keys in tests
        
        @classmethod
        def get_model_settings(cls):
            return {
                "max_retries": cls.MAX_RETRIES,
                "timeout": cls.REQUEST_TIMEOUT,
            }
    
    return MockConfig()


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, mock_config):
    """Automatically set up test environment for all tests."""
    # Mock the config module
    import config
    for attr in dir(mock_config):
        if not attr.startswith('_'):
            monkeypatch.setattr(config.config, attr, getattr(mock_config, attr))


# Async test utilities
@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Force AnyIO to use asyncio backend to avoid trio dependency for tests
@pytest.fixture
def anyio_backend():
    return "asyncio"
