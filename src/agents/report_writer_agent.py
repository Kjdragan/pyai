"""
Report Writer Agent for generating and refining reports from research or YouTube data.
Supports comprehensive, top-10, and summary report styles.
"""

import asyncio
from typing import Union, Dict, Any, List, Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from datetime import datetime

from models import (
    ReportGenerationModel, ResearchPipelineModel, YouTubeTranscriptModel,
    AgentResponse, DomainAnalysis
)
from config import config
from agents.advanced_report_templates import (
    get_advanced_adaptive_template,
    get_style_config,
    template_engine
)
from agents.domain_classifier import domain_classifier


class ReportWriterDeps:
    """Dependencies for Report Writer Agent."""
    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT


# Cache is now handled by centralized domain_classifier service with LRU limits


def get_adaptive_report_template(style: str, query: str, data_types: List[str], domain_context: dict = None) -> str:
    """Get adaptive report template using advanced template engine.

    This function leverages the sophisticated template engine for domain-aware,
    query-adaptive report structures with intelligent section generation.
    """

    # Use domain context if provided, otherwise analyze query
    if domain_context is None:
        domain_context = analyze_query_domain(query)

    # Use advanced template engine for sophisticated template generation
    return get_advanced_adaptive_template(
        style=style,
        query=query,
        data_types=data_types,
        domain_context=domain_context
    )


def calculate_confidence_score(report: str, universal_data: 'UniversalReportData') -> float:
    """Calculate confidence score for report based on data quality and coverage."""
    confidence = 0.5  # Base confidence

    # Data source quality factors
    data_types = universal_data.get_data_types()

    if "research" in data_types and universal_data.research_data:
        research = universal_data.research_data
        # Higher confidence for more scraped content vs snippets
        scraped_ratio = sum(1 for item in research.results if item.content_scraped) / max(len(research.results), 1)
        confidence += scraped_ratio * 0.2

        # Higher confidence for more results
        if research.total_results >= 10:
            confidence += 0.1
        elif research.total_results >= 5:
            confidence += 0.05

    if "youtube" in data_types and universal_data.youtube_data:
        # Higher confidence for longer, more detailed content
        transcript_length = len(universal_data.youtube_data.transcript)
        if transcript_length > 10000:
            confidence += 0.15
        elif transcript_length > 5000:
            confidence += 0.1

    # Report quality factors
    report_length = len(report.split())
    if report_length > 1000:
        confidence += 0.1
    elif report_length > 500:
        confidence += 0.05

    # Multi-source bonus
    if len(data_types) > 1:
        confidence += 0.1

    # Ensure confidence is between 0 and 1
    return min(1.0, max(0.0, confidence))


# Legacy helper functions removed - functionality now provided by AdvancedReportTemplateEngine
# This improves code organization and maintainability


# Legacy function for backward compatibility
def get_report_template(style: str, source_type: str) -> str:
    """Legacy template function - maintained for backward compatibility."""
    # Convert to new system
    data_types = [source_type] if source_type in ["research", "youtube", "weather"] else ["research"]
    return get_adaptive_report_template(style, "general analysis", data_types)


async def generate_intelligent_report(
    universal_data: 'UniversalReportData',
    style: str,
    quality_level: str = "standard"
) -> str:
    """Generate intelligent report using adaptive templates and quality control.

    Args:
        universal_data: Universal data container with all available sources
        style: Report style (comprehensive, top_10, summary)
        quality_level: Quality control level (standard, enhanced, premium)
    """

    # Analyze query and generate adaptive template
    data_types = universal_data.get_data_types()
    # Prefer fast LLM classifier with fallback to heuristic
    domain_context = await classify_query_domain_llm(universal_data.query)

    template = get_adaptive_report_template(
        style=style,
        query=universal_data.query,
        data_types=data_types,
        domain_context=domain_context
    )

    # Select appropriate model based on complexity and quality requirements
    model_name = select_report_model(style, quality_level, len(data_types))

    # Create specialized generation agent with enhanced prompting
    generation_agent = Agent(
        OpenAIModel(model_name),
        instrument=True,
        system_prompt=create_intelligent_system_prompt(style, domain_context, data_types, quality_level),
        retries=3
    )

    # Build comprehensive content summary with intelligent structuring
    content_summary = build_intelligent_content_summary(universal_data, domain_context)

    # Generate report with context-aware prompting
    generation_prompt = create_generation_prompt(
        universal_data.query,
        content_summary,
        template,
        style,
        domain_context
    )

    # Generate initial report
    result = await generation_agent.run(generation_prompt)
    initial_report = result.data if hasattr(result, 'data') else str(result)

    # Apply quality enhancement if requested
    if quality_level in ["enhanced", "premium"]:
        enhanced_report = await apply_quality_enhancement(
            initial_report,
            universal_data,
            style,
            quality_level
        )
        return enhanced_report

    return initial_report


