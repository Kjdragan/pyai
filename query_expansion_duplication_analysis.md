# Query Expansion Duplication Analysis & Centralization Proposal

## Current Problem Analysis

### Code Duplication Identified

**Three separate implementations** of query expansion logic exist:

1. **`src/agents/query_expansion.py`** (Lines 25-102)
   - ✅ **Proper Implementation**: LLM-based agent with system prompts
   - ✅ **Instrumentation**: Has proper tracing (`instrument=True`)
   - ✅ **Error Handling**: Fallback to deterministic approach
   - ✅ **Reusability**: Designed as shared service

2. **`src/agents/research_tavily_agent.py`** (Lines 51-138) 
   - ❌ **Duplicate Logic**: 88 lines of redundant heuristic-based implementation
   - ❌ **Pattern Matching**: Uses hardcoded keyword detection (product, historical, news, business)
   - ❌ **Template Generation**: Simple string interpolation with limited intelligence
   - ❌ **Import Contradiction**: Imports from query_expansion but defines its own version

3. **`src/agents/research_serper_agent.py`** (Lines 61-136)
   - ❌ **Identical Duplicate**: Copy-paste of Tavily's implementation
   - ❌ **Same Issues**: Hardcoded patterns, template strings, no LLM intelligence

### Usage Patterns Analysis

```python
# Contradiction in Tavily agent:
from agents.query_expansion import expand_query_to_subquestions  # Import proper version

async def expand_query_to_subquestions(query: str) -> List[str]:  # Define duplicate version
    # 88 lines of duplicate logic...

# Called 3 times in Tavily:
sub_questions = await expand_query_to_subquestions(query)  # Which version executes?
```

### Impact Assessment

**Maintenance Overhead:**
- **3x Code Maintenance**: Changes must be applied to 3 locations
- **Inconsistent Behavior**: Different implementations may produce different results
- **Testing Complexity**: Must test 3 separate code paths

**Quality Issues:**
- **Heuristic vs LLM**: Dedicated agent uses intelligent LLM, duplicates use basic patterns
- **No Instrumentation**: Duplicate implementations lack tracing
- **Limited Context**: Hardcoded patterns vs contextual LLM understanding

**Performance Impact:**
- **Function Call Ambiguity**: Import shadows local definition (unclear which executes)
- **Code Size**: 200+ lines of redundant logic

## Recommended Solution Architecture

### Phase 1: Centralized Service Pattern

**Single Source of Truth Approach:**

```python
# Enhanced src/agents/query_expansion.py
class QueryExpansionService:
    """Centralized query expansion service with multiple strategies."""
    
    def __init__(self):
        self.llm_agent = query_expansion_agent
        self.fallback_strategies = {
            'product': ProductQueryStrategy(),
            'historical': HistoricalQueryStrategy(), 
            'business': BusinessQueryStrategy(),
            'news': NewsQueryStrategy(),
            'general': GeneralQueryStrategy()
        }
    
    async def expand_query(self, query: str, strategy: str = 'auto') -> List[str]:
        """Expand query with automatic strategy selection or forced strategy."""
        
        if strategy == 'auto':
            # Use LLM-based expansion (preferred)
            try:
                return await self._llm_expansion(query)
            except Exception:
                # Fallback to pattern-based if LLM fails
                return await self._pattern_expansion(query)
        else:
            # Use specific strategy (for testing/debugging)
            return await self._strategy_expansion(query, strategy)
    
    async def _llm_expansion(self, query: str) -> List[str]:
        """Primary LLM-based expansion with intelligent context."""
        result = await self.llm_agent.run(query)
        return result.data
    
    async def _pattern_expansion(self, query: str) -> List[str]:
        """Fallback pattern-based expansion."""
        strategy = self._detect_query_type(query)
        return self.fallback_strategies[strategy].expand(query)
    
    def _detect_query_type(self, query: str) -> str:
        """Intelligent query type detection."""
        # Consolidate the pattern detection logic from duplicates
```

### Phase 2: Implementation Strategy

**Step 1: Extract Common Logic**
- Move hardcoded patterns from duplicates to centralized strategies
- Create strategy classes for each query type (product, historical, etc.)
- Preserve existing behavior during transition

**Step 2: Remove Duplicates**
- Delete `expand_query_to_subquestions` from Tavily agent (Lines 51-138)
- Delete identical function from Serper agent (Lines 61-136)
- Update imports to use centralized service

**Step 3: Enhanced Integration**
```python
# In research agents:
from agents.query_expansion import query_expansion_service

# Replace direct function calls:
# OLD: sub_questions = await expand_query_to_subquestions(query)
# NEW: sub_questions = await query_expansion_service.expand_query(query)
```

### Benefits of Centralization

**Code Quality:**
- **Single Source of Truth**: One place to maintain expansion logic
- **LLM Intelligence**: All agents benefit from intelligent expansion
- **Consistent Results**: Same query always produces same sub-questions
- **Full Instrumentation**: Centralized tracing and monitoring

**Performance:**
- **Intelligent Fallback**: LLM primary, heuristic backup
- **Strategy Caching**: Cache expansion results for repeated queries
- **Reduced Code Size**: ~200 lines of duplicates eliminated

**Maintainability:**
- **Single Update Point**: Changes apply to all research agents
- **Better Testing**: Test centralized service instead of 3 implementations
- **Strategy Pattern**: Easy to add new query types (scientific, technical, etc.)

## Migration Risk Assessment

**Low Risk Factors:**
- ✅ **Existing Import Structure**: Agents already import from query_expansion
- ✅ **Backward Compatibility**: Can maintain same function signature
- ✅ **Gradual Migration**: Can replace agents one at a time

**Medium Risk Factors:**
- ⚠️ **Function Name Shadowing**: Local definitions override imports (current issue)
- ⚠️ **Behavior Changes**: LLM expansion may produce different results than heuristics

**Mitigation Strategy:**
1. **A/B Testing**: Run both implementations in parallel, log differences
2. **Gradual Rollout**: Replace one agent at a time, monitor results
3. **Fallback Safety**: Maintain heuristic strategies as backup
4. **Quality Gates**: Compare expansion quality before/after migration

## Recommendation

**Priority: HIGH** - This duplication creates maintenance overhead and inconsistent behavior.

**Approach: Phased Migration**
1. Create centralized service with enhanced capabilities
2. Remove duplicate implementations one agent at a time
3. Add quality monitoring to ensure no regression

**Timeline: 1-2 days**
- Day 1: Create centralized service, preserve all existing strategies
- Day 2: Remove duplicates, update imports, test integration

**Success Metrics:**
- ✅ Code reduction: ~200 lines eliminated
- ✅ Consistency: Same query produces same results across agents  
- ✅ Quality: LLM expansion improves sub-question intelligence
- ✅ Maintainability: Single point of change for expansion logic