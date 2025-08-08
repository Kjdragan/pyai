"""
Advanced Report Template System
Provides intelligent, adaptive templates for various domains and report styles.
"""

from typing import List, Dict, Any
from datetime import datetime


class AdvancedReportTemplateEngine:
    """Advanced template engine with domain intelligence and adaptive sections."""
    
    def __init__(self):
        self.domain_templates = self._initialize_domain_templates()
        self.section_generators = self._initialize_section_generators()
    
    def _initialize_domain_templates(self) -> Dict[str, Dict[str, str]]:
        """Initialize domain-specific template components."""
        return {
            "technology": {
                "executive_summary": """
                [Provide executive summary focusing on:
                • Technical innovation and market disruption potential
                • Adoption timeline and readiness assessment
                • Competitive landscape and key differentiators
                • Implementation complexity and resource requirements
                • Risk assessment and mitigation strategies]
                """,
                "current_analysis": """
                ## Technology Landscape Analysis
                [Analyze current state including:
                • Market penetration and adoption metrics
                • Key players and their positioning
                • Technical maturity and capabilities
                • Performance benchmarks and limitations
                • Integration ecosystem and partnerships]
                """,
                "future_outlook": """
                ## Technology Roadmap & Future Trends
                [Provide forward-looking analysis including:
                • Emerging developments and breakthrough potential
                • Timeline for major milestones and capabilities
                • Market evolution and adoption predictions
                • Potential disruptions and paradigm shifts
                • Investment and R&D trends]
                """
            },
            
            "business": {
                "executive_summary": """
                [Provide executive summary focusing on:
                • Market opportunity size and growth potential
                • Competitive positioning and strategic advantages
                • Financial impact and ROI projections
                • Key risks and mitigation strategies
                • Strategic recommendations for leadership]
                """,
                "current_analysis": """
                ## Market Analysis & Business Environment
                [Analyze current business landscape including:
                • Market size, growth rates, and segmentation
                • Competitive dynamics and market share analysis
                • Customer behavior and demand patterns
                • Regulatory environment and compliance requirements
                • Value chain analysis and key stakeholders]
                """,
                "future_outlook": """
                ## Market Forecast & Strategic Implications
                [Provide business outlook including:
                • Market growth projections and drivers
                • Emerging opportunities and business models
                • Competitive landscape evolution
                • Strategic recommendations and action items
                • Investment priorities and resource allocation]
                """
            },
            
            "science": {
                "executive_summary": """
                [Provide scientific summary focusing on:
                • Key research findings and their significance
                • Methodology strength and study limitations
                • Reproducibility and peer review status
                • Broader implications for the field
                • Practical applications and next research steps]
                """,
                "current_analysis": """
                ## Research Findings & Evidence Analysis
                [Analyze scientific evidence including:
                • Study methodology and sample characteristics
                • Statistical significance and effect sizes
                • Consistency across multiple studies
                • Quality of evidence and potential biases
                • Comparison with existing literature]
                """,
                "future_outlook": """
                ## Research Implications & Future Directions
                [Provide scientific outlook including:
                • Implications for current understanding
                • Areas requiring further investigation
                • Potential applications and implementations
                • Funding and research priorities
                • Timeline for practical applications]
                """
            }
        }
    
    def _initialize_section_generators(self) -> Dict[str, callable]:
        """Initialize dynamic section generators."""
        return {
            "multi_source_synthesis": self._generate_multi_source_section,
            "quantitative_insights": self._generate_quantitative_section,
            "actionable_recommendations": self._generate_recommendations_section,
            "risk_assessment": self._generate_risk_section,
            "methodology_transparency": self._generate_methodology_section
        }
    
    def generate_adaptive_template(
        self, 
        style: str, 
        query: str, 
        data_types: List[str], 
        domain_context: Dict[str, Any]
    ) -> str:
        """Generate adaptive template based on context and requirements."""
        
        domain = domain_context.get("domain", "general")
        complexity = domain_context.get("complexity", "moderate")
        intent = domain_context.get("intent", "informational")
        
        template_parts = []
        
        # Dynamic title with context
        title_context = self._get_contextual_title(domain, style, data_types)
        template_parts.extend([
            f"# {{title}} - {title_context}",
            "",
            f"*Generated on {datetime.now().strftime('%B %d, %Y')} | Domain: {domain.title()} | Style: {style.title()} | Sources: {', '.join(data_types).title()}*",
            ""
        ])
        
        # Executive Summary (for comprehensive reports or multi-source)
        if style == "comprehensive" or len(data_types) > 1:
            if domain in self.domain_templates:
                template_parts.extend([
                    "## Executive Summary",
                    self.domain_templates[domain]["executive_summary"],
                    ""
                ])
            else:
                template_parts.extend([
                    "## Executive Summary", 
                    "[Provide concise overview of key findings, implications, and recommendations]",
                    ""
                ])
        
        # Context and background (for complex queries)
        if complexity == "high" or any(word in query.lower() for word in ["history", "evolution", "development"]):
            template_parts.extend([
                "## Context & Background",
                "[Provide relevant historical context, key developments, and foundational information necessary to understand current analysis]",
                ""
            ])
        
        # Data source specific sections
        if "youtube" in data_types:
            template_parts.extend([
                "## Video Content Analysis",
                self._generate_video_analysis_section(domain, complexity),
                ""
            ])
        
        if "research" in data_types:
            template_parts.extend([
                "## Research Synthesis & Evidence",
                self._generate_research_synthesis_section(domain, complexity),
                ""
            ])
        
        if "weather" in data_types:
            template_parts.extend([
                "## Weather & Environmental Analysis", 
                "[Analyze weather patterns, trends, and implications for the query context]",
                ""
            ])
        
        # Current state analysis (domain-specific)
        if domain in self.domain_templates:
            template_parts.extend([
                self.domain_templates[domain]["current_analysis"],
                ""
            ])
        else:
            template_parts.extend([
                "## Current State Analysis",
                "[Detailed examination of present situation, key factors, and current dynamics]",
                ""
            ])
        
        # Multi-source synthesis (for multiple data types)
        if len(data_types) > 1:
            template_parts.extend([
                "## Cross-Source Analysis & Synthesis",
                "[Analyze connections, contradictions, and patterns across different data sources. Identify convergent themes and conflicting information.]",
                ""
            ])
        
        # Quantitative insights (always include for comprehensive analysis)
        if style in ["comprehensive", "top_10"] or "analysis" in query.lower():
            template_parts.extend([
                "## Quantitative Insights & Metrics",
                self._generate_quantitative_section(),
                ""
            ])
        
        # Future outlook (domain-specific)
        if style == "comprehensive" or intent == "predictive":
            if domain in self.domain_templates:
                template_parts.extend([
                    self.domain_templates[domain]["future_outlook"],
                    ""
                ])
            else:
                template_parts.extend([
                    "## Future Outlook & Predictions",
                    "[Analyze trends and provide informed predictions about future developments with confidence levels]",
                    ""
                ])
        
        # Risk assessment (for business and technology domains)
        if domain in ["business", "technology"] or "risk" in query.lower():
            template_parts.extend([
                "## Risk Assessment & Mitigation",
                self._generate_risk_section(),
                ""
            ])
        
        # Actionable recommendations (context-aware)
        template_parts.extend([
            "## Strategic Recommendations & Action Items",
            self._generate_recommendations_section(domain, complexity, intent),
            ""
        ])
        
        # Methodology and limitations (for high-quality reports)
        if style == "comprehensive" or complexity == "high":
            template_parts.extend([
                "## Methodology & Limitations",
                self._generate_methodology_section(),
                ""
            ])
        
        # Conclusion with confidence levels
        template_parts.extend([
            "## Conclusion & Key Takeaways",
            self._generate_conclusion_section(domain, intent),
            ""
        ])
        
        # Additional resources (for educational intent)
        if intent == "educational" or "learn" in query.lower():
            template_parts.extend([
                "## Additional Resources & Further Reading",
                "[Provide curated list of additional resources for deeper understanding]"
            ])
        
        return "\n".join(template_parts)
    
    def _get_contextual_title(self, domain: str, style: str, data_types: List[str]) -> str:
        """Generate contextual title suffix."""
        context_map = {
            "technology": "Technology Intelligence Report",
            "business": "Strategic Business Analysis",
            "science": "Research Analysis Report", 
            "news": "Current Affairs Intelligence",
            "historical": "Historical Analysis Report",
            "educational": "Comprehensive Learning Guide",
            "general": "Intelligence Report"
        }
        
        base_context = context_map.get(domain, "Analysis Report")
        
        if len(data_types) > 1:
            base_context = f"Multi-Source {base_context}"
        
        if style == "comprehensive":
            base_context = f"Comprehensive {base_context}"
        elif style == "top_10":
            base_context = f"Top Insights {base_context}"
        
        return base_context
    
    def _generate_video_analysis_section(self, domain: str, complexity: str) -> str:
        """Generate video analysis section based on domain."""
        if domain == "technology":
            return """[Analyze video content focusing on:
            • Technical concepts and innovations discussed
            • Implementation feasibility and practical applications
            • Expert credibility and supporting evidence
            • Technical accuracy and current relevance
            • Actionable insights for technologists]"""
        elif domain == "business":
            return """[Analyze video content focusing on:
            • Business insights and strategic implications
            • Market intelligence and competitive analysis
            • Speaker expertise and business credibility
            • Actionable business recommendations
            • ROI and implementation considerations]"""
        else:
            return """[Comprehensive video content analysis including:
            • Main arguments and supporting evidence
            • Speaker credibility and expertise assessment
            • Content quality and factual accuracy
            • Key insights and practical takeaways
            • Relevance to query context]"""
    
    def _generate_research_synthesis_section(self, domain: str, complexity: str) -> str:
        """Generate research synthesis section."""
        return """[Synthesize research findings by:
        • Analyzing methodology quality and reliability
        • Identifying patterns and consensus across sources
        • Highlighting conflicting viewpoints and uncertainties
        • Assessing credibility and publication quality
        • Extracting quantifiable insights and metrics
        • Connecting findings to practical implications]"""
    
    def _generate_multi_source_section(self) -> str:
        """Generate multi-source synthesis section."""
        return """[Cross-reference and synthesize information by:
        • Identifying convergent themes across sources
        • Analyzing conflicting information and explanations
        • Assessing relative credibility of different sources
        • Creating unified understanding from diverse inputs
        • Highlighting gaps and areas of uncertainty]"""
    
    def _generate_quantitative_section(self) -> str:
        """Generate quantitative insights section."""
        return """[Present quantitative analysis including:
        • Key metrics, statistics, and performance indicators
        • Trend analysis with growth rates and changes over time
        • Comparative analysis and benchmarking
        • Statistical significance and confidence intervals
        • Data visualization recommendations
        • Quantified impact assessments]"""
    
    def _generate_recommendations_section(self, domain: str, complexity: str, intent: str) -> str:
        """Generate context-aware recommendations section."""
        if domain == "technology":
            return """[Provide technical recommendations organized by:
            • Immediate implementation steps (0-3 months)
            • Technology adoption roadmap (3-12 months)
            • Long-term strategic initiatives (1+ years)
            • Risk mitigation and security considerations
            • Resource requirements and skill development
            • Success metrics and evaluation criteria]"""
        elif domain == "business":
            return """[Provide business recommendations organized by:
            • Strategic priorities and quick wins (immediate)
            • Market positioning and competitive responses (3-6 months)
            • Long-term growth and innovation strategies (12+ months)
            • Investment priorities and resource allocation
            • Risk management and contingency planning
            • Performance metrics and success tracking]"""
        else:
            return """[Provide actionable recommendations categorized by:
            • Immediate actions and quick wins
            • Medium-term strategies and initiatives
            • Long-term vision and strategic goals
            • Implementation timeline and milestones
            • Resource requirements and dependencies
            • Success metrics and evaluation framework]"""
    
    def _generate_risk_section(self) -> str:
        """Generate risk assessment section."""
        return """[Comprehensive risk assessment including:
        • Identification of key risks and vulnerabilities
        • Probability and impact analysis for each risk
        • Risk interconnections and cascade effects
        • Mitigation strategies and contingency plans
        • Monitoring indicators and early warning signals
        • Risk-adjusted recommendations and alternatives]"""
    
    def _generate_methodology_section(self) -> str:
        """Generate methodology transparency section."""
        return """[Methodology and transparency disclosure:
        • Data sources and collection methods
        • Analysis frameworks and assumptions
        • Limitations and potential biases
        • Quality assessment of source materials
        • Confidence levels and uncertainty ranges
        • Peer review and validation processes]"""
    
    def _generate_conclusion_section(self, domain: str, intent: str) -> str:
        """Generate domain and intent-aware conclusion section."""
        base = """[Synthesize analysis into clear conclusion that:
        • Directly answers the original query with confidence levels
        • Highlights the most critical and actionable insights
        • Provides forward-looking perspective with timelines
        • Acknowledges limitations and areas of uncertainty"""
        
        if domain == "technology":
            base += """
        • Assesses technical feasibility and market readiness
        • Provides innovation timeline and adoption predictions]"""
        elif domain == "business":
            base += """
        • Quantifies market opportunity and business impact
        • Provides strategic recommendations for decision makers]"""
        else:
            base += """
        • Connects findings to broader implications and context]"""
        
        return base


