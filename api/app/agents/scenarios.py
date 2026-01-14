"""Scenario configurations for deep research."""

from app.models.schemas import ResearchScenario

SCENARIO_CONFIGS = {
    ResearchScenario.ACADEMIC: {
        "name": "Academic Research",
        "system_prompt": """You are an academic research assistant specializing in scholarly analysis.
Your role is to:
1. Identify and analyze peer-reviewed sources and scholarly articles
2. Provide proper citations and references
3. Synthesize findings following academic standards
4. Present balanced, evidence-based conclusions

Focus on authoritative academic sources, research papers, and established journals.""",
        "search_focus": [
            "scholarly articles",
            "peer-reviewed papers",
            "academic journals",
            "research publications",
            "citations",
        ],
        "report_structure": [
            "Abstract",
            "Literature Review",
            "Methodology Overview",
            "Key Findings",
            "Discussion",
            "References",
        ],
    },
    ResearchScenario.MARKET_ANALYSIS: {
        "name": "Market Analysis",
        "system_prompt": """You are a market research analyst with expertise in business intelligence.
Your role is to:
1. Analyze market trends and industry dynamics
2. Evaluate competitive landscapes
3. Identify opportunities and threats
4. Provide actionable business insights

Focus on market data, industry reports, and competitive intelligence.""",
        "search_focus": [
            "market trends",
            "industry analysis",
            "competitor data",
            "market share",
            "business reports",
            "financial data",
        ],
        "report_structure": [
            "Executive Summary",
            "Market Overview",
            "Competitive Landscape",
            "SWOT Analysis",
            "Key Trends",
            "Strategic Recommendations",
        ],
    },
    ResearchScenario.TECHNICAL: {
        "name": "Technical Investigation",
        "system_prompt": """You are a technical research specialist with deep expertise in software and technology.
Your role is to:
1. Analyze technical documentation and specifications
2. Evaluate implementation approaches and best practices
3. Provide code examples and technical guidance
4. Compare technologies and frameworks objectively

Focus on official documentation, API references, and technical specifications.""",
        "search_focus": [
            "technical documentation",
            "API references",
            "code examples",
            "implementation guides",
            "technical specifications",
            "developer resources",
        ],
        "report_structure": [
            "Technical Overview",
            "Architecture Analysis",
            "Implementation Details",
            "Code Examples",
            "Best Practices",
            "Technical Recommendations",
        ],
    },
    ResearchScenario.NEWS: {
        "name": "News & Current Events",
        "system_prompt": """You are a news and current events researcher focused on timely information.
Your role is to:
1. Track and analyze recent news and developments
2. Identify key events and their implications
3. Provide chronological context and timelines
4. Offer balanced perspective on current events

Focus on recent news, press releases, and authoritative news sources.""",
        "search_focus": [
            "recent news",
            "current events",
            "press releases",
            "breaking developments",
            "news analysis",
            "media coverage",
        ],
        "report_structure": [
            "Summary",
            "Timeline of Events",
            "Key Developments",
            "Stakeholder Analysis",
            "Impact Assessment",
            "Future Outlook",
        ],
    },
}


def get_scenario_config(scenario: ResearchScenario) -> dict:
    """Get configuration for a specific research scenario."""
    return SCENARIO_CONFIGS.get(scenario, SCENARIO_CONFIGS[ResearchScenario.ACADEMIC])
