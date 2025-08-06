#!/usr/bin/env python3
"""
Debug script to test Logfire configuration and authentication.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import logfire
from config import config


async def test_logfire_configuration():
    """Test Logfire configuration and authentication."""
    
    print("🔧 Debugging Logfire Configuration")
    print("=" * 60)
    
    # Check environment variables
    print("\n📋 Environment Variables:")
    print(f"LOGFIRE_TOKEN: {'SET' if os.getenv('LOGFIRE_TOKEN') else 'NOT SET'}")
    print(f"LOGFIRE_READ_TOKEN: {'SET' if os.getenv('LOGFIRE_READ_TOKEN') else 'NOT SET'}")
    print(f"LOGFIRE_PROJECT_NAME: {os.getenv('LOGFIRE_PROJECT_NAME', 'NOT SET')}")
    print(f"LOGFIRE_ORG_NAME: {os.getenv('LOGFIRE_ORG_NAME', 'NOT SET')}")
    
    # Check credentials file
    credentials_file = Path("src/.logfire/logfire_credentials.json")
    print(f"\n📄 Credentials File:")
    print(f"Path: {credentials_file}")
    print(f"Exists: {credentials_file.exists()}")
    
    if credentials_file.exists():
        import json
        try:
            with open(credentials_file, 'r') as f:
                creds = json.load(f)
                print(f"Token in file: {creds.get('token', 'NOT FOUND')[:20]}...")
                print(f"Project name: {creds.get('project_name', 'NOT FOUND')}")
                print(f"Project URL: {creds.get('project_url', 'NOT FOUND')}")
        except Exception as e:
            print(f"Error reading credentials: {e}")
    
    # Check if tokens match
    env_token = os.getenv('LOGFIRE_TOKEN')
    try:
        with open(credentials_file, 'r') as f:
            file_creds = json.load(f)
            file_token = file_creds.get('token')
            
        print(f"\n🔍 Token Comparison:")
        print(f"Environment token: {env_token[:20]}...{env_token[-10:] if env_token else 'NONE'}")
        print(f"File token:        {file_token[:20]}...{file_token[-10:] if file_token else 'NONE'}")
        print(f"Tokens match: {env_token == file_token}")
        
    except Exception as e:
        print(f"Error comparing tokens: {e}")
    
    # Test Logfire configuration
    print(f"\n⚙️ Testing Logfire Configuration:")
    try:
        # Check the current working directory
        print(f"Current working directory: {os.getcwd()}")
        
        # Try to configure Logfire
        logfire.configure(
            send_to_logfire=True,
            token=env_token,
            service_name='pyai-debug-test',
            service_version='1.0.0'
        )
        print("✅ Logfire configuration succeeded")
        
        # Test a simple log message
        print("\n📝 Testing simple log message:")
        logfire.info("Test message from debug script", extra_data={"test": "value"})
        print("✅ Log message sent successfully")
        
        # Test instrumenting httpx
        print("\n🔧 Testing instrumentation:")
        logfire.instrument_httpx(capture_all=True)
        print("✅ HTTPX instrumentation configured")
        
        # Test Pydantic AI instrumentation
        logfire.instrument_pydantic_ai(event_mode='logs')
        print("✅ Pydantic AI instrumentation configured")
        
    except Exception as e:
        print(f"❌ Logfire configuration failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test simple HTTP request with tracing
    print(f"\n🌐 Testing HTTP request with tracing:")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("https://httpbin.org/json")
            print(f"✅ HTTP request successful: {response.status_code}")
    except Exception as e:
        print(f"❌ HTTP request failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_logfire_configuration())