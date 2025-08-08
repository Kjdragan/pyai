import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from config import Config
from pydantic import BaseModel
from models import (
    ResearchPipelineModel, MasterOutputModel, YouTubeTranscriptModel, 
    WeatherModel, ReportGenerationModel, AgentResponse
)

class ResearchDataLogger:
    """Logger for capturing complete state model for each agent."""
    
    def __init__(self, log_dir: str = "src/logs/state"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    class PydanticJSONEncoder(json.JSONEncoder):
        """Custom JSON encoder that handles Pydantic types like datetime."""
        def default(self, obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            return super().default(obj)
    
    @staticmethod
    def _truncate_fields(obj: Any, fields_to_truncate: set[str], max_chars: int) -> Any:
        """Return a truncated deep copy of obj, limiting specified fields to max_chars.
        Truncates only string values for matching keys; recurses into dicts/lists.
        """
        def _trunc(val: str) -> str:
            if val is None:
                return val
            if len(val) <= max_chars:
                return val
            return val[:max_chars] + "...[TRUNCATED]"

        def _walk(node: Any) -> Any:
            if isinstance(node, dict):
                new_d = {}
                for k, v in node.items():
                    if k in fields_to_truncate and isinstance(v, str):
                        new_d[k] = _trunc(v)
                    else:
                        new_d[k] = _walk(v)
                return new_d
            if isinstance(node, list):
                return [_walk(x) for x in node]
            return node

        return _walk(obj)
    
    def log_agent_state(self, agent_name: str, agent_data: dict, master_output: MasterOutputModel = None):
        """Log the complete state model for a specific agent to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"{agent_name}_state_{timestamp}.json"
        
        # Create a comprehensive log entry
        log_entry = {
            "timestamp": timestamp,
            "agent_name": agent_name,
            "agent_data": agent_data
        }
        
        # Add master output data if available
        if master_output:
            log_entry["master_output"] = {
                "job_request": {
                    "job_type": master_output.job_request.job_type,
                    "query": master_output.job_request.query,
                    "report_style": master_output.job_request.report_style
                },
                "orchestrator_id": master_output.orchestrator_id,
                "agents_used": master_output.agents_used,
                "success": master_output.success,
                "errors": master_output.errors,
                "total_processing_time": master_output.total_processing_time
            }
        
        # Write to file with custom encoder
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False, cls=self.PydanticJSONEncoder)
        
        print(f"{agent_name} state logged to: {filename}")

        # Optionally write truncated LLM-friendly copy
        if Config.WRITE_TRUNCATED_STATE_COPY:
            fields = set(Config.LLM_STATE_TRUNCATE_FIELDS)
            max_chars = Config.LLM_STATE_MAX_FIELD_CHARS
            truncated_entry = self._truncate_fields(log_entry, fields, max_chars)
            llm_filename = filename.with_name(filename.stem + ".llm.json")
            with open(llm_filename, 'w', encoding='utf-8') as f_llm:
                json.dump(truncated_entry, f_llm, indent=2, ensure_ascii=False, cls=self.PydanticJSONEncoder)
            print(f"LLM-friendly truncated state written to: {llm_filename}")
        return filename
    
    def log_research_state(self, research_data: ResearchPipelineModel, master_output: MasterOutputModel = None):
        """Log the complete research data model state to a JSON file."""
        return self.log_agent_state("ResearchPipeline", research_data.model_dump(), master_output)
    
    def log_youtube_state(self, youtube_data: YouTubeTranscriptModel, master_output: MasterOutputModel = None):
        """Log the complete YouTube data model state to a JSON file."""
        return self.log_agent_state("YouTube", youtube_data.model_dump(), master_output)
    
    def log_weather_state(self, weather_data: WeatherModel, master_output: MasterOutputModel = None):
        """Log the complete weather data model state to a JSON file."""
        return self.log_agent_state("Weather", weather_data.model_dump(), master_output)
    
    def log_report_state(self, report_data: ReportGenerationModel, master_output: MasterOutputModel = None):
        """Log the complete report data model state to a JSON file."""
        return self.log_agent_state("Report", report_data.model_dump(), master_output)

# Example usage:
# logger = ResearchDataLogger()
# logger.log_research_state(research_pipeline_model, master_output_model)


class MasterStateLogger:
    """Logger for the centralized master state document."""
    
    def __init__(self, log_dir: str = "src/logs/state"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    class PydanticJSONEncoder(json.JSONEncoder):
        """Custom JSON encoder that handles Pydantic types like datetime."""
        def default(self, obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            return super().default(obj)
    
    def log_master_state(self, master_output: MasterOutputModel, state_summary: dict = None) -> str:
        """Log the complete master state document to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"master_state_{master_output.orchestrator_id}_{timestamp}.json"
        
        # Create comprehensive log entry
        log_entry = {
            "timestamp": timestamp,
            "master_state": master_output.model_dump(),
            "state_summary": state_summary or {}
        }
        
        # Write to file with custom encoder
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False, cls=self.PydanticJSONEncoder)
        
        print(f"Master state logged to: {filename}")

        # Optional LLM-friendly truncated copy
        if Config.WRITE_TRUNCATED_STATE_COPY:
            fields = set(Config.LLM_STATE_TRUNCATE_FIELDS)
            max_chars = Config.LLM_STATE_MAX_FIELD_CHARS
            truncated_entry = ResearchDataLogger._truncate_fields(log_entry, fields, max_chars)
            llm_filename = filename.with_name(filename.stem + ".llm.json")
            with open(llm_filename, 'w', encoding='utf-8') as f_llm:
                json.dump(truncated_entry, f_llm, indent=2, ensure_ascii=False, cls=self.PydanticJSONEncoder)
            print(f"LLM-friendly truncated master state written to: {llm_filename}")
        return str(filename)
