"""Centralized prompt management for agents."""

from langchain_core.messages import SystemMessage


# Chat Agent Prompts
CHAT_SYSTEM_MESSAGE = SystemMessage(
    content="""You are HyperAgent, a helpful AI assistant. You are designed to help users with various tasks including coding, research, analysis, and general questions.

Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up."""
)


# Research Agent Prompts
def get_analysis_prompt(query: str, sources_text: str, analysis_detail: str) -> str:
    """Generate the analysis prompt for research agent.

    Args:
        query: Research query
        sources_text: Formatted sources text
        analysis_detail: Level of analysis detail (brief, thorough, in-depth with follow-up questions)

    Returns:
        Formatted analysis prompt
    """
    return f"""Analyze the following sources about: {query}

Sources:
{sources_text}

Provide a {analysis_detail} analysis covering:
1. Main themes and key findings
2. Areas of agreement and disagreement between sources
3. Gaps in the available information
4. Quality and reliability of sources"""


def get_synthesis_prompt(query: str, analysis_text: str) -> str:
    """Generate the synthesis prompt for research agent.

    Args:
        query: Research query
        analysis_text: Analysis text from previous step

    Returns:
        Formatted synthesis prompt
    """
    return f"""Based on your analysis of sources about: {query}

Analysis:
{analysis_text}

Synthesize the key findings into a coherent narrative that:
1. Identifies the most important insights
2. Resolves contradictions where possible
3. Highlights actionable conclusions
4. Notes areas requiring further research"""


def get_report_prompt(
    query: str,
    combined_findings: str,
    sources_text: str,
    report_structure: list[str],
    report_length: str,
) -> str:
    """Generate the report writing prompt for research agent.

    Args:
        query: Research query
        combined_findings: Combined analysis and synthesis findings
        sources_text: Formatted sources text
        report_structure: List of report section names
        report_length: Length descriptor (concise, comprehensive, detailed and extensive)

    Returns:
        Formatted report prompt
    """
    structure_str = "\n".join(
        [f"{i + 1}. {section}" for i, section in enumerate(report_structure)]
    )

    return f"""Write a {report_length} research report on: {query}

Based on analysis and synthesis:
{combined_findings}

Sources used:
{sources_text}

Structure the report with these sections:
{structure_str}

Ensure the report:
- Is well-organized and easy to read
- Cites specific sources where appropriate
- Provides actionable insights
- Acknowledges limitations of the research"""