def analyze_query_domain(query: str) -> dict:
    """Analyze query to determine domain, complexity, and context."""
    query_lower = query.lower()

    # Domain classification with confidence scores
    domain_scores = {
        "technology": sum(1 for word in ["tech", "ai", "software", "digital", "innovation", "startup", "algorithm", "data", "cloud", "cybersecurity"] if word in query_lower),
        "business": sum(1 for word in ["business", "market", "economic", "finance", "industry", "competition", "strategy", "revenue", "profit", "investment"] if word in query_lower),
        "science": sum(1 for word in ["science", "research", "study", "scientific", "medical", "health", "climate", "environment", "biology", "physics"] if word in query_lower),
        "news": sum(1 for word in ["news", "current", "recent", "latest", "breaking", "update", "today", "yesterday", "2024", "2025"] if word in query_lower),
        "historical": sum(1 for word in ["history", "historical", "past", "evolution", "development", "origin", "timeline", "decade", "century"] if word in query_lower),
        "educational": sum(1 for word in ["how to", "tutorial", "guide", "learn", "explain", "understanding", "basics", "introduction"] if word in query_lower)
    }

    primary_domain = max(domain_scores.items(), key=lambda x: x[1])[0] if max(domain_scores.values()) > 0 else "general"

    # Complexity analysis
    complexity_indicators = {
        "high": ["comprehensive", "detailed", "thorough", "deep", "analysis", "investigate", "research", "examine", "explore"],
        "low": ["quick", "brief", "summary", "overview", "simple", "basic", "intro", "what is"]
    }

    complexity = "moderate"
    for level, indicators in complexity_indicators.items():
        if any(indicator in query_lower for indicator in indicators):
            complexity = level
            break

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
        "domain_confidence": domain_scores[primary_domain] / len(query.split()) if len(query.split()) > 0 else 0,
        "complexity": complexity,
        "intent": intent,
        "query_length": len(query.split()),
        "technical_terms": sum(1 for word in query_lower.split() if len(word) > 8)  # Rough technical complexity indicator
    }


async def classify_query_domain_llm(query: str) -> Dict[str, Any]:
    """
    DEPRECATED: Wrapper for backward compatibility.
    Use domain_classifier.classify_domain() directly for new code.
    """
    return await domain_classifier.classify_domain(query)


def select_report_model(style: str, quality_level: str, data_source_count: int) -> str:
    """Select appropriate model based on report requirements."""
    if quality_level == "premium" or (style == "comprehensive" and data_source_count > 1):
        return config.STANDARD_MODEL  # High-quality model for complex reports
    elif quality_level == "enhanced" or style == "comprehensive":
        return config.DEFAULT_MODEL  # Balanced model
    else:
        return config.NANO_MODEL  # Fast model for simple reports


