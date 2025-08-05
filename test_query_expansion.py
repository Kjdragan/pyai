#!/usr/bin/env python3
"""
Test script for the enhanced query expansion functionality.
"""

import asyncio
import sys
import os

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.research_tavily_agent import expand_query_to_subquestions as tavily_expand
from agents.research_serper_agent import expand_query_to_subquestions as serper_expand

async def test_query_expansion():
    """Test the enhanced universal query expansion functionality."""
    test_queries = [
        # Product queries
        "iPhone 15 Pro",
        "Tesla Model 3",
        
        # Historical queries
        "Fall of Berlin Wall",
        "American Civil War",
        
        # Current news queries
        "2024 US election results",
        "latest AI developments",
        
        # Business/market queries
        "cryptocurrency market trends",
        "tech industry layoffs",
        
        # Scientific/general queries
        "quantum computing",
        "climate change solutions"
    ]
    
    print("Testing enhanced query expansion functionality")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\nOriginal query: {query}")
        
        # Test Tavily expansion
        tavily_subquestions = await tavily_expand(query)
        print("Tavily sub-questions:")
        for i, subq in enumerate(tavily_subquestions, 1):
            print(f"  {i}. {subq}")
        
        # Test Serper expansion
        serper_subquestions = await serper_expand(query)
        print("Serper sub-questions:")
        for i, subq in enumerate(serper_subquestions, 1):
            print(f"  {i}. {subq}")
        
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(test_query_expansion())
