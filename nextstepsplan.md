# Critical PyAI Performance Fixes - Development Plan

**Status**: SYSTEM FAILING - 510 second timeouts with asyncio shutdown errors  
**Priority**: P0 (Production Breaking)  
**Last Updated**: 2025-08-08

## 🚨 CRITICAL ISSUE: System Complete Failure

**Current State**: System makes 58+ OpenAI API calls in 8+ minutes, then fails with:
- `"cannot schedule new futures after shutdown"` 
- No research data retrieved
- 510 second timeout with complete failure

**Root Cause**: Infinite agent loop due to multiple cascading bugs.

## P0 CRITICAL FIXES (Complete System Failure)

### 1. Fix Agent Infinite Loop (BLOCKING - P0)
**File**: `src/agents/research_tavily_agent.py:250-269`  
**Issue**: Type mismatch causing infinite retry loop

**Problem**:
```python
# Agent expects ResearchPipelineModel output
tavily_research_agent = Agent(
    output_type=ResearchPipelineModel,  # Line 254
    # ...
)

# But tool returns dict, not ResearchPipelineModel
def perform_tavily_research() -> dict:  # Line 326
    return result_dict  # Line 575
```

**Fix**: Research agent tool must return `ResearchPipelineModel` object, not dict.

**Code Change**:
```python
# In perform_tavily_research() at line 575, replace:
return result_dict

# With:
return ResearchPipelineModel(
    original_query=query,
    sub_queries=sub_questions,
    results=cleaned_results,  # Already ResearchItem objects
    pipeline_type="tavily",
    total_results=len(cleaned_results),
    processing_time=0.0
)
```

### 2. Fix String Escaping Bug (BLOCKING - P0)
**File**: `src/agents/orchestrator_agent.py:793, 811`  
**Issue**: Query parsing fails due to string escaping mismatch

**Problem**:
```python
# Orchestrator sends (Line 793):
sub_queries_text = "\\\\n".join([...])  # Becomes literal \n in string

# But regex expects actual newlines (Line 356 in tavily agent):
r'Use these pre-generated sub-queries.*?:\\n((?:\\d+\\.\\s+.*\\n?)+)'
```

**Fix**: Use actual newlines, not escaped literals.

**Code Change**:
```python
# In dispatch_to_research_agents() at lines 793 and 811, replace:
sub_queries_text = "\\\\n".join([f"{i+1}. {q}" for i, q in enumerate(centralized_sub_queries)])

# With:
sub_queries_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(centralized_sub_queries)])
```

### 3. Apply Same Fixes to Serper Agent (BLOCKING - P0)
**File**: `src/agents/research_serper_agent.py`  
**Issue**: Same type mismatch and parsing bugs exist in Serper agent

**Fix**: Apply identical changes to Serper agent as done for Tavily agent above.

## P0 VERIFICATION FIXES (Previous Issues)

### 4. Fix Query Expansion Still Duplicating (P0)
**File**: `src/agents/research_tavily_agent.py:368-376`  
**Issue**: Despite centralization, agents still fall back to individual expansion

**Problem**: When regex parsing fails, agents use fallback expansion instead of single query.

**Fix**: Remove fallback expansion completely when centralized queries fail to parse.

**Code Change**:
```python
# At line 368, replace the entire else block:
else:
    # Enforce centralized queries unless explicitly allowed
    if not config.ALLOW_AGENT_QUERY_EXPANSION:
        sub_questions = [query]  # Use single query as fallback
        print(f"🎯 TAVILY TOOL DEBUG: Using single query fallback (regex parsing failed)")
    else:
        # REMOVE THIS FALLBACK - it causes duplication
        sub_questions = [query]  # Still use single query
        print(f"🎯 TAVILY TOOL DEBUG: Query expansion disabled, using single query")
```

### 5. Fix Over-Aggressive Garbage Filtering (P0)
**File**: `src/config.py` (GARBAGE_FILTER_THRESHOLD)  
**Issue**: 87.5-100% content rejection including quality sources

**Current**: `GARBAGE_FILTER_THRESHOLD = 0.4` (too restrictive)  
**Fix**: `GARBAGE_FILTER_THRESHOLD = 0.2` (more permissive)

### 6. Fix Data Pipeline Visibility Fields (P1)
**Files**: `src/models.py:87-94`, Research agents  
**Issue**: New visibility fields showing as null in state data

**Fix**: Ensure all research items properly populate:
- `pre_filter_content_length`
- `post_filter_content_length` 
- `garbage_filtered`
- `quality_score`

## P1 PERFORMANCE OPTIMIZATIONS

### 7. Verify Batched Content Cleaning (P1)
**File**: `src/agents/research_tavily_agent.py:460`  
**Issue**: Single item still takes 6.68 seconds

**Fix**: Verify `clean_multiple_contents_batched()` is actually batching calls, not processing sequentially.

### 8. Implement Parallel URL Scraping (P1)
**Files**: `src/agents/research_tavily_agent.py`, `research_serper_agent.py`  
**Enhancement**: Add concurrent URL scraping for better performance

## TESTING VERIFICATION

After implementing fixes:

1. **Integration Test**: Run wind energy query and verify:
   - Execution time < 60 seconds (vs current 510+ seconds)
   - No "cannot schedule new futures" errors
   - Research data successfully retrieved
   - < 10 total OpenAI API calls (vs current 58+)

2. **Query Expansion Test**: Verify logs show:
   - "Using X pre-generated sub-queries from orchestrator" 
   - NO "Generated X sub-questions" from individual agents
   - Sub-queries printed in both orchestrator and agent logs match exactly

3. **Garbage Filtering Test**: Verify:
   - Quality sources (*.gov, *.edu, established domains) pass filtering
   - Filtering rate drops from 87.5-100% to reasonable 20-40%
   - Visibility fields properly populated in state data

## CODE REVIEW CHECKLIST

- [ ] Agent `output_type` matches tool return type
- [ ] String escaping uses actual newlines, not literal `\n`
- [ ] Fallback query expansion removed from research agents
- [ ] Same fixes applied to both Tavily and Serper agents
- [ ] Garbage filter threshold reduced to 0.2
- [ ] Integration test passes with < 60 second execution

## ESTIMATED TIMELINE

- **P0 Fixes**: 2-4 hours (critical system repair)
- **P1 Optimizations**: 4-6 hours (performance improvements)
- **Testing & Verification**: 2-3 hours

**Total**: 8-13 hours for complete resolution

## SUCCESS CRITERIA

- ✅ System completes wind energy research in < 60 seconds
- ✅ No asyncio shutdown errors
- ✅ Research data successfully retrieved and processed
- ✅ < 10 total API calls per research request
- ✅ Quality content (gov/edu sources) passes garbage filtering
- ✅ All visibility fields properly populated in state data