def create_intelligent_system_prompt(style: str, domain_context: dict, data_types: List[str], quality_level: str) -> str:
    """Create context-aware system prompt for report generation."""
    domain = domain_context["domain"]
    complexity = domain_context["complexity"]
    intent = domain_context["intent"]

    base_prompt = f"""
    You are an expert {domain} analyst and report writer specializing in {style} reports.

    DOMAIN EXPERTISE: {domain.title()} Analysis
    COMPLEXITY LEVEL: {complexity.title()}
    INTENT: {intent.title()} Analysis
    DATA SOURCES: {', '.join(data_types)}
    QUALITY LEVEL: {quality_level.title()}

    CORE RESPONSIBILITIES:
    1. Generate publication-ready {style} reports with domain-specific insights
    2. Synthesize information across multiple data sources intelligently
    3. Provide quantified insights with supporting evidence
    4. Ensure actionable recommendations appropriate to the domain
    5. Maintain analytical rigor and factual accuracy

    DOMAIN-SPECIFIC REQUIREMENTS:
    """

    # Add domain-specific guidance
    if domain == "technology":
        base_prompt += """
    - Focus on technical feasibility, scalability, and innovation impact
    - Include performance metrics, adoption rates, and market dynamics
    - Address security, compliance, and implementation considerations
    - Provide technology roadmap insights where relevant
    """
    elif domain == "business":
        base_prompt += """
    - Emphasize market opportunity, competitive analysis, and ROI
    - Include financial implications and risk assessment
    - Address strategic positioning and operational considerations
    - Provide actionable business recommendations
    """
    elif domain == "science":
        base_prompt += """
    - Focus on research methodology, statistical significance, and validity
    - Include peer review status and replication considerations
    - Address broader scientific and societal implications
    - Provide evidence-based conclusions with confidence intervals
    """

    # Add quality-specific requirements
    if quality_level == "premium":
        base_prompt += """

    PREMIUM QUALITY STANDARDS:
    - Provide executive-level insights with strategic implications
    - Include confidence levels and uncertainty analysis
    - Cross-reference findings across multiple sources
    - Offer forward-looking predictions with supporting rationale
    - Ensure all claims are substantiated with evidence
    """
    elif quality_level == "enhanced":
        base_prompt += """

    ENHANCED QUALITY STANDARDS:
    - Provide detailed analysis with supporting evidence
    - Include multiple perspectives where relevant
    - Offer specific, measurable recommendations
    - Connect findings to broader context and implications
    """

    base_prompt += """

    OUTPUT REQUIREMENTS:
    - Follow the template structure precisely while adapting content intelligently
    - Use clear, professional language appropriate for the target domain
    - Include specific data points, metrics, and quantifiable insights
    - Ensure logical flow and coherent argumentation throughout
    - Provide publication-ready quality (no draft language)
    """

    return base_prompt


def build_intelligent_content_summary(universal_data: 'UniversalReportData', domain_context: dict) -> str:
    """Build intelligent content summary optimized for report generation."""
    summary_parts = []

    # Add query context
    summary_parts.append(f"ANALYSIS REQUEST: {universal_data.query}")
    summary_parts.append(f"DOMAIN CONTEXT: {domain_context['domain'].title()} ({domain_context['intent']} analysis)")
    summary_parts.append(f"COMPLEXITY: {domain_context['complexity'].title()}")
    summary_parts.append("")

    # YouTube data processing
    if universal_data.youtube_data:
        yt_data = universal_data.youtube_data
        summary_parts.append("=== VIDEO CONTENT ANALYSIS ===")
        summary_parts.append(f"Title: {yt_data.title or 'Unknown Title'}")
        summary_parts.append(f"Channel: {yt_data.channel or 'Unknown Channel'}")
        summary_parts.append(f"Duration: {yt_data.duration or 'Unknown'} | URL: {yt_data.url}")

        # Intelligent transcript processing
        transcript = yt_data.transcript
        if len(transcript) > 12000:
            # Extract key segments for very long transcripts
            transcript_preview = extract_key_transcript_segments(transcript, domain_context)
            summary_parts.append(f"Transcript (Key Segments from {len(transcript)} chars):")
            summary_parts.append(transcript_preview)
        else:
            summary_parts.append(f"Full Transcript ({len(transcript)} chars):")
            summary_parts.append(transcript)
        summary_parts.append("")

    # Research data processing
    if universal_data.research_data:
        research = universal_data.research_data
        summary_parts.append("=== RESEARCH FINDINGS ===")
        summary_parts.append(f"Original Query: {research.original_query}")
        summary_parts.append(f"Sub-queries: {', '.join(research.sub_queries)}")
        summary_parts.append(f"Total Results: {research.total_results} from {research.pipeline_type}")
        summary_parts.append("")

        # Prioritize results by relevance and content quality
        prioritized_results = prioritize_research_results(research.results, domain_context)

        for i, item in enumerate(prioritized_results[:10], 1):  # Top 10 results
            content = item.scraped_content if (item.content_scraped and item.scraped_content) else item.snippet
            content = content[:800] + "..." if len(content) > 800 else content

            quality_indicator = "[FULL CONTENT]" if item.content_scraped else "[SNIPPET]"
            relevance_indicator = f"[REL: {item.relevance_score:.2f}]" if item.relevance_score else ""

            summary_parts.append(f"{i}. {item.title} {quality_indicator} {relevance_indicator}")
            summary_parts.append(f"   Source: {item.source_url}")
            summary_parts.append(f"   Content: {content}")
            summary_parts.append("")

    # Weather data processing
    if universal_data.weather_data:
        weather = universal_data.weather_data
        summary_parts.append("=== WEATHER DATA ===")
        summary_parts.append(f"Location: {weather.location}")
        summary_parts.append(f"Current: {weather.current.temp}°C, {weather.current.description}")
        if weather.forecast:
            summary_parts.append(f"Forecast: {len(weather.forecast)} periods available")
        summary_parts.append("")

    return "\n".join(summary_parts)


