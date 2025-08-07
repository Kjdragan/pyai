"""
Configuration settings for the multi-agent system.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

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
    NANO_MODEL: str = "gpt-4.1-nano-2025-04-14"
    # Intelligent model for complex reasoning  
    STANDARD_MODEL: str = "gpt-4o"
    
    # Agent-specific model assignments (respects environment variables)
    DEFAULT_MODEL: str = os.getenv('DEFAULT_MODEL', 'gpt-4o-mini')  # Default to efficient model
    ORCHESTRATOR_MODEL: str = os.getenv('ORCHESTRATOR_MODEL', STANDARD_MODEL)  # Complex coordination
    RESEARCH_MODEL: str = os.getenv('RESEARCH_MODEL', 'gpt-4o-mini')  # FIXED: Nano model causes validation failures  
    WEATHER_MODEL: str = os.getenv('WEATHER_MODEL', NANO_MODEL)  # Simple API data processing
    YOUTUBE_MODEL: str = os.getenv('YOUTUBE_MODEL', NANO_MODEL)  # Transcript extraction/processing
    REPORT_MODEL: str = os.getenv('REPORT_MODEL', STANDARD_MODEL)  # Quality reasoning needed
    
    # Agent Settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Research Settings
    MAX_RESEARCH_RESULTS: int = int(os.getenv("MAX_RESEARCH_RESULTS", "10"))
    RESEARCH_TIMEOUT: int = int(os.getenv("RESEARCH_TIMEOUT", "60"))
    
    # Tavily-specific Settings
    TAVILY_TIME_RANGE: str = os.getenv("TAVILY_TIME_RANGE", "month")
    TAVILY_SEARCH_DEPTH: str = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
    TAVILY_MIN_SCORE: float = float(os.getenv("TAVILY_MIN_SCORE", "0.5"))
    TAVILY_RATE_LIMIT_RPS: int = int(os.getenv("TAVILY_RATE_LIMIT_RPS", "5"))
    
    # Streamlit Settings
    STREAMLIT_PORT: int = int(os.getenv("STREAMLIT_PORT", "8501"))
    STREAMLIT_HOST: str = os.getenv("STREAMLIT_HOST", "localhost")
    
    # Weather Settings
    WEATHER_UNITS: str = os.getenv("WEATHER_UNITS", "metric")
    WEATHER_LANG: str = os.getenv("WEATHER_LANG", "en")
    
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


# Global config instance
config = Config()
