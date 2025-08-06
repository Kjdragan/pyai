# Task Completion Checklist

When completing any development task, ensure you follow these steps:

## Code Quality Checks
1. **Format Code**: `python run_tests.py format`
2. **Lint Check**: `python run_tests.py lint`  
3. **Type Check**: `python run_tests.py types`
4. **Run Tests**: `python run_tests.py all` or specific test suites

## Testing Requirements
- **Unit Tests**: Test individual agent functions
- **Integration Tests**: Test full agent workflows
- **Smoke Tests**: Quick validation of core functionality
- Ensure all tests pass before considering task complete

## Documentation Updates
- Update docstrings for any new/modified functions
- Update type hints
- Add relevant comments for complex logic
- No automatic README/documentation generation

## Environment Validation
- Ensure `.env` file has required API keys
- Test with actual API calls if modifying agents
- Verify Logfire traces are working if modifying observability

## Deployment Preparation
- Check that code runs in both CLI and web modes
- Validate configuration handling
- Ensure proper error handling and logging
- Test with realistic data/queries

## Agent-Specific Requirements
- **YouTube Agent**: Test with various YouTube URL formats
- **Weather Agent**: Test with different location formats
- **Research Agents**: Test with different query types
- **Report Agent**: Validate output formatting

## Observability Verification
- Check that Logfire traces appear in dashboard
- Validate structured logging output
- Ensure agent execution timing is captured