def extract_key_transcript_segments(transcript: str, domain_context: dict) -> str:
    """Extract key segments from long transcripts based on domain context."""
    # Simple keyword-based extraction - could be enhanced with NLP
    domain = domain_context["domain"]

    # Domain-specific keywords for segment extraction
    keywords_map = {
        "technology": ["innovation", "development", "technology", "solution", "system", "algorithm", "data", "performance"],
        "business": ["market", "business", "strategy", "revenue", "profit", "customer", "competition", "growth"],
        "science": ["research", "study", "results", "findings", "evidence", "analysis", "method", "conclusion"],
        "general": ["important", "key", "main", "significant", "critical", "essential", "primary"]
    }

    keywords = keywords_map.get(domain, keywords_map["general"])

    # Extract segments around keywords (simple implementation)
    sentences = transcript.split('. ')
    key_segments = []

    for i, sentence in enumerate(sentences):
        if any(keyword in sentence.lower() for keyword in keywords):
            # Extract context around keyword sentences
            start_idx = max(0, i - 1)
            end_idx = min(len(sentences), i + 2)
            segment = '. '.join(sentences[start_idx:end_idx])
            key_segments.append(segment)

    # Take top segments and ensure reasonable length
    if key_segments:
        combined = ' [...] '.join(key_segments[:8])  # Top 8 segments
        return combined[:8000] + "..." if len(combined) > 8000 else combined
    else:
        # Fallback to beginning and end if no keywords found
        return transcript[:4000] + " [...] " + transcript[-4000:] if len(transcript) > 8000 else transcript


def prioritize_research_results(results: List['ResearchItem'], domain_context: dict) -> List['ResearchItem']:
    """Prioritize research results based on relevance and quality."""
    def score_result(item: 'ResearchItem') -> float:
        score = 0.0

        # Base relevance score
        if item.relevance_score:
            score += item.relevance_score * 10

        # Content quality bonus
        if item.content_scraped and item.scraped_content:
            score += 5.0
            # Length bonus for substantial content
            content_length = len(item.scraped_content)
            if content_length > 1000:
                score += min(2.0, content_length / 2000)  # Up to 2 points for length

        # Domain relevance bonus
        domain = domain_context["domain"]
        title_lower = item.title.lower()
        content_lower = (item.scraped_content or item.snippet).lower()

        domain_keywords = {
            "technology": ["tech", "digital", "software", "innovation", "ai", "algorithm"],
            "business": ["market", "business", "economic", "financial", "industry", "strategy"],
            "science": ["research", "study", "scientific", "analysis", "findings", "evidence"]
        }.get(domain, [])

        domain_score = sum(1 for keyword in domain_keywords if keyword in title_lower or keyword in content_lower)
        score += domain_score * 0.5

        # Recency bonus (if timestamp available)
        if item.timestamp:
            # This is a simplified recency calculation
            score += 1.0

        return score

    # Sort by score (highest first)
    return sorted(results, key=score_result, reverse=True)


