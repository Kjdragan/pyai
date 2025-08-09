"""
Centralized state management system integrated with Pydantic AI framework.
Provides unified access to all agent work products and integrates with RunContext.

CRITICAL: This module acts as an orchestration boundary. It must accept
typed Pydantic models from agents, but also be resilient to callers that
accidentally pass dicts or JSON strings. To prevent infinite retry loops
from agents returning untyped outputs, we coerce inputs into the declared
Pydantic models before persisting them into the master state.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, Type, TypeVar
from threading import Lock
from pydantic import BaseModel

from models import (
    MasterOutputModel, JobRequest, ResearchPipelineModel, 
    YouTubeTranscriptModel, WeatherModel, ReportGenerationModel
)


class MasterStateManager:
    """
    Centralized state manager that integrates with Pydantic AI's dependency system.
    Allows agents to access each other's work products and maintains a master state document.
    """
    
    def __init__(self, orchestrator_id: str, job_request: JobRequest, log_dir: str = "src/logs/state"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self._lock = Lock()  # Thread safety for concurrent agent access
        
        # Initialize master state
        # Coerce job_request to dict to avoid model identity mismatches during tests/imports
        _jr = job_request.model_dump() if isinstance(job_request, BaseModel) else job_request
        self.master_state = MasterOutputModel(
            job_request=_jr,
            orchestrator_id=orchestrator_id,
            timestamp=datetime.now(),
            agents_used=[],
            success=True,
            errors=[]
        )
        
        # Track which agents have completed
        self._completed_agents = set()

    # ------------------------------------------------------------------
    # Internal helpers: type coercion at orchestration boundaries
    # ------------------------------------------------------------------
    TModel = TypeVar('TModel', bound=BaseModel)

    def _coerce_to_model(self, value: Any, model_cls: Type[TModel]) -> TModel:
        """Coerce input into a Pydantic model instance of model_cls.

        Accepts:
        - An instance of model_cls
        - Any Pydantic BaseModel (converted via model_dump)
        - A dict (validated directly)
        - A JSON string encoding a dict

        Raises ValueError with a descriptive message on failure.
        """
        # Already correct type
        if isinstance(value, model_cls):
            return value

        # Any other BaseModel → dump then validate
        if isinstance(value, BaseModel):
            try:
                return model_cls.model_validate(value.model_dump())
            except Exception as e:
                raise ValueError(f"Failed to coerce BaseModel to {model_cls.__name__}: {e}")

        # Dict → validate
        if isinstance(value, dict):
            try:
                return model_cls.model_validate(value)
            except Exception as e:
                raise ValueError(f"Failed to validate dict as {model_cls.__name__}: {e}")

        # JSON string → parse then validate
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception as e:
                raise ValueError(f"Failed to parse JSON string for {model_cls.__name__}: {e}")
            if not isinstance(parsed, dict):
                raise ValueError(f"Parsed JSON for {model_cls.__name__} is not an object")
            try:
                return model_cls.model_validate(parsed)
            except Exception as e:
                raise ValueError(f"Failed to validate parsed JSON as {model_cls.__name__}: {e}")

        # Unsupported
        raise ValueError(f"Unsupported type {type(value)} for coercion to {model_cls.__name__}")
        
    def update_research_data(self, agent_name: str, research_data: Any) -> None:
        """Store research pipeline results in master state with type coercion."""
        with self._lock:
            try:
                coerced = self._coerce_to_model(research_data, ResearchPipelineModel)
            except Exception as e:
                # Record error but do not raise to avoid cascading failures
                self.master_state.errors.append(f"{agent_name}: Research data type error - {e}")
                self.master_state.success = False
                self._persist_state()
                return
            self.master_state.research_data = coerced
            self._completed_agents.add(agent_name)
            if agent_name not in self.master_state.agents_used:
                self.master_state.agents_used.append(agent_name)
            self._persist_state()
            
    def update_youtube_data(self, agent_name: str, youtube_data: Any) -> None:
        """Store YouTube transcript results in master state with type coercion."""
        with self._lock:
            try:
                coerced = self._coerce_to_model(youtube_data, YouTubeTranscriptModel)
            except Exception as e:
                self.master_state.errors.append(f"{agent_name}: YouTube data type error - {e}")
                self.master_state.success = False
                self._persist_state()
                return
            self.master_state.youtube_data = coerced
            self._completed_agents.add(agent_name)
            if agent_name not in self.master_state.agents_used:
                self.master_state.agents_used.append(agent_name)
            self._persist_state()
            
    def update_weather_data(self, agent_name: str, weather_data: Any) -> None:
        """Store weather results in master state with type coercion."""
        with self._lock:
            try:
                coerced = self._coerce_to_model(weather_data, WeatherModel)
            except Exception as e:
                self.master_state.errors.append(f"{agent_name}: Weather data type error - {e}")
                self.master_state.success = False
                self._persist_state()
                return
            self.master_state.weather_data = coerced
            self._completed_agents.add(agent_name)
            if agent_name not in self.master_state.agents_used:
                self.master_state.agents_used.append(agent_name)
            self._persist_state()
            
    def update_report_data(self, agent_name: str, report_data: Any) -> None:
        """Store report generation results in master state with type coercion."""
        with self._lock:
            try:
                coerced = self._coerce_to_model(report_data, ReportGenerationModel)
            except Exception as e:
                self.master_state.errors.append(f"{agent_name}: Report data type error - {e}")
                self.master_state.success = False
                self._persist_state()
                return
            self.master_state.report_data = coerced
            self._completed_agents.add(agent_name)
            if agent_name not in self.master_state.agents_used:
                self.master_state.agents_used.append(agent_name)
            self._persist_state()
            
    def add_error(self, agent_name: str, error: str) -> None:
        """Add an error from an agent to the master state."""
        with self._lock:
            self.master_state.errors.append(f"{agent_name}: {error}")
            self.master_state.success = False
            self._persist_state()
            
    def get_research_data(self) -> Optional[ResearchPipelineModel]:
        """Get research data for use by other agents (e.g., report writer)."""
        return self.master_state.research_data
        
    def get_youtube_data(self) -> Optional[YouTubeTranscriptModel]:
        """Get YouTube data for use by other agents."""
        return self.master_state.youtube_data
        
    def get_weather_data(self) -> Optional[WeatherModel]:
        """Get weather data for use by other agents."""
        return self.master_state.weather_data

        
    def get_universal_report_data(self) -> 'UniversalReportData':
        """Get unified data package for report generation."""
        from models import UniversalReportData
        return UniversalReportData(
            query=self.master_state.job_request.query,
            youtube_data=self.master_state.youtube_data,
            research_data=self.master_state.research_data,
            weather_data=self.master_state.weather_data
        )
        
    def get_master_state(self) -> MasterOutputModel:
        """Get the complete master state document."""
        return self.master_state
        
    def is_agent_completed(self, agent_name: str) -> bool:
        """Check if a specific agent has completed its work."""
        return agent_name in self._completed_agents
        
    def get_completed_agents(self) -> set:
        """Get list of agents that have completed their work."""
        return self._completed_agents.copy()
        
    def set_processing_time(self, processing_time: float) -> None:
        """Set the total processing time for the job."""
        with self._lock:
            self.master_state.total_processing_time = processing_time
            self._persist_state()
            
    def _persist_state(self) -> None:
        """Persist the current master state to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"master_state_{self.master_state.orchestrator_id}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Use the model's JSON serialization
                json.dump(
                    self.master_state.model_dump(mode='json'), 
                    f, 
                    indent=2, 
                    ensure_ascii=False,
                    default=str  # Handle any remaining datetime objects
                )
        except Exception as e:
            logging.error(f"Failed to persist master state: {e}")
            
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state for debugging/monitoring."""
        return {
            "orchestrator_id": self.master_state.orchestrator_id,
            "job_type": self.master_state.job_request.job_type,
            "query": self.master_state.job_request.query,
            "agents_used": self.master_state.agents_used,
            "completed_agents": list(self._completed_agents),
            "has_research_data": self.master_state.research_data is not None,
            "has_youtube_data": self.master_state.youtube_data is not None,
            "has_weather_data": self.master_state.weather_data is not None,
            "has_report_data": self.master_state.report_data is not None,
            "success": self.master_state.success,
            "error_count": len(self.master_state.errors),
            "processing_time": self.master_state.total_processing_time
        }


class StateAwareDeps:
    """
    Base dependency class that includes access to the master state manager.
    All agent dependencies should inherit from this to enable state access.
    """
    
    def __init__(self, state_manager: MasterStateManager):
        self.state_manager = state_manager
        
    def get_research_data(self) -> Optional[ResearchPipelineModel]:
        """Access research data from other agents."""
        return self.state_manager.get_research_data()
        
    def get_youtube_data(self) -> Optional[YouTubeTranscriptModel]:
        """Access YouTube data from other agents."""
        return self.state_manager.get_youtube_data()
        
    def get_weather_data(self) -> Optional[WeatherModel]:
        """Access weather data from other agents."""
        return self.state_manager.get_weather_data()