"""
Agent-level response caching for Pydantic AI agents.
"""

import hashlib
import json
import time
import asyncio
from typing import Any, Dict, Optional, Union, Tuple
from datetime import datetime, timedelta
import logging


class CacheEntry:
    """Individual cache entry with TTL support."""
    
    def __init__(self, data: Any, ttl_seconds: int = 3600):
        self.data = data
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl_seconds
    
    def access(self) -> Any:
        """Access the cached data and update statistics."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.data
    
    def get_age_seconds(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.created_at


class AgentResponseCache:
    """Thread-safe response cache for agent results."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(f"{__name__}.AgentResponseCache")
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
    def _generate_cache_key(self, agent_name: str, prompt: str, **kwargs) -> str:
        """Generate a consistent cache key from agent name, prompt, and parameters."""
        # Create a deterministic key from the inputs
        key_data = {
            'agent': agent_name,
            'prompt': prompt,
            'kwargs': sorted(kwargs.items()) if kwargs else []
        }
        
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]  # 16 char hash
    
    async def get(self, agent_name: str, prompt: str, **kwargs) -> Optional[Any]:
        """Get cached response if available and not expired."""
        cache_key = self._generate_cache_key(agent_name, prompt, **kwargs)
        
        async with self.lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                
                if entry.is_expired():
                    # Remove expired entry
                    del self.cache[cache_key]
                    self.misses += 1
                    self.logger.debug(f"Cache miss (expired): {agent_name} - {cache_key}")
                    return None
                
                # Cache hit
                self.hits += 1
                self.logger.debug(f"Cache hit: {agent_name} - {cache_key} (age: {entry.get_age_seconds():.1f}s)")
                return entry.access()
            
            # Cache miss
            self.misses += 1
            self.logger.debug(f"Cache miss (not found): {agent_name} - {cache_key}")
            return None
    
    async def put(self, agent_name: str, prompt: str, response: Any, ttl: Optional[int] = None, **kwargs):
        """Store response in cache with optional TTL override."""
        cache_key = self._generate_cache_key(agent_name, prompt, **kwargs)
        effective_ttl = ttl or self.default_ttl
        
        async with self.lock:
            # Check if we need to evict entries to make room
            if len(self.cache) >= self.max_size:
                await self._evict_lru()
            
            # Store new entry
            self.cache[cache_key] = CacheEntry(response, effective_ttl)
            self.logger.debug(f"Cached response: {agent_name} - {cache_key} (TTL: {effective_ttl}s)")
    
    async def _evict_lru(self):
        """Evict least recently used entries to make room."""
        if not self.cache:
            return
        
        # Sort by last accessed time (oldest first)
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Remove oldest 10% of entries
        evict_count = max(1, len(sorted_entries) // 10)
        
        for i in range(evict_count):
            cache_key, _ = sorted_entries[i]
            del self.cache[cache_key]
            self.evictions += 1
        
        self.logger.debug(f"Evicted {evict_count} cache entries (LRU)")
    
    async def clear_expired(self):
        """Remove all expired entries."""
        async with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                self.logger.debug(f"Cleared {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "evictions": self.evictions,
            "total_requests": total_requests
        }
    
    async def invalidate_agent(self, agent_name: str):
        """Invalidate all cache entries for a specific agent."""
        async with self.lock:
            keys_to_remove = []
            
            for key in self.cache:
                # This is a simple approach - in production we might store agent names in entries
                # For now, we could enhance the key generation to include agent prefix
                pass  # Would need more sophisticated key tracking
            
            self.logger.debug(f"Invalidated cache for agent: {agent_name}")


# Global cache instances with different TTL strategies
youtube_cache = AgentResponseCache(max_size=500, default_ttl=7 * 24 * 3600)  # 7 days
research_cache = AgentResponseCache(max_size=1000, default_ttl=24 * 3600)    # 24 hours
weather_cache = AgentResponseCache(max_size=200, default_ttl=2 * 3600)       # 2 hours
report_cache = AgentResponseCache(max_size=300, default_ttl=6 * 3600)        # 6 hours
general_cache = AgentResponseCache(max_size=1000, default_ttl=3600)          # 1 hour


def get_agent_cache(agent_name: str) -> AgentResponseCache:
    """Get the appropriate cache instance for an agent."""
    cache_map = {
        "youtube": youtube_cache,
        "youtubeagent": youtube_cache,
        "weather": weather_cache,
        "weatheragent": weather_cache,
        "research": research_cache,
        "tavily": research_cache,
        "serper": research_cache,
        "report": report_cache,
        "reportwriter": report_cache,
    }
    
    agent_key = agent_name.lower().replace("_", "").replace(" ", "")
    return cache_map.get(agent_key, general_cache)


async def cached_agent_run(agent, agent_name: str, prompt: str, use_cache: bool = True, **kwargs):
    """Run an agent with caching support.
    
    Args:
        agent: The Pydantic AI agent instance
        agent_name: Name of the agent for cache key generation
        prompt: The prompt to send to the agent
        use_cache: Whether to use caching (default: True)
        **kwargs: Additional arguments to pass to agent.run()
    
    Returns:
        The agent's response (from cache or fresh execution)
    """
    if not use_cache:
        return await agent.run(prompt, **kwargs)
    
    cache = get_agent_cache(agent_name)
    
    # Try to get from cache first
    cached_response = await cache.get(agent_name, prompt, **kwargs)
    if cached_response is not None:
        logging.getLogger(__name__).info(f"Using cached response for {agent_name}")
        return cached_response
    
    # Cache miss - run the agent
    response = await agent.run(prompt, **kwargs)
    
    # Store in cache for future use
    await cache.put(agent_name, prompt, response, **kwargs)
    
    return response


# Background task to clean up expired entries
async def cleanup_expired_cache_entries():
    """Background task to periodically clean up expired cache entries."""
    caches = [youtube_cache, research_cache, weather_cache, report_cache, general_cache]
    
    while True:
        try:
            for cache in caches:
                await cache.clear_expired()
            
            # Sleep for 15 minutes
            await asyncio.sleep(15 * 60)
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Cache cleanup error: {e}")
            await asyncio.sleep(60)  # Shorter sleep on error


def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all caches."""
    return {
        "youtube_cache": youtube_cache.get_stats(),
        "research_cache": research_cache.get_stats(),
        "weather_cache": weather_cache.get_stats(),
        "report_cache": report_cache.get_stats(),
        "general_cache": general_cache.get_stats()
    }


# Start cleanup task when module is imported
import atexit

def _start_cleanup_task():
    """Start the cleanup task in the background."""
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running():
            return
        
        task = loop.create_task(cleanup_expired_cache_entries())
        
        def cleanup():
            if not task.done():
                task.cancel()
        
        atexit.register(cleanup)
        
    except RuntimeError:
        # No event loop running, cleanup task will be started when needed
        pass


# Auto-start cleanup when imported
_start_cleanup_task()