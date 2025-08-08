import os
import pytest

from config import config
from agents.domain_classifier import domain_classifier, DomainClassificationService

ALLOWED_DOMAINS = {"technology", "business", "science", "news", "historical", "educational", "general"}


@pytest.mark.anyio
async def test_classify_domain_heuristic_mode(monkeypatch):
    # Force heuristic mode to avoid API calls
    monkeypatch.setattr(config, 'DOMAIN_CLASSIFIER_MODE', 'heuristic', raising=False)

    queries = [
        "AI model comparison",
        "stock market outlook",
        "basic physics tutorial",
        "latest news in space",
        "history of the Roman empire",
        "quick summary of cloud computing",
    ]

    for q in queries:
        result = await domain_classifier.classify_domain(q)
        assert isinstance(result, dict)
        assert result["domain"] in ALLOWED_DOMAINS
        assert result["complexity"] in {"low", "moderate", "high"}
        assert result["intent"] in {"informational", "instructional", "comparative", "predictive", "evaluative"}
        assert 0.0 <= float(result["domain_confidence"]) <= 1.0
        assert isinstance(result["query_length"], int)
        assert isinstance(result["technical_terms"], int)


@pytest.mark.anyio
async def test_get_enhanced_domain_context_async_heuristic(monkeypatch):
    # Ensure heuristic mode
    monkeypatch.setattr(config, 'DOMAIN_CLASSIFIER_MODE', 'heuristic', raising=False)

    ctx = await domain_classifier.get_enhanced_domain_context("youtube video about AI trends 2025")
    assert ctx["domain"] in ALLOWED_DOMAINS
    assert ctx["needs_youtube"] is True
    assert isinstance(ctx["needs_research"], bool)
    assert isinstance(ctx["needs_weather"], bool)
    assert isinstance(ctx["needs_report"], bool)
    assert ctx["confidence_score"] == ctx["domain_confidence"]


@pytest.mark.anyio
async def test_classify_domain_llm_live_api_if_key(monkeypatch):
    # Only run if OPENAI_API_KEY is set in environment; otherwise skip gracefully
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set; skipping live LLM domain classifier test")

    # Allow real model requests and ensure environment/config uses the real key
    try:
        from pydantic_ai import models as pyd_models
        pyd_models.ALLOW_MODEL_REQUESTS = True
    except Exception:
        pass

    # Ensure both env var and config are set so the SDK can find the key
    monkeypatch.setenv('OPENAI_API_KEY', api_key)
    monkeypatch.setattr(config, 'OPENAI_API_KEY', api_key, raising=False)
    # Provide a safe Nano model fallback for tests
    monkeypatch.setattr(config, 'NANO_MODEL', 'gpt-4o-mini', raising=False)
    monkeypatch.setattr(config, 'DOMAIN_CLASSIFIER_MODE', 'llm', raising=False)

    # Use a fresh service instance to avoid prior cached state
    service = DomainClassificationService(max_cache_size=10)

    q = "quantum computing advances 2025: error-corrected qubits"
    result = await service.classify_domain(q)

    assert isinstance(result, dict)
    assert result["domain"] in ALLOWED_DOMAINS
    assert 0.0 <= float(result["domain_confidence"]) <= 1.0
    assert isinstance(result.get("rationale"), str) and len(result["rationale"]) > 0

    # Call again to exercise cache path
    result2 = await service.classify_domain(q)
    assert result2 == result
