"""
Pydantic data models for the multi-agent system.
All agent I/O is strictly typed via these models.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime


class YouTubeTranscriptModel(BaseModel):
    """Model for YouTube transcript data - cleaned up model without legacy fields."""
    url: str  # Simplified from HttpUrl to avoid validation issues
    transcript: str
    metadata: Dict[str, Any]  # All video metadata (title, duration, channel, etc.) stored here
    
    # Convenience properties for backward compatibility
    @property
    def title(self) -> Optional[str]:
        """Get title from metadata."""
        return self.metadata.get('title')
    
    @property
    def duration(self) -> Optional[str]:
        """Get duration from metadata."""
        return self.metadata.get('duration')
    
    @property
    def channel(self) -> Optional[str]:
        """Get channel from metadata."""
        return self.metadata.get('channel')


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
    """Individual research result item with content cleaning support."""
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
    scraped_content: Optional[str] = None  # Full scraped content (cleaned if processing succeeded)
    # PDF extraction tracking - CRITICAL for garbage filter exemption
    is_pdf_content: Optional[bool] = None  # Whether content was extracted from PDF (exempt from garbage filtering)
    # Raw content preservation (pre-cleaning)
    raw_content: Optional[str] = None  # Exact raw scraped text before any cleaning/normalization
    raw_content_length: Optional[int] = None  # Length of raw scraped text
    # Content cleaning metadata
    content_cleaned: Optional[bool] = None  # Whether content cleaning was attempted and succeeded
    original_content_length: Optional[int] = None  # Length before cleaning
    cleaned_content_length: Optional[int] = None  # Length after cleaning
    # Garbage filtering pipeline visibility (NEW)
    pre_filter_content: Optional[str] = None  # Full content before garbage filtering (truncated after processing)
    pre_filter_content_length: Optional[int] = None  # Character count before filtering
    post_filter_content: Optional[str] = None  # Content after garbage filtering (if passed)
    post_filter_content_length: Optional[int] = None  # Character count after filtering
    garbage_filtered: Optional[bool] = None  # Whether content was identified as garbage
    filter_reason: Optional[str] = None  # Reason why content was filtered (if applicable)
    quality_score: Optional[float] = None  # Overall quality score from content filter (0-1)
    # Quality grading/scraping flags and extra info
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResearchPipelineModel(BaseModel):
    """Complete research pipeline output."""
    original_query: str
    sub_queries: List[str]  # 3 sub-questions (past, present, future)
    results: List[ResearchItem]
    pipeline_type: Literal["tavily", "serper", "combined_tavily_serper"]
    total_results: int
    processing_time: Optional[float] = None


class ReportGenerationModel(BaseModel):
    """Enhanced report generation output with quality control and multi-source support."""
    style: Literal["comprehensive", "executive", "top_10", "summary", "technical"]
    prompt_template: str
    draft: str
    final: str  # after synthesis + edit loop
    source_type: Literal["research", "youtube", "weather", "multi_source"]
    word_count: Optional[int] = None
    generation_time: Optional[float] = None
    
    # Enhanced fields for intelligent reporting
    quality_level: Optional[Literal["standard", "enhanced", "premium"]] = "standard"
    domain_context: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None  # Overall confidence in report accuracy
    data_sources_count: Optional[int] = None
    enhancement_applied: Optional[bool] = False

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


class DomainAnalysis(BaseModel):
    """Structured output for query domain analysis (LLM or heuristic)."""
    domain: Literal["technology", "business", "science", "news", "historical", "educational", "general"]
    domain_confidence: float
    complexity: Literal["low", "moderate", "high"]
    intent: Literal["informational", "instructional", "comparative", "predictive", "evaluative"]
    query_length: int
    technical_terms: int
    secondary_domains: Optional[List[Dict[str, Any]]] = None  # e.g., [{"name": "business", "confidence": 0.3}]
    rationale: Optional[str] = None


class QueryIntentAnalysis(BaseModel):
    """Structured output for query intent analysis to determine which agents are needed."""
    needs_research: bool
    needs_youtube: bool  
    needs_weather: bool
    needs_report: bool
    confidence_score: float  # 0.0-1.0 overall confidence in classification
    research_rationale: Optional[str] = None  # Why research is/isn't needed
    youtube_url: Optional[str] = None  # Extracted YouTube URL if found
    weather_location: Optional[str] = None  # Extracted location if weather is needed
    query_complexity: Literal["simple", "moderate", "complex"] = "moderate"


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
