"""
Centralized Domain Classification Service
Consolidates LLM and heuristic domain analysis to eliminate duplication.
"""

from typing import Dict, Any, Optional
from collections import OrderedDict
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from config import config
from models import DomainAnalysis


class DomainClassificationService:
    """
    Centralized service for query domain classification.
    Eliminates duplication between orchestrator and report writer.
    """
    
    def __init__(self, max_cache_size: int = 1000):
        # Build LLM classifier agent once for reuse
        self.llm_classifier = Agent(
            OpenAIModel(config.NANO_MODEL),
            instrument=True,
            output_type=DomainAnalysis,
            system_prompt="""
            You classify a short user query into a limited set of labels and return ONLY structured JSON per the schema.
            
            Allowed values:
            - domain: [technology, business, science, news, historical, educational, general]
            - complexity: [low, moderate, high]
            - intent: [informational, instructional, comparative, predictive, evaluative]
            - domain_confidence: 0.0..1.0
            - query_length: integer word count
            - technical_terms: integer count of technical terms (rough estimate)
            - secondary_domains: optional list of {name, confidence}
            - rationale: short one-sentence rationale
            """,
            retries=2
        )
        
        # Simple async-compatible LRU cache
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_cache_size = max_cache_size
    
    async def classify_domain(
        self, 
        query: str, 
        prefer_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Classify query domain using unified LLM/heuristic approach.
        
        Args:
            query: User query to classify
            prefer_llm: Whether to use LLM first (True) or heuristic only (False)
            
        Returns:
            Domain classification dict compatible with existing consumers
        """
        if not query or not query.strip():
            return self._get_default_classification()
        
        # Check cache first
        cache_key = query.strip().lower()
        if cache_key in self.cache:
            # Move to end (mark as recently used)
            self.cache.move_to_end(cache_key)
            return self.cache[cache_key]
        
        # Use LLM classification if preferred and available
        result = None
        if prefer_llm and getattr(config, "DOMAIN_CLASSIFIER_MODE", "llm").lower() == "llm":
            try:
                result = await self._classify_with_llm(query)
            except Exception as e:
                print(f"LLM domain classification failed: {e}, falling back to heuristic")
                
        # Fallback to heuristic classification if LLM failed
        if result is None:
            result = self._classify_with_heuristics(query)
        
        # Store in cache with LRU eviction
        self._store_in_cache(cache_key, result)
        
        return result
    
    def _store_in_cache(self, key: str, value: Dict[str, Any]) -> None:
        """Store result in LRU cache with size limits."""
        # Remove oldest items if cache is full
        while len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)  # Remove oldest (FIFO)
        
        self.cache[key] = value
    
    async def _classify_with_llm(self, query: str) -> Dict[str, Any]:
        """Use LLM agent for intelligent domain classification."""
        prompt = f"""
        Classify the following query and return ONLY JSON matching the schema:
        Query: "{query}"
        """
        
        result = await self.llm_classifier.run(prompt)
        analysis: DomainAnalysis = result.data if hasattr(result, 'data') else None
        
        if analysis:
            # Convert to dict format expected by consumers
            return {
                "domain": analysis.domain,
                "domain_confidence": float(analysis.domain_confidence),
                "complexity": analysis.complexity,
                "intent": analysis.intent,
                "query_length": int(analysis.query_length),
                "technical_terms": int(analysis.technical_terms),
                "secondary_domains": analysis.secondary_domains,
                "rationale": analysis.rationale,
            }
        else:
            # Fallback if LLM returned unexpected format
            return self._classify_with_heuristics(query)
    
    def _classify_with_heuristics(self, query: str) -> Dict[str, Any]:
        """Heuristic domain classification as fallback."""
        query_lower = query.lower()
        
        # Domain classification with confidence scores
        domain_scores = {
            "technology": self._count_keywords(query_lower, ["tech", "ai", "software", "digital", "innovation", "startup", "algorithm", "data", "cloud", "cybersecurity"]),
            "business": self._count_keywords(query_lower, ["business", "market", "economic", "finance", "industry", "competition", "strategy", "revenue", "profit", "investment"]),
            "science": self._count_keywords(query_lower, ["science", "research", "study", "scientific", "medical", "health", "climate", "environment", "biology", "physics"]),
            "news": self._count_keywords(query_lower, ["news", "current", "recent", "latest", "breaking", "update", "today", "yesterday", "2024", "2025"]),
            "historical": self._count_keywords(query_lower, ["history", "historical", "past", "evolution", "development", "origin", "timeline", "decade", "century"]),
            "educational": self._count_keywords(query_lower, ["how to", "tutorial", "guide", "learn", "explain", "understanding", "basics", "introduction"])
        }
        
        primary_domain = max(domain_scores.items(), key=lambda x: x[1])[0] if max(domain_scores.values()) > 0 else "general"
        domain_confidence = domain_scores[primary_domain] / len(query.split()) if len(query.split()) > 0 else 0.5
        
        # Complexity analysis
        complexity = "moderate"
        if any(indicator in query_lower for indicator in ["comprehensive", "detailed", "thorough", "deep", "analysis", "investigate"]):
            complexity = "high"
        elif any(indicator in query_lower for indicator in ["quick", "brief", "summary", "overview", "simple", "basic"]):
            complexity = "low"
        
        # Intent analysis
        intent = "informational"
        if any(word in query_lower for word in ["how to", "guide", "tutorial", "steps"]):
            intent = "instructional"
        elif any(word in query_lower for word in ["compare", "vs", "versus", "difference", "better"]):
            intent = "comparative"
        elif any(word in query_lower for word in ["predict", "future", "forecast", "trend", "outlook"]):
            intent = "predictive"
        elif any(word in query_lower for word in ["pros and cons", "advantages", "disadvantages", "benefits", "risks"]):
            intent = "evaluative"
        
        return {
            "domain": primary_domain,
            "domain_confidence": min(1.0, domain_confidence),
            "complexity": complexity,
            "intent": intent,
            "query_length": len(query.split()),
            "technical_terms": sum(1 for word in query_lower.split() if len(word) > 8),
            "secondary_domains": None,  # Could enhance this
            "rationale": f"Heuristic classification based on keyword analysis"
        }
    
    def _count_keywords(self, text: str, keywords: list) -> int:
        """Count keyword occurrences in text."""
        return sum(1 for word in keywords if word in text)
    
    def _get_default_classification(self) -> Dict[str, Any]:
        """Default classification for empty/invalid queries."""
        return {
            "domain": "general",
            "domain_confidence": 0.5,
            "complexity": "moderate",
            "intent": "informational",
            "query_length": 0,
            "technical_terms": 0,
            "secondary_domains": None,
            "rationale": "Default classification for empty query"
        }
    
    def get_enhanced_domain_context(self, query: str) -> Dict[str, Any]:
        """
        Get enhanced domain context for report generation.
        Replaces both orchestrator intent analysis and report writer domain analysis.
        """
        classification = self.classify_domain(query)
        
        # Enhance with additional context needed for report generation
        return {
            **classification,
            "needs_research": True,  # Most queries benefit from research
            "needs_youtube": "youtube" in query.lower() or "video" in query.lower(),
            "needs_weather": any(word in query.lower() for word in ["weather", "temperature", "forecast", "climate"]),
            "needs_report": any(word in query.lower() for word in ["report", "summary", "write", "document", "analyze"]),
            "confidence_score": classification["domain_confidence"],
            "research_rationale": f"Domain analysis suggests {classification['domain']} research needed",
            "youtube_url": None,  # Would be extracted separately
            "weather_location": None,  # Would be extracted separately
            "query_complexity": classification["complexity"]
        }


# Global service instance
domain_classifier = DomainClassificationService()