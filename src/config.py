"""
Configuration settings for the multi-agent system.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for the multi-agent system."""
    
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    
    # Model Settings
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    ORCHESTRATOR_MODEL: str = os.getenv("ORCHESTRATOR_MODEL", "gpt-4o-mini")
    
    # Individual Agent Model Settings
    YOUTUBE_MODEL: str = os.getenv("YOUTUBE_MODEL", "gpt-4o-mini")
    WEATHER_MODEL: str = os.getenv("WEATHER_MODEL", "gpt-4o-mini")
    RESEARCH_MODEL: str = os.getenv("RESEARCH_MODEL", "gpt-4o-mini")
    REPORT_MODEL: str = os.getenv("REPORT_MODEL", "gpt-4o-mini")
    
    # Agent Settings
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Research Settings
    MAX_RESEARCH_RESULTS: int = int(os.getenv("MAX_RESEARCH_RESULTS", "10"))
    RESEARCH_TIMEOUT: int = int(os.getenv("RESEARCH_TIMEOUT", "60"))
    
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


# Global config instance
config = Config()
