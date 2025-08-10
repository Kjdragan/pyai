"""
Configuration settings for the multi-agent system.
"""

import os
from pathlib import Path
from typing import Optional
try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback no-op if python-dotenv is not installed
    def load_dotenv(*args, **kwargs):  # type: ignore
        return False

# Load environment variables - check parent directory for .env file
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to current directory
    load_dotenv()


class Config:
    """Configuration class for the multi-agent system."""

    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
    YOUTUBE_DATA_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

    # Model configurations - Smart model selection for cost/performance optimization
    # Fast/Cheap model for simple tasks
    NANO_MODEL: str = "gpt-5-nano-2025-08-07"
    # Intelligent model for complex reasoning
    STANDARD_MODEL: str = "gpt-5-mini-2025-08-07"

    # Agent-specific model assignments (respects environment variables)
    DEFAULT_MODEL: str = os.getenv('DEFAULT_MODEL', 'gpt-5-mini-2025-08-07')  # Default to efficient model
    ORCHESTRATOR_MODEL: str = os.getenv('ORCHESTRATOR_MODEL', STANDARD_MODEL)  # Complex coordination
    RESEARCH_MODEL: str = os.getenv('RESEARCH_MODEL', 'gpt-5-mini-2025-08-07')  # FIXED: Nano model causes validation failures
    WEATHER_MODEL: str = os.getenv('WEATHER_MODEL', NANO_MODEL)  # Simple API data processing
    YOUTUBE_MODEL: str = os.getenv('YOUTUBE_MODEL', NANO_MODEL)  # Transcript extraction/processing
    REPORT_MODEL: str = os.getenv('REPORT_MODEL', STANDARD_MODEL)  # Quality reasoning needed
    # Domain classifier mode: 'llm' (default) or 'heuristic'
    DOMAIN_CLASSIFIER_MODE: str = os.getenv('DOMAIN_CLASSIFIER_MODE', 'llm')

    # Agent Settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

    # Research Settings
    MAX_RESEARCH_RESULTS: int = int(os.getenv("MAX_RESEARCH_RESULTS", "15"))  # Increased for more comprehensive research
    MAX_SCRAPING_PER_QUERY: int = int(os.getenv("MAX_SCRAPING_PER_QUERY", "8"))  # Limit expensive scraping operations
    RESEARCH_TIMEOUT: int = int(os.getenv("RESEARCH_TIMEOUT", "60"))

    # Tavily-specific Settings
    TAVILY_TIME_RANGE: str = os.getenv("TAVILY_TIME_RANGE", "month")
    TAVILY_SEARCH_DEPTH: str = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
    TAVILY_MIN_SCORE: float = float(os.getenv("TAVILY_MIN_SCORE", "0.5"))
    TAVILY_SCRAPING_THRESHOLD: float = float(os.getenv("TAVILY_SCRAPING_THRESHOLD", "0.5"))  # Scrape good quality results
    TAVILY_RATE_LIMIT_RPS: int = int(os.getenv("TAVILY_RATE_LIMIT_RPS", "5"))
    TAVILY_MAX_RESULTS: int = int(os.getenv("TAVILY_MAX_RESULTS", "50"))  # Get full result set from API

    # Serper-specific Settings
    SERPER_MAX_RESULTS: int = int(os.getenv("SERPER_MAX_RESULTS", "20"))  # Maximum reliable results per query

    # Streamlit Settings
    STREAMLIT_PORT: int = int(os.getenv("STREAMLIT_PORT", "8501"))
    STREAMLIT_HOST: str = os.getenv("STREAMLIT_HOST", "localhost")

    # Weather Settings
    WEATHER_UNITS: str = os.getenv("WEATHER_UNITS", "metric")
    WEATHER_LANG: str = os.getenv("WEATHER_LANG", "en")

    # Timezone Settings (default to Houston, TX - America/Chicago)
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Chicago")

    # State logging/truncation settings
    WRITE_TRUNCATED_STATE_COPY: bool = os.getenv("WRITE_TRUNCATED_STATE_COPY", "true").lower() == "true"
    LLM_STATE_MAX_FIELD_CHARS: int = int(os.getenv("LLM_STATE_MAX_FIELD_CHARS", "1000"))
    # Comma-separated list of fields to truncate in the LLM-friendly state copy
    LLM_STATE_TRUNCATE_FIELDS: list[str] = [f.strip() for f in os.getenv(
        "LLM_STATE_TRUNCATE_FIELDS",
        "raw_content,scraped_content,pre_filter_content,post_filter_content"
    ).split(",") if f.strip()]

    # Research parallelism & behavior flags
    RESEARCH_PARALLELISM_ENABLED: bool = os.getenv("RESEARCH_PARALLELISM_ENABLED", "false").lower() == "true"
    RESEARCH_MAX_CONCURRENCY: int = int(os.getenv("RESEARCH_MAX_CONCURRENCY", "8"))
    SERPER_MAX_CONCURRENCY: int = int(os.getenv("SERPER_MAX_CONCURRENCY", "5"))
    # Prevent agents from expanding queries on their own unless explicitly allowed
    ALLOW_AGENT_QUERY_EXPANSION: bool = os.getenv("ALLOW_AGENT_QUERY_EXPANSION", "false").lower() == "true"
    # Simple, global garbage filter quality threshold (0..1). Default unchanged unless user tests step-back.
    GARBAGE_FILTER_THRESHOLD: float = float(os.getenv("GARBAGE_FILTER_THRESHOLD", "0.2"))

    # Query Strategy Settings
    INCLUDE_ORIGINAL_QUERY: bool = os.getenv("INCLUDE_ORIGINAL_QUERY", "true").lower() == "true"  # Process 4 queries instead of 3
    ENABLE_URL_DEDUPLICATION: bool = os.getenv("ENABLE_URL_DEDUPLICATION", "true").lower() == "true"  # Cross-API deduplication
    
    # Content Processing Optimization
    MAX_PARALLEL_CLEANING: bool = os.getenv("MAX_PARALLEL_CLEANING", "true").lower() == "true"  # Remove batch limits for LLM cleaning

    # Content cleaning behavior - PDF processing now enabled with local text extraction
    CLEANING_SKIP_PDFS: bool = os.getenv("CLEANING_SKIP_PDFS", "false").lower() == "true"  # Enable PDF processing by default

    @classmethod
    def validate_required_keys(cls) -> list[str]:
        """Validate that required API keys are present."""
        missing_keys = []

        if not cls.OPENAI_API_KEY:
            missing_keys.append("OPENAI_API_KEY")

        return missing_keys

    @classmethod
    def get_model_settings(cls) -> dict:
        """Get model settings for Pydantic-AI agents."""
        return {
            "max_retries": cls.MAX_RETRIES,
            "timeout": cls.REQUEST_TIMEOUT,
        }

    @classmethod
    def get_agent_model(cls, agent_type: str) -> str:
        """Get the appropriate model for a specific agent type with fallback logic."""
        model_map = {
            "orchestrator": cls.ORCHESTRATOR_MODEL,
            "youtube": cls.YOUTUBE_MODEL,
            "weather": cls.WEATHER_MODEL,
            "research": cls.RESEARCH_MODEL,
            "report": cls.REPORT_MODEL,
            "tavily": cls.RESEARCH_MODEL,
            "serper": cls.RESEARCH_MODEL,
        }
        return model_map.get(agent_type.lower(), cls.DEFAULT_MODEL)

    @classmethod
    def get_fallback_model(cls, current_model: str) -> str:
        """Get fallback model if current model fails."""
        if current_model == cls.NANO_MODEL:
            return cls.STANDARD_MODEL
        return cls.STANDARD_MODEL  # Always fallback to standard model

    @classmethod
    def is_nano_model(cls, model: str) -> bool:
        """Check if the model is the nano (fast/cheap) model."""
        return model == cls.NANO_MODEL

    @classmethod
    def get_model_for_task(cls, task_type: str) -> str:
        """Get the appropriate model for a specific task type."""
        task_model_map = {
            # Report enhancement needs reasoning capability but not maximum model
            "report_enhancement": cls.REPORT_MODEL,
            # Domain classification can use fast model 
            "domain_classification": cls.NANO_MODEL,
            # Content cleaning and processing
            "content_cleaning": cls.STANDARD_MODEL,
            # Research synthesis
            "research_synthesis": cls.RESEARCH_MODEL,
            # Query expansion
            "query_expansion": cls.STANDARD_MODEL,
            # Default report writing
            "report_generation": cls.REPORT_MODEL,
            # Context assessment (simple task)
            "context_assessment": cls.NANO_MODEL,
        }
        return task_model_map.get(task_type.lower(), cls.DEFAULT_MODEL)


# Global config instance
config = Config()


def get_model_for_task(task_type: str) -> str:
    """Global function to get the appropriate model for a specific task type."""
    return config.get_model_for_task(task_type)