# Global template engine instance
template_engine = AdvancedReportTemplateEngine()


def get_advanced_adaptive_template(
    style: str,
    query: str,
    data_types: List[str],
    domain_context: Dict[str, Any] = None
) -> str:
    """Get advanced adaptive template using the template engine."""
    if domain_context is None:
        domain_context = {"domain": "general", "complexity": "moderate", "intent": "informational"}
    
    return template_engine.generate_adaptive_template(style, query, data_types, domain_context)


# Template style definitions for different report formats
REPORT_STYLE_CONFIGS = {
    "comprehensive": {
        "min_sections": 8,
        "include_methodology": True,
        "include_future_outlook": True,
        "include_risk_assessment": True,
        "quality_level": "enhanced"
    },
    "executive": {
        "min_sections": 5,
        "focus_on": ["summary", "recommendations", "risks"],
        "include_quantitative": True,
        "quality_level": "premium"
    },
    "top_10": {
        "format": "numbered_insights",
        "max_insights": 10,
        "include_summary": True,
        "quality_level": "standard"
    },
    "summary": {
        "min_sections": 4,
        "focus_on": ["overview", "key_findings", "implications"],
        "quality_level": "standard"
    },
    "technical": {
        "domain": "technology",
        "include_methodology": True,
        "include_implementation": True,
        "quality_level": "enhanced"
    }
}


def get_style_config(style: str) -> Dict[str, Any]:
    """Get configuration for specific report style."""
    return REPORT_STYLE_CONFIGS.get(style.lower(), REPORT_STYLE_CONFIGS["summary"])