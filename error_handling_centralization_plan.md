# Error Handling Centralization Implementation Plan

## Current Problem Analysis

### Redundant Error Handling Layers

**Issue**: Multiple layers of exception handling create verbose logs and maintenance overhead.

**Current Pattern in Every Agent**:
```python
# Layer 1: Agent function level
try:
    result = await some_operation()
except Exception as e:
    print(f"Operation failed: {e}")
    
# Layer 2: AgentResponse wrapping  
return AgentResponse(
    agent_name="SomeAgent",
    success=False,
    error=str(e),
    processing_time=processing_time
)

# Layer 3: Orchestrator level
try:
    agent_response = await process_research_request(query)
    if not agent_response.success:
        print(f"Agent failed: {agent_response.error}")
except Exception as e:
    print(f"Orchestrator error: {e}")
```

**Impact**:
- **Log Noise**: Same error logged 3 times with different formats
- **Inconsistent Error Messages**: Each layer formats errors differently  
- **Maintenance Overhead**: Error handling logic duplicated across 11 agents
- **Debugging Difficulty**: Hard to trace actual error source through layers

## Recommended Centralized Architecture

### 1. Error Classification System

```python
# src/agents/error_handler.py
from enum import Enum
from typing import Optional, Dict, Any

class ErrorSeverity(Enum):
    LOW = "low"        # Recoverable, fallback available
    MEDIUM = "medium"  # Significant but not blocking
    HIGH = "high"      # Blocks current operation
    CRITICAL = "critical" # System-wide impact

class ErrorCategory(Enum):
    NETWORK = "network"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    MODEL = "model"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

class AgentError(Exception):
    """Standardized agent error with context."""
    def __init__(
        self, 
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        agent_name: str,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.agent_name = agent_name
        self.context = context or {}
        self.recoverable = recoverable
        super().__init__(message)
```

### 2. Centralized Error Handler Service

```python
class ErrorHandler:
    """Centralized error handling and logging service."""
    
    def __init__(self):
        self.logger = get_agent_logger("ErrorHandler")
        self.error_counts = defaultdict(int)
        self.recovery_strategies = self._init_recovery_strategies()
    
    async def handle_error(
        self, 
        error: Exception, 
        agent_name: str,
        operation: str,
        context: Dict[str, Any] = None
    ) -> tuple[bool, Optional[Any]]:
        """
        Handle error with automatic recovery attempts.
        
        Returns:
            tuple[recovered, result]: Whether recovery succeeded and result if any
        """
        # Classify error
        agent_error = self._classify_error(error, agent_name, operation, context)
        
        # Log with appropriate level
        self._log_error(agent_error)
        
        # Update metrics
        self._update_metrics(agent_error)
        
        # Attempt recovery
        if agent_error.recoverable:
            return await self._attempt_recovery(agent_error)
        
        return False, None
    
    def _classify_error(self, error: Exception, agent_name: str, operation: str, context: Dict) -> AgentError:
        """Classify exception into structured AgentError."""
        if isinstance(error, httpx.TimeoutError):
            return AgentError(
                f"Timeout in {operation}",
                ErrorCategory.TIMEOUT,
                ErrorSeverity.MEDIUM,
                agent_name,
                context,
                recoverable=True
            )
        elif "rate limit" in str(error).lower():
            return AgentError(
                f"Rate limit exceeded in {operation}",
                ErrorCategory.RATE_LIMIT,
                ErrorSeverity.MEDIUM,
                agent_name,
                context,
                recoverable=True
            )
        elif "401" in str(error) or "unauthorized" in str(error).lower():
            return AgentError(
                f"Authentication failed in {operation}",
                ErrorCategory.AUTH,
                ErrorSeverity.HIGH,
                agent_name,
                context,
                recoverable=False
            )
        # ... more classification rules
        
    async def _attempt_recovery(self, error: AgentError) -> tuple[bool, Optional[Any]]:
        """Attempt error recovery based on category."""
        strategy = self.recovery_strategies.get(error.category)
        if strategy:
            return await strategy(error)
        return False, None
```

### 3. Agent Integration Pattern

```python
# Simplified agent pattern
class ResearchAgent:
    def __init__(self):
        self.error_handler = ErrorHandler()
    
    async def search(self, query: str) -> AgentResponse:
        """Clean agent logic with centralized error handling."""
        try:
            # Core business logic only
            results = await self._perform_search(query)
            
            return AgentResponse(
                agent_name="ResearchAgent",
                success=True,
                data=results
            )
            
        except Exception as e:
            # Single centralized error handling
            recovered, fallback_data = await self.error_handler.handle_error(
                error=e,
                agent_name="ResearchAgent", 
                operation="search",
                context={"query": query}
            )
            
            if recovered and fallback_data:
                return AgentResponse(
                    agent_name="ResearchAgent",
                    success=True,
                    data=fallback_data,
                    warning="Recovered from error using fallback"
                )
            else:
                return AgentResponse(
                    agent_name="ResearchAgent",
                    success=False,
                    error=str(e)
                )
```

### 4. Orchestrator Simplification

```python
# Simplified orchestrator with centralized errors
async def run_orchestrator_job(job_request: JobRequest) -> MasterOutputModel:
    """Simplified orchestrator using centralized error handling."""
    
    # No more try/catch wrapping - errors handled at agent level
    if job_request.job_type == "research":
        research_response = await process_research_request(job_request.query)
        # Agent already handled errors internally
        
    # Orchestrator focuses on coordination, not error handling
    return MasterOutputModel(
        job_request=job_request,
        research_data=research_response.data if research_response.success else None,
        errors=[research_response.error] if not research_response.success else []
    )
```

## Implementation Benefits

### Code Reduction
- **~50% Error Handling Code Elimination**: Remove duplicate try/catch blocks
- **Consistent Error Format**: Single logging format across all agents
- **Simplified Agent Logic**: Agents focus on business logic, not error handling

### Improved Observability
- **Structured Error Metrics**: Track error patterns across system
- **Error Classification**: Understand error types and frequencies
- **Recovery Success Rates**: Monitor which strategies work

### Enhanced Reliability
- **Automatic Recovery**: Built-in retry and fallback mechanisms
- **Circuit Breaker Pattern**: Prevent cascade failures
- **Graceful Degradation**: System continues operating with reduced functionality

## Migration Strategy

### Phase 1: Error Classification (1 day)
1. Create `AgentError` and `ErrorHandler` classes
2. Add error classification logic for common patterns
3. Create recovery strategies for each error category

### Phase 2: Agent Migration (2-3 days) 
1. Start with least critical agent (Weather)
2. Remove agent-level error handling, use centralized handler
3. Update one agent at a time, validate behavior
4. Migrate orchestrator last

### Phase 3: Metrics & Monitoring (1 day)
1. Add error dashboards and alerting
2. Monitor error patterns and recovery rates
3. Fine-tune recovery strategies based on data

## Risk Assessment

**Low Risk**:
- ✅ Backward compatibility maintained through AgentResponse
- ✅ Gradual migration possible - replace one agent at a time
- ✅ Fallback to original error handling if centralized system fails

**Medium Risk**:
- ⚠️ Complex error scenarios may need custom handling
- ⚠️ Recovery strategies need tuning based on real usage

**Success Metrics**:
- ✅ 50% reduction in error handling code
- ✅ Consistent error logging format across all agents
- ✅ Improved error recovery rates (target: 70% recoverable errors auto-resolved)
- ✅ Faster debugging - single error trace instead of multiple layers