def create_generation_prompt(query: str, content_summary: str, template: str, style: str, domain_context: dict) -> str:
    """Create intelligent generation prompt for report creation."""
    domain = domain_context["domain"]
    complexity = domain_context["complexity"]
    intent = domain_context["intent"]

    prompt = f"""
    Generate a {style} {domain} analysis report that addresses this query: "{query}"

    ANALYTICAL FRAMEWORK:
    - Intent: {intent.title()} analysis
    - Complexity: {complexity.title()} level treatment
    - Domain: {domain.title()} expertise required

    CONTENT TO ANALYZE:
    {content_summary}

    TEMPLATE STRUCTURE TO FOLLOW:
    {template}

    QUALITY REQUIREMENTS:
    1. Extract quantifiable insights and metrics from the source data
    2. Provide domain-specific analysis and recommendations
    3. Ensure all claims are supported by evidence from the source material
    4. Create coherent narrative flow between all sections
    5. Include forward-looking insights where appropriate
    6. Use professional, publication-ready language throughout

    CRITICAL SUCCESS FACTORS:
    - Answer the original query comprehensively and directly
    - Synthesize insights across all available data sources
    - Provide actionable recommendations specific to the {domain} domain
    - Include confidence levels for predictions and recommendations
    - Maintain analytical rigor while ensuring readability

    Generate the complete report now, following the template structure exactly while adapting content intelligently to the query and domain context.
    """

    return prompt


async def apply_quality_enhancement(
    initial_report: str,
    universal_data: 'UniversalReportData',
    style: str,
    quality_level: str
) -> str:
    """Apply quality enhancement and validation to initial report."""

    if quality_level == "premium":
        # Premium quality: Multiple enhancement passes
        enhanced_report = await enhance_report_structure(initial_report, universal_data)
        validated_report = await validate_report_claims(enhanced_report, universal_data)
        final_report = await add_executive_insights(validated_report, universal_data, style)
        return final_report
    elif quality_level == "enhanced":
        # Enhanced quality: Single enhancement pass
        enhanced_report = await enhance_report_structure(initial_report, universal_data)
        return enhanced_report
    else:
        return initial_report


async def enhance_report_structure(report: str, universal_data: 'UniversalReportData') -> str:
    """Enhance report structure and flow."""
    enhancement_agent = Agent(
        OpenAIModel(config.DEFAULT_MODEL),
        instrument=True,
        system_prompt="""
        You are an expert editor specializing in report enhancement and structural improvement.
        
        Your task is to enhance the provided report by:
        1. Improving logical flow and transitions between sections
        2. Strengthening arguments with better evidence integration
        3. Adding quantitative insights where appropriate
        4. Enhancing readability while maintaining analytical depth
        5. Ensuring consistent professional tone throughout
        6. Integrating a few short, highly relevant verbatim quotes from the provided source material to enrich key points
           - Always attribute quotes inline to the speaker's name if available; otherwise use their title/role or the source title
           - Do NOT fabricate quotes; only quote exact text found in the source material
           - Keep quotes concise (typically 10–30 words) and only where it improves clarity or credibility
           - If a speaker name is unknown (e.g., from a YouTube transcript), attribute to the channel host or use a clear title (e.g., "Host, {channel}")
           - For research items without a clear speaker, attribute to the article/source title
        
        Maintain all original content and structure while improving quality and coherence. Add quotes sparingly and naturally within the narrative.
        Return only the enhanced report.
        """,
        retries=2
    )
    
    # Prepare source material to enable safe, attributed quote insertion
    source_context_parts: List[str] = []
    try:
        if universal_data.youtube_data:
            yt = universal_data.youtube_data
            source_context_parts.append(f"YouTube: {yt.title or 'Unknown Title'} | Channel: {yt.channel or 'Unknown Channel'} | URL: {yt.url}")
            # Provide transcript for exact-quote extraction (trim to protect context window)
            source_context_parts.append("Transcript (truncated):")
            source_context_parts.append((yt.transcript or "")[:6000])
        if universal_data.research_data:
            research = universal_data.research_data
            source_context_parts.append("Research Sources (top items, truncated):")
            # Use LLM classifier domain context for prioritization
            domain_ctx_for_priority = await classify_query_domain_llm(universal_data.query)
            for item in prioritize_research_results(research.results, domain_ctx_for_priority)[:5]:
                source_line = f"- {item.title} | {item.source_url or 'N/A'}"
                source_context_parts.append(source_line)
                content = (item.scraped_content or item.snippet or "")
                if content:
                    excerpt = content[:1200]
                    source_context_parts.append(f"  Excerpt: \"{excerpt}\"")
    except Exception:
        # Fail-soft: if any issue occurs, proceed without source context
        pass
    source_context = "\n".join(source_context_parts) if source_context_parts else "(No additional source material available)"

    prompt = f"""
    Please enhance this report for better structure, flow, and impact. Where it genuinely improves clarity or credibility, insert 2–4 short verbatim quotes with inline attribution (speaker name or title/source). Never fabricate quotes—use only exact text present in the source material below.
    
    REPORT:
    {report}
    
    SOURCE MATERIAL (for exact-quote extraction and attribution):
    {source_context}
    
    Focus on improving coherence, strengthening arguments, and enhancing professional presentation while maintaining all original insights and structure. Add quotes sparingly and ensure attributions are clear in the text.
    """
    
    result = await enhancement_agent.run(prompt)
    return result.data if hasattr(result, 'data') else str(result)

