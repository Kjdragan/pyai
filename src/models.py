"""
Pydantic data models for the multi-agent system.
All agent I/O is strictly typed via these models.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime


class YouTubeTranscriptModel(BaseModel):
    """Model for YouTube transcript data."""
    url: str  # Simplified from HttpUrl to avoid validation issues
    transcript: str
    metadata: Dict[str, Any]
    title: Optional[str] = None
    duration: Optional[str] = None
    channel: Optional[str] = None


class YouTubeMetadata(BaseModel):
    """Proper YouTube transcript metadata model matching API response."""
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    transcript_length: int
    segments_count: int
    is_translatable: bool
    available_languages: List[str]
    translation_languages: List[Dict[str, str]]
    duration_seconds: float
    first_segment_start: float
    last_segment_end: float


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
    source_url: Optional[str] = None  # Simplified from HttpUrl to avoid validation issues
    title: str
    snippet: str  # Original search result snippet (short)
    relevance_score: Optional[float] = None
    timestamp: Optional[datetime] = None
    # Enhanced scraping metadata
    content_scraped: bool = False  # Whether full content was successfully scraped
    scraping_error: Optional[str] = None  # Error message if scraping failed
    content_length: Optional[int] = None  # Length of scraped content
    scraped_content: Optional[str] = None  # Full scraped content (untruncated, for report generation)


class ResearchPipelineModel(BaseModel):
    """Complete research pipeline output."""
    original_query: str
    sub_queries: List[str]  # 3 sub-questions (past, present, future)
    results: List[ResearchItem]
    pipeline_type: Literal["tavily", "serper", "combined_tavily_serper"]
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

class UniversalReportData(BaseModel):
    """Universal data container for report generation - can handle any combination of data sources."""
    query: str  # Original user query
    
    # Optional data sources
    youtube_data: Optional[YouTubeTranscriptModel] = None
    research_data: Optional[ResearchPipelineModel] = None
    weather_data: Optional[WeatherModel] = None
    
    def has_data(self) -> bool:
        """Check if any data sources are available."""
        return any([self.youtube_data, self.research_data, self.weather_data])
    
    def get_data_types(self) -> List[str]:
        """Get list of available data types."""
        types = []
        if self.youtube_data: types.append("youtube")
        if self.research_data: types.append("research") 
        if self.weather_data: types.append("weather")
        return types
    
    def get_primary_content(self) -> str:
        """Get the main content for analysis."""
        if self.youtube_data and self.youtube_data.transcript:
            return f"YouTube Video: {self.youtube_data.title or 'Unknown Title'}\n\nTranscript:\n{self.youtube_data.transcript}"
        elif self.research_data and self.research_data.results:
            content = f"Research Results for: {self.research_data.original_query}\n\n"
            for result in self.research_data.results[:5]:  # Top 5 results
                content += f"• {result.title}: {result.snippet}\n"
            return content
        elif self.weather_data:
            return f"Weather data for query: {self.query}"
        else:
            return f"General information about: {self.query}"


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


# ============================================================================
# TRACE ANALYSIS MODELS - For automated performance analytics
# ============================================================================

class PerformanceMetric(BaseModel):
    """Individual performance metric from trace analysis."""
    metric_name: str
    value: float
    unit: str
    context: Optional[str] = None
    threshold_status: Optional[Literal["good", "warning", "critical"]] = None


class AgentPerformanceAnalysis(BaseModel):
    """Performance analysis for a specific agent."""
    agent_name: str
    total_calls: int
    success_rate: float
    average_response_time: float
    total_processing_time: float
    error_count: int
    common_errors: List[str] = Field(default_factory=list)
    performance_rating: Literal["excellent", "good", "needs_improvement", "critical"]


class CostAnalysis(BaseModel):
    """Token usage and cost analysis from traces."""
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    cost_by_model: Dict[str, float] = Field(default_factory=dict)
    cost_by_agent: Dict[str, float] = Field(default_factory=dict)
    optimization_opportunities: List[str] = Field(default_factory=list)


class TraceAnalysisInsights(BaseModel):
    """LLM-generated insights from trace analysis."""
    critical_issues: List[str] = Field(default_factory=list)
    optimization_recommendations: List[str] = Field(default_factory=list)
    performance_trends: List[str] = Field(default_factory=list)
    cost_optimization_suggestions: List[str] = Field(default_factory=list)
    reliability_assessment: str
    overall_system_health: Literal["excellent", "good", "concerning", "critical"]


class TraceAnalysisReport(BaseModel):
    """Complete trace analysis report model."""
    analysis_type: Literal["performance", "cost", "error", "comprehensive", "comparison"]
    time_range: str
    total_traces_analyzed: int
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    
    # Core metrics
    performance_metrics: List[PerformanceMetric] = Field(default_factory=list)
    agent_analysis: List[AgentPerformanceAnalysis] = Field(default_factory=list)
    cost_analysis: Optional[CostAnalysis] = None
    
    # LLM-generated insights
    insights: TraceAnalysisInsights
    
    # Summary data
    total_execution_time: float
    average_job_time: float
    success_rate: float
    total_api_calls: int
    
    # Recommendations
    immediate_actions: List[str] = Field(default_factory=list)
    strategic_improvements: List[str] = Field(default_factory=list)
    
    # Report metadata
    generated_by: str = "TraceAnalyzer Agent"
    report_version: str = "1.0"


class TraceQuery(BaseModel):
    """Query parameters for trace analysis."""
    time_range_minutes: int = 60  # Last N minutes
    max_traces: int = 100
    include_successful: bool = True
    include_failed: bool = True
    agent_filter: Optional[str] = None  # Filter by specific agent
    analysis_focus: Literal["performance", "cost", "errors", "all"] = "all"
