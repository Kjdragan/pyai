#!/usr/bin/env python3
"""
Test runner script for the Pydantic-AI Multi-Agent System.
Provides convenient commands for running different test suites.
"""

import subprocess
import sys
import os
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle output."""
    print(f"\n🔄 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        print("Make sure pytest is installed: uv add --group test pytest")
        return False


def install_test_dependencies():
    """Install test dependencies."""
    print("📦 Installing test dependencies...")
    return run_command(
        ["uv", "add", "--group", "test", "pytest", "pytest-asyncio", "pytest-mock", "dirty-equals"],
        "Installing test dependencies"
    )


def run_unit_tests():
    """Run unit tests only."""
    return run_command(
        ["uv", "run", "pytest", "tests/test_models.py", "tests/test_agents.py", "-v", "-m", "not integration"],
        "Running unit tests"
    )


def run_integration_tests():
    """Run integration tests only."""
    return run_command(
        ["uv", "run", "pytest", "tests/test_integration.py", "-v"],
        "Running integration tests"
    )


def run_all_tests():
    """Run all tests."""
    return run_command(
        ["uv", "run", "pytest", "tests/", "-v"],
        "Running all tests"
    )


def run_tests_with_coverage():
    """Run tests with coverage report."""
    return run_command(
        ["uv", "run", "pytest", "tests/", "--cov=src", "--cov-report=html", "--cov-report=term-missing"],
        "Running tests with coverage"
    )


def run_specific_test(test_path):
    """Run a specific test file or test function."""
    return run_command(
        ["uv", "run", "pytest", test_path, "-v"],
        f"Running specific test: {test_path}"
    )


def lint_code():
    """Run code linting."""
    success = True
    
    # Run black
    if not run_command(["uv", "run", "black", "--check", "src/", "tests/"], "Checking code formatting with black"):
        success = False
    
    # Run isort
    if not run_command(["uv", "run", "isort", "--check-only", "src/", "tests/"], "Checking import sorting with isort"):
        success = False
    
    return success


def format_code():
    """Format code with black and isort."""
    success = True
    
    # Format with black
    if not run_command(["uv", "run", "black", "src/", "tests/"], "Formatting code with black"):
        success = False
    
    # Sort imports with isort
    if not run_command(["uv", "run", "isort", "src/", "tests/"], "Sorting imports with isort"):
        success = False
    
    return success


def check_types():
    """Run type checking with mypy."""
    return run_command(
        ["uv", "run", "mypy", "src/", "--ignore-missing-imports"],
        "Running type checking with mypy"
    )


def run_quick_test():
    """Run a quick smoke test to verify system works."""
    print("🚀 Running quick smoke test...")
    
    # Test model imports and basic functionality
    test_code = '''
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

try:
    from models import JobRequest, StreamingUpdate, MasterOutputModel
    from agents.orchestrator_agent import parse_job_request
    from config import config
    
    # Test model creation
    job = JobRequest(job_type="research", query="test", report_style="summary")
    print(f"✅ JobRequest created: {job.job_type}")
    
    # Test job parsing
    parsed = parse_job_request("Research AI trends")
    print(f"✅ Job parsing works: {parsed.job_type}")
    
    # Test config
    missing_keys = config.validate_required_keys()
    if missing_keys:
        print(f"⚠️  Missing API keys: {', '.join(missing_keys)}")
    else:
        print("✅ All API keys configured")
    
    print("✅ Smoke test passed - basic system functionality works")
    
except Exception as e:
    print(f"❌ Smoke test failed: {e}")
    sys.exit(1)
'''
    
    with open("smoke_test.py", "w") as f:
        f.write(test_code)
    
    try:
        result = subprocess.run(["uv", "run", "python", "smoke_test.py"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    finally:
        # Clean up
        if os.path.exists("smoke_test.py"):
            os.remove("smoke_test.py")


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test runner for Pydantic-AI Multi-Agent System")
    parser.add_argument("command", nargs="?", default="all", 
                       choices=["install", "unit", "integration", "all", "coverage", "lint", "format", "types", "quick"],
                       help="Test command to run")
    parser.add_argument("--test", "-t", help="Run specific test file or function")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print("🧪 Pydantic-AI Multi-Agent System - Test Runner")
    print("=" * 60)
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    success = True
    
    if args.command == "install":
        success = install_test_dependencies()
    elif args.command == "unit":
        success = run_unit_tests()
    elif args.command == "integration":
        success = run_integration_tests()
    elif args.command == "all":
        success = run_all_tests()
    elif args.command == "coverage":
        success = run_tests_with_coverage()
    elif args.command == "lint":
        success = lint_code()
    elif args.command == "format":
        success = format_code()
    elif args.command == "types":
        success = check_types()
    elif args.command == "quick":
        success = run_quick_test()
    elif args.test:
        success = run_specific_test(args.test)
    
    if success:
        print("\n🎉 All operations completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some operations failed. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
