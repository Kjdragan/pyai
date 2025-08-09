import json
import tempfile
from pathlib import Path

import pytest

from src.state_manager import MasterStateManager
from models import (
    JobRequest,
    YouTubeTranscriptModel,
    WeatherData,
    WeatherModel,
    ResearchPipelineModel,
)


@pytest.fixture()
def temp_state_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRequest(job_type="research", query="test query")
        mgr = MasterStateManager(orchestrator_id="test-orch", job_request=job, log_dir=tmpdir)
        yield mgr


def test_update_youtube_data_coerces_dict(temp_state_manager: MasterStateManager):
    mgr = temp_state_manager
    payload = {
        "url": "https://www.youtube.com/watch?v=abc123def45",
        "transcript": "hello world",
        "metadata": {"title": "Demo", "duration": "5:00", "channel": "Test"},
    }

    mgr.update_youtube_data("YouTubeAgent", payload)

    yt = mgr.get_youtube_data()
    assert isinstance(yt, YouTubeTranscriptModel)
    assert yt.url.endswith("abc123def45")
    assert yt.transcript == "hello world"
    assert yt.title == "Demo"


def test_update_research_data_coerces_json_string(temp_state_manager: MasterStateManager):
    mgr = temp_state_manager

    research_dict = {
        "original_query": "ai trends",
        "sub_queries": ["past", "present", "future"],
        "results": [
            {
                "query_variant": "present",
                "source_url": "https://example.com/ai",
                "title": "AI Today",
                "snippet": "State of AI",
            }
        ],
        "pipeline_type": "tavily",
        "total_results": 1,
    }
    research_json = json.dumps(research_dict)

    mgr.update_research_data("TavilyResearchAgent", research_json)

    rp = mgr.get_research_data()
    assert isinstance(rp, ResearchPipelineModel)
    assert rp.original_query == "ai trends"
    assert rp.total_results == 1
    assert len(rp.results) == 1
    assert rp.results[0].title == "AI Today"


def test_update_weather_data_passthrough_model(temp_state_manager: MasterStateManager):
    mgr = temp_state_manager

    current = WeatherData(timestamp="2025-01-01T00:00:00Z", temp=20.0, description="Clear")
    forecast = [
        WeatherData(timestamp="2025-01-01T03:00:00Z", temp=19.0, description="Clear"),
        WeatherData(timestamp="2025-01-01T06:00:00Z", temp=18.0, description="Cloudy"),
    ]
    weather_model = WeatherModel(location="NYC", current=current, forecast=forecast, units="metric")

    mgr.update_weather_data("WeatherAgent", weather_model)

    w = mgr.get_weather_data()
    assert isinstance(w, WeatherModel)
    assert w.location == "NYC"
    assert len(w.forecast) == 2


def test_update_report_data_invalid_records_error(temp_state_manager: MasterStateManager):
    mgr = temp_state_manager

    # Invalid type (e.g., integer) should be handled gracefully and recorded as error
    mgr.update_report_data("ReportAgent", 12345)  # type: ignore[arg-type]

    ms = mgr.get_master_state()
    assert ms.report_data is None
    assert ms.success is False
    assert any("Report data type error" in e for e in ms.errors)
