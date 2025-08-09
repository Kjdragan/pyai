# Critical String Escaping Bug Pattern - Infinite Loop Root Cause

## The Deadly Mistake
**ALWAYS CHECK STRING ESCAPING FIRST** when debugging Pydantic-AI infinite loops with excessive API calls.

## Pattern Recognition
When you see:
- Infinite API call loops (25+ calls, 50+ calls, 100+ calls)
- Task names like "Task-XXX" or "dispatch_to_research_agents" repeating endlessly
- Agents making calls every 6-15 seconds without stopping
- No obvious type mismatches in agent output_type vs tool return types

**IMMEDIATELY CHECK FOR DOUBLE-ESCAPED NEWLINES** in f-string prompts.

## The Bug Pattern
```python
# ❌ WRONG - Creates literal \n characters instead of newlines
f"prompt text:\\n{variable}\\n"

# ✅ CORRECT - Creates actual newlines
f"prompt text:\n{variable}\n"
```

## Why This Causes Infinite Loops
1. Double-escaped newlines (`\\n`) create literal `\n` text in prompts
2. This corrupts the prompt structure and confuses the LLM
3. LLM returns malformed responses that fail Pydantic validation
4. Pydantic-AI retries infinitely due to validation failures
5. Results in 50-100+ API calls before system failure

## Historical Incidents
### August 8, 2025 - Multiple Occurrences
1. **First incident**: Lines 796, 839 in orchestrator_agent.py - fixed
2. **Second incident**: Lines 852, 894 in orchestrator_agent.py - caused hours of debugging

Both times, the double-escaped newlines (`\\n`) in f-strings caused:
- Task-111: 28+ API calls (Report Writer)  
- Task-150: 25+ API calls (first orchestrator bug)
- dispatch_to_research_agents: 100+ API calls (second orchestrator bug)

## Debugging Protocol
When investigating infinite loops:
1. **First**: Check all f-strings for `\\n` instead of `\n`
2. **Second**: Check agent output_type vs tool return type mismatches  
3. **Third**: Check for other validation issues

## Search Command to Find These Bugs
```bash
grep -r "\\\\n" src/agents/ --include="*.py"
```

This will reveal any f-strings with double-escaped newlines that could cause infinite loops.

## Why This is So Dangerous
- Hard to spot in code review (looks almost correct)
- Causes catastrophic system failure with massive API costs
- Symptoms point to complex agent coordination issues, not simple string bugs
- Hours of debugging chasing the wrong root cause
- Can occur anywhere f-strings are used in agent prompts

**REMEMBER**: String escaping bugs in agent prompts = infinite API call loops. Always check this first.