async def validate_report_claims(report: str, universal_data: 'UniversalReportData') -> str:
    """Validate report claims against source data."""
    validation_agent = Agent(
        OpenAIModel(config.STANDARD_MODEL),
        instrument=True,
        system_prompt="""
        You are a source-alignment reviewer for analytical reports.
        
        PRINCIPLES:
        - Assume the provided research and transcripts are credible; do not re-judge credibility.
        - Preserve the report's existing content, tone, and structure. Make minimal edits only.
        - Ensure statements align with the provided source material and are not altered to fit a desired narrative.
        - Do not add or delete substantive text solely to push a narrative.
        - Prefer inclusion over omission: add concise inline citations or parenthetical source notes rather than rewriting.
        - For statements you cannot verify in the provided sources, add a brief bracketed note (e.g., [source not found in provided materials]) next to the sentence; do not remove it.
        - Keep any quotes verbatim; never fabricate quotes or paraphrase as direct quotes.
        
        OUTPUT:
        - Return the report with only minimal inline citations/notes where needed. Avoid large rewrites.
        """,
        retries=2
    )

    primary_content = universal_data.get_primary_content()

    prompt = f"""
    Please perform a light-touch source alignment review.
    
    REPORT TO REVIEW:
    {report}
    
    SOURCE MATERIAL:
    {primary_content[:5000]}  # Truncate for context window
    
    Instructions:
    - Assume sources are credible.
    - Do not rewrite to fit a desired narrative.
    - Preserve content and structure; make only minimal edits.
    - Where helpful, add short inline citations (e.g., (Source: Title) or [Source: URL]).
    - If a claim lacks clear support in the provided material, add a brief bracketed note next to it; do not delete the claim.
    """

    result = await validation_agent.run(prompt)
    return result.data if hasattr(result, 'data') else str(result)


async def add_executive_insights(report: str, universal_data: 'UniversalReportData', style: str) -> str:
    """Add executive-level insights and strategic recommendations."""
    insights_agent = Agent(
        OpenAIModel(config.STANDARD_MODEL),
        instrument=True,
        system_prompt="""
        You are a senior executive consultant specializing in strategic insights and recommendations.

        Your task is to enhance the report with:
        1. Executive-level strategic insights
        2. High-level implications and consequences
        3. Strategic recommendations for leadership
        4. Risk assessment and mitigation strategies
        5. Competitive and market implications

        Add these insights while maintaining the original report structure and content.
        """,
        retries=2
    )

    prompt = f"""
    Please enhance this {style} report with executive-level strategic insights:

    {report}

    Add strategic implications, leadership recommendations, and high-level insights while preserving the original structure and analysis.
    """

    result = await insights_agent.run(prompt)
    return result.data if hasattr(result, 'data') else str(result)


# Legacy function maintained for compatibility
async def generate_complete_report(
    data: Union[ResearchPipelineModel, YouTubeTranscriptModel],
    style: str,
    template: str
) -> str:
    """Legacy report generation function - maintained for backward compatibility."""
    # Convert legacy data to universal format
    from models import UniversalReportData

    if isinstance(data, ResearchPipelineModel):
        universal_data = UniversalReportData(
            query=data.original_query,
            research_data=data
        )
    else:  # YouTubeTranscriptModel
        universal_data = UniversalReportData(
            query=data.metadata.get("title", "YouTube Analysis"),
            youtube_data=data
        )

    # Use new intelligent system
    return await generate_intelligent_report(universal_data, style, "standard")


