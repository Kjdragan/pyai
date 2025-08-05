#!/usr/bin/env python3
"""
Simple test script to verify pytube functionality and debug metadata fetching.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_pytube_basic():
    """Test basic pytube functionality."""
    print("🧪 Testing pytube basic functionality...")
    
    try:
        from pytube import YouTube
        print("✅ pytube import successful")
        
        # Test URL from the logs
        test_url = "https://www.youtube.com/watch?v=IKdfXDrqNxk"
        print(f"🎬 Testing URL: {test_url}")
        
        # Create YouTube object
        yt = YouTube(test_url)
        print("✅ YouTube object created successfully")
        
        # Try to get metadata
        print(f"📺 Title: {yt.title}")
        print(f"👤 Author: {yt.author}")
        print(f"⏱️ Length: {yt.length} seconds")
        print(f"📅 Publish Date: {yt.publish_date}")
        print(f"👀 Views: {yt.views}")
        
        return True
        
    except Exception as e:
        print(f"❌ pytube test failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def test_alternative_urls():
    """Test with different YouTube URLs to see if it's URL-specific."""
    print("\n🧪 Testing alternative YouTube URLs...")
    
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - very stable
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # Me at the zoo - first YouTube video
    ]
    
    for url in test_urls:
        print(f"\n🎬 Testing URL: {url}")
        try:
            from pytube import YouTube
            yt = YouTube(url)
            print(f"✅ Title: {yt.title}")
            print(f"✅ Author: {yt.author}")
            print(f"✅ Length: {yt.length} seconds")
            return True
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    return False

def test_pytube_version():
    """Check pytube version and suggest alternatives."""
    print("\n🔍 Checking pytube version and alternatives...")
    
    try:
        import pytube
        print(f"📦 pytube version: {pytube.__version__}")
    except:
        print("❌ Could not get pytube version")
    
    # Test if yt-dlp is available as alternative
    try:
        import yt_dlp
        print(f"📦 yt-dlp available: {yt_dlp.version.__version__}")
        return True
    except ImportError:
        print("❌ yt-dlp not available")
        return False

def test_yt_dlp_alternative():
    """Test yt-dlp as an alternative to pytube."""
    print("\n🧪 Testing yt-dlp as alternative...")
    
    try:
        import yt_dlp
        
        test_url = "https://www.youtube.com/watch?v=IKdfXDrqNxk"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            
            print(f"✅ Title: {info.get('title', 'N/A')}")
            print(f"✅ Uploader: {info.get('uploader', 'N/A')}")
            print(f"✅ Duration: {info.get('duration', 'N/A')} seconds")
            print(f"✅ Upload Date: {info.get('upload_date', 'N/A')}")
            
            return True
            
    except ImportError:
        print("❌ yt-dlp not installed")
        return False
    except Exception as e:
        print(f"❌ yt-dlp test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 YouTube Metadata Fetching Test Suite")
    print("=" * 50)
    
    # Test 1: Basic pytube
    success_pytube = test_pytube_basic()
    
    # Test 2: Alternative URLs
    if not success_pytube:
        success_alt_urls = test_alternative_urls()
    else:
        success_alt_urls = True
    
    # Test 3: Check versions
    test_pytube_version()
    
    # Test 4: Try yt-dlp alternative
    success_yt_dlp = test_yt_dlp_alternative()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"  pytube basic: {'✅ PASS' if success_pytube else '❌ FAIL'}")
    print(f"  alternative URLs: {'✅ PASS' if success_alt_urls else '❌ FAIL'}")
    print(f"  yt-dlp alternative: {'✅ PASS' if success_yt_dlp else '❌ FAIL'}")
    
    if not success_pytube and not success_alt_urls:
        print("\n💡 Recommendations:")
        print("  1. Update pytube: pip install --upgrade pytube")
        print("  2. Try yt-dlp: pip install yt-dlp")
        print("  3. Check network/firewall settings")
        print("  4. Some videos may be region-restricted")
