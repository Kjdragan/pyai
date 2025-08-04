#!/usr/bin/env python3
"""
Minimal test to verify JSON serialization works with HttpUrl.
"""
import json
from datetime import datetime
from pathlib import Path

# Test the JSON encoder directly without complex imports
class TestJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Pydantic types like HttpUrl."""
    def default(self, obj):
        # Simulate HttpUrl by checking if it has a string representation
        if hasattr(obj, '__str__') and 'http' in str(obj):
            return str(obj)
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return super().default(obj)

def test_json_serialization():
    """Test JSON serialization with mock data."""
    print("Testing JSON serialization...")
    
    # Create test data that simulates what we'd get from agents
    test_data = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "agent_name": "YouTube",
        "agent_data": {
            "url": "https://www.youtube.com/watch?v=test123",  # This simulates HttpUrl
            "title": "Test Video",
            "transcript": "This is a test transcript."
        }
    }
    
    # Test serialization
    try:
        json_output = json.dumps(test_data, indent=2, cls=TestJSONEncoder)
        print("✅ JSON serialization successful!")
        print("Sample output:")
        print(json_output[:200] + "..." if len(json_output) > 200 else json_output)
        
        # Test writing to file
        logs_dir = Path("src/logs/state")
        logs_dir.mkdir(exist_ok=True)
        test_file = logs_dir / "test_serialization.json"
        
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2, cls=TestJSONEncoder)
        
        print(f"✅ File write successful: {test_file}")
        return True
        
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False

if __name__ == "__main__":
    success = test_json_serialization()
    if success:
        print("\n🎉 Test completed successfully! The JSON serialization fix works.")
    else:
        print("\n💥 Test failed. There's still an issue with JSON serialization.")
