"""
Pydantic data models for the multi-agent system.
All agent I/O is strictly typed via these models.
"""

from pydantic import BaseModel, HttpUrl, Field
from typing import List, Dict, Optional, Literal
from datetime import datetime


class YouTubeTranscriptModel(BaseModel):
    """Model for YouTube transcript data."""
    url: HttpUrl
    transcript: str
    metadata: Dict[str, str]
    title: Optional[str] = None
    duration: Optional[str] = None
    channel: Optional[str] = None


class WeatherData(BaseModel):
    """Individual weather data point."""
    timestamp: str
    temp: float
    description: str
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None


class WeatherModel(BaseModel):
    """Complete weather information."""
    location: str
    current: WeatherData
    forecast: List[WeatherData]
    units: str = "metric"


class ResearchItem(BaseModel):
    """Individual research result item."""
    query_variant: str  # e.g. "Historical adoption of X"
    source_url: Optional[HttpUrl] = None
    title: str
    snippet: str
    relevance_score: Optional[float] = None
    timestamp: Optional[datetime] = None


class ResearchPipelineModel(BaseModel):
    """Complete research pipeline output."""
    original_query: str
    sub_queries: List[str]  # 3 sub-questions (past, present, future)
    results: List[ResearchItem]
    pipeline_type: Literal["tavily", "duckduckgo"]
    total_results: int
    processing_time: Optional[float] = None


class ReportGenerationModel(BaseModel):
    """Report generation output."""
    style: Literal["comprehensive", "top_10", "summary"]
    prompt_template: str
    draft: str
    final: str  # after synthesis + edit loop
    source_type: Literal["research", "youtube"]
    word_count: Optional[int] = None
    generation_time: Optional[float] = None


class JobRequest(BaseModel):
    """User job request model."""
    job_type: Literal["youtube", "weather", "research", "report"]
    query: str
    parameters: Optional[Dict[str, str]] = None
    report_style: Optional[Literal["comprehensive", "top_10", "summary"]] = "summary"


class AgentResponse(BaseModel):
    """Generic agent response wrapper."""
    agent_name: str
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None


class MasterOutputModel(BaseModel):
    """Master output model aggregating all agent results."""
    job_request: JobRequest
    orchestrator_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Agent outputs (optional based on job type)
    youtube_data: Optional[YouTubeTranscriptModel] = None
    weather_data: Optional[WeatherModel] = None
    research_data: Optional[ResearchPipelineModel] = None
    report_data: Optional[ReportGenerationModel] = None
    
    # Metadata
    total_processing_time: Optional[float] = None
    agents_used: List[str] = Field(default_factory=list)
    success: bool = True
    errors: List[str] = Field(default_factory=list)


class StreamingUpdate(BaseModel):
    """Model for streaming updates to the UI."""
    update_type: Literal["status", "partial_result", "final_result", "error"]
    agent_name: str
    message: str
    data: Optional[Dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)
