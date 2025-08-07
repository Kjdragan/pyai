"""
Centralized retry mechanism for Pydantic AI agents with intelligent fallback.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional, Type, Union
from functools import wraps
from enum import Enum

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
try:
    from pydantic_ai.exceptions import ModelRetryError
except ImportError:
    # Fallback for different Pydantic AI versions
    from pydantic_ai.exceptions import ModelHTTPError as ModelRetryError
from openai import APIError, RateLimitError, APIConnectionError

from config import config


class ErrorCategory(Enum):
    """Categories of errors for different retry strategies."""
    TRANSIENT = "transient"      # Network issues, rate limits, temporary API problems
    PERMANENT = "permanent"      # Invalid API keys, malformed requests, model errors
    MODEL_SPECIFIC = "model"     # Model-specific issues that might work with fallback


class RetryStrategy:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = None,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        enable_model_fallback: bool = True
    ):
        self.max_retries = max_retries or config.MAX_RETRIES
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.enable_model_fallback = enable_model_fallback


class PydanticAIRetryHandler:
    """Enhanced retry handler specifically designed for Pydantic AI agents."""
    
    def __init__(self, strategy: RetryStrategy = None):
        self.strategy = strategy or RetryStrategy()
        self.logger = logging.getLogger(f"{__name__}.PydanticAIRetryHandler")
        self._circuit_breaker_state: Dict[str, Dict] = {}
    
    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error to determine appropriate retry strategy."""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Permanent errors - don't retry
        permanent_indicators = [
            "invalid api key",
            "unauthorized", 
            "authentication failed",
            "invalid request format",
            "model not found",
            "insufficient credits"
        ]
        
        if any(indicator in error_message for indicator in permanent_indicators):
            return ErrorCategory.PERMANENT
        
        # Transient network/API errors - safe to retry
        if isinstance(error, (APIConnectionError, RateLimitError)):
            return ErrorCategory.TRANSIENT
        
        # Model-specific errors - try fallback model
        if isinstance(error, (ModelRetryError, UnexpectedModelBehavior)):
            return ErrorCategory.MODEL_SPECIFIC
        
        # Output validation errors - likely need a more capable model
        output_validation_indicators = [
            "output validation",
            "exceeded maximum retries",
            "validation error",
            "pydantic validation",
            "invalid output format",
            "failed to parse output"
        ]
        
        if any(indicator in error_message for indicator in output_validation_indicators):
            return ErrorCategory.MODEL_SPECIFIC
        
        # 503 Service Unavailable and similar
        if "503" in error_message or "service unavailable" in error_message:
            return ErrorCategory.TRANSIENT
        
        # Default to model-specific for unknown errors
        return ErrorCategory.MODEL_SPECIFIC
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = self.strategy.base_delay * (self.strategy.exponential_base ** attempt)
        delay = min(delay, self.strategy.max_delay)
        
        if self.strategy.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        
        return delay
    
    async def execute_with_retry(
        self,
        agent: Agent,
        prompt: str,
        agent_name: str = "Unknown",
        **kwargs
    ) -> Any:
        """Execute Pydantic AI agent with intelligent retry and fallback logic."""
        
        original_model = agent.model
        current_model = original_model
        fallback_attempted = False
        
        for attempt in range(self.strategy.max_retries + 1):
            try:
                self.logger.info(f"Agent {agent_name} attempt {attempt + 1}/{self.strategy.max_retries + 1} with model {current_model}")
                
                # Update agent model if we're using fallback
                if fallback_attempted:
                    # Create new agent instance with fallback model
                    from pydantic_ai.models.openai import OpenAIModel
                    fallback_model_str = config.get_fallback_model(str(original_model))
                    agent = Agent(
                        model=OpenAIModel(fallback_model_str),
                        deps_type=agent.deps_type,
                        output_type=agent.output_type,
                        system_prompt=agent.system_prompt,
                        instrument=True,
                        retries=1  # Avoid nested retries
                    )
                    current_model = fallback_model_str
                
                # Execute the agent
                result = await agent.run(prompt, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"Agent {agent_name} succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                error_category = self.categorize_error(e)
                self.logger.warning(f"Agent {agent_name} attempt {attempt + 1} failed: {e} (Category: {error_category.value})")
                
                # Don't retry permanent errors
                if error_category == ErrorCategory.PERMANENT:
                    self.logger.error(f"Permanent error in agent {agent_name}, not retrying: {e}")
                    raise e
                
                # On last attempt, raise the error
                if attempt >= self.strategy.max_retries:
                    self.logger.error(f"Agent {agent_name} exhausted all retry attempts")
                    raise e
                
                # Try model fallback for model-specific errors (only once)
                if (error_category == ErrorCategory.MODEL_SPECIFIC and 
                    not fallback_attempted and 
                    self.strategy.enable_model_fallback):
                    
                    fallback_model = config.get_fallback_model(str(current_model))
                    if fallback_model != str(current_model):
                        self.logger.info(f"Agent {agent_name} attempting model fallback: {current_model} -> {fallback_model}")
                        fallback_attempted = True
                        # Don't increment attempt counter for fallback
                        continue
                
                # Calculate delay for transient errors
                if error_category == ErrorCategory.TRANSIENT:
                    delay = self.calculate_delay(attempt)
                    self.logger.info(f"Agent {agent_name} waiting {delay:.2f}s before retry")
                    await asyncio.sleep(delay)


# Global retry handler instance
default_retry_handler = PydanticAIRetryHandler()


def with_retry(
    strategy: RetryStrategy = None,
    agent_name: str = None
):
    """Decorator to add retry logic to Pydantic AI agent execution functions."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = PydanticAIRetryHandler(strategy) if strategy else default_retry_handler
            
            # Extract agent and prompt from function arguments
            # Assumes first arg is agent, second is prompt
            if len(args) >= 2:
                agent, prompt = args[0], args[1]
                name = agent_name or getattr(agent, '__name__', 'Unknown')
                
                return await handler.execute_with_retry(
                    agent=agent,
                    prompt=prompt,
                    agent_name=name,
                    **kwargs
                )
            else:
                # Fallback to original function if signature doesn't match
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def create_agent_with_retry(
    model_str: str,
    agent_type: str,
    deps_type: Type = None,
    output_type: Type = None,
    system_prompt: str = "",
    custom_strategy: RetryStrategy = None,
    **agent_kwargs
) -> Agent:
    """Create a Pydantic AI agent with enhanced retry configuration."""
    
    from pydantic_ai.models.openai import OpenAIModel
    
    # Use smart model selection
    final_model = config.get_agent_model(agent_type) if model_str == "auto" else model_str
    
    # Create agent with minimal built-in retries (we handle retries externally)
    agent = Agent(
        model=OpenAIModel(final_model),
        deps_type=deps_type,
        output_type=output_type,
        system_prompt=system_prompt,
        instrument=True,  # Enable Logfire tracing
        retries=1,  # Minimal built-in retries to avoid conflicts
        **agent_kwargs
    )
    
    return agent


# Convenience functions for common retry strategies
def create_fast_retry_strategy() -> RetryStrategy:
    """Strategy for fast operations that should fail quickly."""
    return RetryStrategy(
        max_retries=2,
        base_delay=0.5,
        max_delay=5.0,
        enable_model_fallback=True
    )


def create_robust_retry_strategy() -> RetryStrategy:
    """Strategy for critical operations that need high reliability."""
    return RetryStrategy(
        max_retries=5,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=1.5,
        enable_model_fallback=True
    )