# Create Report Writer Agent with instrumentation
report_writer_agent = Agent(
    model=OpenAIModel(config.REPORT_MODEL),
    deps_type=ReportWriterDeps,
    output_type=ReportGenerationModel,
    instrument=True,  # Enable Pydantic AI tracing
    system_prompt="""
    You are a professional report writer agent. Your job is to:
    1. Ingest research data or YouTube transcript data
    2. Generate reports in specified styles (comprehensive, top-10, summary)
    3. Apply synthesis and editing loops to refine the output
    4. Return high-quality, structured reports

    Always follow the appropriate template for the requested style and source type.
    Ensure reports are well-structured, insightful, and actionable.
    """,
    retries=config.MAX_RETRIES
)


@report_writer_agent.tool
async def generate_intelligent_report_tool(
    ctx: RunContext[ReportWriterDeps],
    query: str,
    data_sources: str,
    style: str = "summary",
    quality_level: str = "standard"
) -> ReportGenerationModel:
    """Tool to generate intelligent report with adaptive templates and quality control.

    Args:
        query: Original user query for context
        data_sources: JSON string containing available data sources
        style: Report style (comprehensive, top_10, summary)
        quality_level: Quality control level (standard, enhanced, premium)
    """
    try:
        import json
        from models import UniversalReportData, ResearchPipelineModel, YouTubeTranscriptModel

        # Parse data sources
        data_dict = json.loads(data_sources)

        # Create universal data container
        universal_data = UniversalReportData(query=query)

        # Populate data sources
        if "research_data" in data_dict and data_dict["research_data"]:
            universal_data.research_data = ResearchPipelineModel(**data_dict["research_data"])

        if "youtube_data" in data_dict and data_dict["youtube_data"]:
            universal_data.youtube_data = YouTubeTranscriptModel(**data_dict["youtube_data"])

        if "weather_data" in data_dict and data_dict["weather_data"]:
            from models import WeatherModel
            universal_data.weather_data = WeatherModel(**data_dict["weather_data"])

        # Validate data availability
        if not universal_data.has_data():
            # Return minimal ReportGenerationModel for error case
            return ReportGenerationModel(
                style=style,
                prompt_template="Error template",
                draft="No valid data sources provided",
                final="Error: No valid data sources provided for report generation",
                source_type="multi_source",
                quality_level=quality_level,
                word_count=0,
                generation_time=0.0,
                confidence_score=0.0
            )

        # Generate report
        response = await process_intelligent_report_request(
            universal_data=universal_data,
            style=style,
            quality_level=quality_level
        )

        if response.success:
            # Extract ReportGenerationModel from response.data
            report_data = response.data
            if isinstance(report_data, dict) and 'report_model' in report_data:
                # Return the actual ReportGenerationModel
                return report_data['report_model']
            else:
                # Construct minimal ReportGenerationModel from available data
                return ReportGenerationModel(
                    style=style,
                    prompt_template="Generated template",
                    draft="Generated draft content",
                    final=report_data.get('final', 'Generated report content') if isinstance(report_data, dict) else str(report_data),
                    source_type="multi_source",
                    quality_level=quality_level,
                    word_count=report_data.get('word_count', 0) if isinstance(report_data, dict) else 0,
                    generation_time=response.processing_time,
                    confidence_score=report_data.get('confidence_score', 0.8) if isinstance(report_data, dict) else 0.8,
                    data_sources_count=len(universal_data.get_data_types())
                )
        else:
            # Return ReportGenerationModel for error case
            return ReportGenerationModel(
                style=style,
                prompt_template="Error template",
                draft="Report generation failed",
                final=f"Error generating report: {response.error}",
                source_type="multi_source",
                quality_level=quality_level,
                word_count=0,
                generation_time=response.processing_time or 0.0,
                confidence_score=0.0
            )

    except Exception as e:
        # Return ReportGenerationModel for exception case
        return ReportGenerationModel(
            style=style,
            prompt_template="Error template",
            draft="Exception occurred during generation",
            final=f"Error in intelligent report generation: {str(e)}",
            source_type="multi_source",
            quality_level=quality_level,
            word_count=0,
            generation_time=0.0,
            confidence_score=0.0
        )


