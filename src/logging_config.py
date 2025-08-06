"""
Comprehensive logging configuration for Pydantic-AI Multi-Agent System.
Integrates with Pydantic AI's built-in observability features and provides
structured logging for debugging and monitoring.
"""

import logging
import logging.handlers
import os
import sys
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json
import traceback
from contextlib import contextmanager

from pydantic_ai.agent import InstrumentationSettings


class PydanticAIFormatter(logging.Formatter):
    """Custom formatter for Pydantic AI logs with structured output."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        # Create base log entry
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields for agent-specific information
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                              'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                              'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    try:
                        # Ensure the value is JSON serializable
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False)


class AgentLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for agent-specific logging with context."""
    
    def __init__(self, logger: logging.Logger, agent_name: str, agent_id: str = None):
        self.agent_name = agent_name
        self.agent_id = agent_id or "unknown"
        super().__init__(logger, {})
    
    def process(self, msg: Any, kwargs: Dict[str, Any]) -> tuple[Any, Dict[str, Any]]:
        # Add agent context to all log messages
        extra = kwargs.get('extra', {})
        extra.update({
            'agent_name': self.agent_name,
            'agent_id': self.agent_id,
            'component': 'agent'
        })
        kwargs['extra'] = extra
        return msg, kwargs
    
    def log_agent_start(self, query: str, **kwargs):
        """Log agent execution start."""
        self.info(f"Agent {self.agent_name} starting execution", 
                 extra={'event_type': 'agent_start', 'query': query, **kwargs})
    
    def log_agent_complete(self, success: bool, duration: float, **kwargs):
        """Log agent execution completion."""
        status = "completed" if success else "failed"
        self.info(f"Agent {self.agent_name} {status}", 
                 extra={'event_type': 'agent_complete', 'success': success, 
                       'duration_seconds': duration, **kwargs})
    
    def log_model_call(self, model: str, prompt_length: int, **kwargs):
        """Log model API calls."""
        self.debug(f"Model call to {model}", 
                  extra={'event_type': 'model_call', 'model': model, 
                        'prompt_length': prompt_length, **kwargs})
    
    def log_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs):
        """Log tool function calls."""
        self.debug(f"Tool call: {tool_name}", 
                  extra={'event_type': 'tool_call', 'tool_name': tool_name, 
                        'tool_args': args, **kwargs})


class LoggingManager:
    """Central logging manager for the Pydantic AI system."""
    
    def __init__(self, logs_dir: str = None):
        self.logs_dir = Path(logs_dir) if logs_dir else Path(__file__).parent / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.loggers: Dict[str, logging.Logger] = {}
        self.agent_adapters: Dict[str, AgentLoggerAdapter] = {}
        
        
        # Setup base logging configuration
        self._setup_base_logging()
    
    
    
    def _setup_base_logging(self):
        """Setup base Python logging configuration."""
        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        file_formatter = PydanticAIFormatter(include_extra=True)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Console handler (INFO level - clean output)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (DEBUG level)
        log_file = self.logs_dir / f"pyai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=50*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Error file handler (ERROR level only) - only create if there are actual errors
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hostname = socket.gethostname()
        error_file = self.logs_dir / f"pyai-error_{hostname}_{timestamp}.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file, maxBytes=25*1024*1024, backupCount=2, encoding='utf-8', delay=True
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        print(f"📝 Logging configured - Files: {log_file.name}, {error_file.name}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger for a specific component."""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]
    
    def get_agent_logger(self, agent_name: str, agent_id: str = None) -> AgentLoggerAdapter:
        """Get or create an agent-specific logger adapter."""
        key = f"{agent_name}_{agent_id}" if agent_id else agent_name
        
        if key not in self.agent_adapters:
            base_logger = self.get_logger(f"agent.{agent_name}")
            self.agent_adapters[key] = AgentLoggerAdapter(base_logger, agent_name, agent_id)
        
        return self.agent_adapters[key]
    
    def create_instrumentation_settings(self) -> Optional[InstrumentationSettings]:
        """Create custom instrumentation settings for Pydantic AI agents."""
        try:
            # Create custom providers if needed
            instrumentation_settings = InstrumentationSettings(
                include_content=True,  # Include prompts and completions
                include_binary_content=False,  # Exclude binary data
            )
            
            return instrumentation_settings
            
        except ImportError:
            return None
    
    @contextmanager
    def log_agent_execution(self, agent_name: str, query: str, agent_id: str = None):
        """Context manager for logging agent execution with timing."""
        agent_logger = self.get_agent_logger(agent_name, agent_id)
        start_time = datetime.now()
        
        agent_logger.log_agent_start(query)
        
        
        try:
            yield agent_logger
            
            # Log successful completion
            duration = (datetime.now() - start_time).total_seconds()
            agent_logger.log_agent_complete(True, duration)
            
        except Exception as e:
            # Log failed completion
            duration = (datetime.now() - start_time).total_seconds()
            agent_logger.log_agent_complete(False, duration)
            agent_logger.exception(f"Agent {agent_name} execution failed: {str(e)}")
            raise
    
    def log_system_event(self, event_type: str, message: str, **kwargs):
        """Log system-level events."""
        logger = self.get_logger("system")
        logger.info(message, extra={'event_type': event_type, **kwargs})
    
    def log_api_call(self, service: str, endpoint: str, status_code: int, 
                     duration: float, **kwargs):
        """Log external API calls."""
        logger = self.get_logger("api")
        logger.info(f"API call to {service}/{endpoint}", 
                   extra={'event_type': 'api_call', 'service': service, 
                         'endpoint': endpoint, 'status_code': status_code,
                         'duration_seconds': duration, **kwargs})


# Global logging manager instance
_logging_manager: Optional[LoggingManager] = None


def initialize_logging(logs_dir: str = None) -> LoggingManager:
    """Initialize the global logging manager."""
    global _logging_manager
    _logging_manager = LoggingManager(logs_dir)
    return _logging_manager


def get_logging_manager() -> LoggingManager:
    """Get the global logging manager instance."""
    if _logging_manager is None:
        raise RuntimeError("Logging not initialized. Call initialize_logging() first.")
    return _logging_manager


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a logger."""
    return get_logging_manager().get_logger(name)


def get_agent_logger(agent_name: str, agent_id: str = None) -> AgentLoggerAdapter:
    """Convenience function to get an agent logger."""
    return get_logging_manager().get_agent_logger(agent_name, agent_id)