# Legacy tool maintained for backward compatibility
@report_writer_agent.tool
async def generate_report(
    ctx: RunContext[ReportWriterDeps],
    data_json: str,
    style: str,
    source_type: str
) -> ReportGenerationModel:
    """Legacy tool for report generation - maintained for backward compatibility."""
    try:
        # Get appropriate template (legacy)
        template = get_report_template(style, source_type)

        # Return minimal ReportGenerationModel for legacy tool
        return ReportGenerationModel(
            style=style,
            prompt_template=template,
            draft="Legacy tool generated draft",
            final=f"Successfully generated {style} report template for {source_type} data. Template includes {len(template.split('##'))} main sections.",
            source_type=source_type,
            quality_level="standard",
            word_count=len(template.split()),
            generation_time=0.1,
            confidence_score=0.7
        )

    except Exception as e:
        # Return ReportGenerationModel for error case
        return ReportGenerationModel(
            style=style,
            prompt_template="Error template",
            draft="Error occurred",
            final=f"Error generating report: {str(e)}",
            source_type=source_type,
            quality_level="standard",
            word_count=0,
            generation_time=0.0,
            confidence_score=0.0
        )


async def process_intelligent_report_request(
    universal_data: 'UniversalReportData',
    style: str = "summary",
    quality_level: str = "standard"
) -> AgentResponse:
    """Process intelligent report generation request with adaptive templates and quality control."""
    start_time = asyncio.get_event_loop().time()

    try:
        # Generate intelligent report
        final_report = await generate_intelligent_report(
            universal_data=universal_data,
            style=style,
            quality_level=quality_level
        )

        # Analyze report quality metrics
        word_count = len(final_report.split())
        data_types = universal_data.get_data_types()
        domain_context = await classify_query_domain_llm(universal_data.query)

        # Generate adaptive template for metadata
        template = get_adaptive_report_template(
            style=style,
            query=universal_data.query,
            data_types=data_types,
            domain_context=domain_context
        )

        # Determine source type for compatibility
        if len(data_types) == 1:
            source_type = data_types[0]
        else:
            source_type = "multi_source"

        # Create enhanced result model with new fields
        result = ReportGenerationModel(
            style=style,
            prompt_template=template[:1000] + "..." if len(template) > 1000 else template,  # Truncate for storage
            draft=f"[Intelligent generation - {quality_level} quality level]",
            final=final_report,
            source_type=source_type,
            word_count=word_count,
            generation_time=asyncio.get_event_loop().time() - start_time,
            # Enhanced fields
            quality_level=quality_level,
            domain_context=domain_context,
            confidence_score=calculate_confidence_score(final_report, universal_data),
            data_sources_count=len(data_types),
            enhancement_applied=quality_level in ["enhanced", "premium"]
        )

        processing_time = asyncio.get_event_loop().time() - start_time

        return AgentResponse(
            agent_name="IntelligentReportWriter",
            success=True,
            data=result.model_dump(),
            processing_time=processing_time
        )

    except Exception as e:
        processing_time = asyncio.get_event_loop().time() - start_time
        return AgentResponse(
            agent_name="IntelligentReportWriter",
            success=False,
            error=str(e),
            processing_time=processing_time
        )


# Legacy function maintained for backward compatibility
async def process_report_request(
    data: Union[ResearchPipelineModel, YouTubeTranscriptModel],
    style: str = "summary"
) -> AgentResponse:
    """Legacy report processing function - maintained for backward compatibility."""
    # Convert to universal data format
    from models import UniversalReportData

    if isinstance(data, ResearchPipelineModel):
        universal_data = UniversalReportData(
            query=data.original_query,
            research_data=data
        )
    else:  # YouTubeTranscriptModel
        universal_data = UniversalReportData(
            query=data.metadata.get("title", "YouTube Analysis"),
            youtube_data=data
        )

    # Use new intelligent system with standard quality
    return await process_intelligent_report_request(
        universal_data=universal_data,
        style=style,
        quality_level="standard"
    )
