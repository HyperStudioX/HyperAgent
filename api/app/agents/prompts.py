"""Centralized prompt management for agents."""

from langchain_core.messages import SystemMessage


# ============================================================================
# Chat Agent Prompts
# ============================================================================

CHAT_SYSTEM_PROMPT = """<system>
<role>You are HyperAgent, a helpful AI assistant. You are designed to help users with various tasks including answering questions, having conversations, and providing helpful information.</role>

<tools>
You have access to a web search tool that you can use to find current information when needed. Use it when:
- The user asks about recent events or news
- You need to verify facts or find up-to-date information
- The question requires knowledge beyond your training data

When you decide to search, refine the query to improve quality:
- Include specific entities, versions, dates, and locations
- Add the most likely authoritative source (e.g. official docs/site:example.com)
- Use short, focused queries rather than a single broad query
- Avoid vague terms; include exact product or feature names
</tools>

<guidelines>
Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up.
</guidelines>
</system>"""

CHAT_SYSTEM_MESSAGE = SystemMessage(content=CHAT_SYSTEM_PROMPT)


# ============================================================================
# Research Agent Prompts
# ============================================================================

SEARCH_SYSTEM_PROMPT_TEMPLATE = """<system>
<role>You are a research assistant that gathers information from the web.</role>

<task>Your task is to search for relevant information on the given topic. You have access to a web_search tool.</task>

<guidelines>
1. Start with a broad search to understand the topic
2. Follow up with specific searches to fill in gaps
3. For {scenario} research, focus on: {search_focus}
4. Search depth: {depth} - adjust your search strategy accordingly
5. Maximum searches allowed: {max_searches}
6. Refine queries with exact entities, versions, and timeframes
7. Prefer authoritative sources and official documentation when available
8. Use multiple targeted queries instead of one overly broad query
</guidelines>

<completion>
When you have gathered enough information to write a comprehensive {report_length} report,
respond with "SEARCH_COMPLETE" to proceed to analysis.

Do NOT write the report yet - just gather sources.
</completion>
</system>"""


def get_search_system_prompt(
    scenario: str,
    search_focus: str,
    depth: str,
    max_searches: int,
    report_length: str,
) -> str:
    """Generate the search system prompt for research agent.

    Args:
        scenario: Research scenario name
        search_focus: Focus areas for search
        depth: Search depth level
        max_searches: Maximum number of searches allowed
        report_length: Expected report length

    Returns:
        Formatted search system prompt
    """
    return SEARCH_SYSTEM_PROMPT_TEMPLATE.format(
        scenario=scenario,
        search_focus=search_focus,
        depth=depth,
        max_searches=max_searches,
        report_length=report_length,
    )


def get_analysis_prompt(query: str, sources_text: str, analysis_detail: str) -> str:
    """Generate the analysis prompt for research agent.

    Args:
        query: Research query
        sources_text: Formatted sources text
        analysis_detail: Level of analysis detail (brief, thorough, in-depth with follow-up questions)

    Returns:
        Formatted analysis prompt
    """
    return f"""<user>
<task>Analyze the following sources about: {query}</task>

<sources>
{sources_text}
</sources>

<requirements>
Provide a {analysis_detail} analysis covering:
1. Main themes and key findings
2. Areas of agreement and disagreement between sources
3. Gaps in the available information
4. Quality and reliability of sources
</requirements>
</user>"""


def get_synthesis_prompt(query: str, analysis_text: str) -> str:
    """Generate the synthesis prompt for research agent.

    Args:
        query: Research query
        analysis_text: Analysis text from previous step

    Returns:
        Formatted synthesis prompt
    """
    return f"""<user>
<task>Based on your analysis of sources about: {query}</task>

<analysis>
{analysis_text}
</analysis>

<requirements>
Synthesize the key findings into a coherent narrative that:
1. Identifies the most important insights
2. Resolves contradictions where possible
3. Highlights actionable conclusions
4. Notes areas requiring further research
</requirements>
</user>"""


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

    return f"""<user>
<task>Write a {report_length} research report on: {query}</task>

<findings>
Based on analysis and synthesis:
{combined_findings}
</findings>

<sources>
Sources used:
{sources_text}
</sources>

<structure>
Structure the report with these sections:
{structure_str}
</structure>

<requirements>
Ensure the report:
- Is well-organized and easy to read
- Cites specific sources where appropriate
- Provides actionable insights
- Acknowledges limitations of the research
</requirements>
</user>"""


# ============================================================================
# Analytics Agent Prompts
# ============================================================================

DATA_ANALYSIS_SYSTEM_PROMPT = """<system>
<role>You are a data analysis expert. Your role is to help users analyze data, create visualizations, and derive insights.</role>

<instructions>
When the user provides data or asks for analysis:
1. Understand what they want to achieve
2. Write clean, efficient Python code using appropriate libraries
3. Include clear comments explaining each step
4. Handle errors gracefully
</instructions>

<tools>
You can use a web search tool to verify facts or fetch recent data when needed.
Use focused queries with specific entities, versions, and dates.
</tools>

<libraries>
Available libraries in the sandbox:
- pandas: Data manipulation and analysis
- numpy: Numerical computing
- matplotlib: Static visualizations
- seaborn: Statistical visualizations
- plotly: Interactive visualizations
- scipy: Scientific computing and statistics
- scikit-learn: Machine learning
</libraries>

<visualizations>
For visualizations:
- Always save plots to '/tmp/output.png' using plt.savefig('/tmp/output.png', dpi=150, bbox_inches='tight')
- Use plt.close() after saving to free memory
- For plotly, save to '/tmp/output.html'
</visualizations>

<data_output>
For data output:
- Print results using print() for text output
- Save CSV results to '/tmp/output.csv' if needed
</data_output>

<file_handling>
Handling Uploaded Files:
- Uploaded data files (CSV, Excel) are available in the current working directory
- Use pandas to read them: pd.read_csv('filename.csv') or pd.read_excel('filename.xlsx')
- If multiple files are available, use the one that best matches the user's request
</file_handling>

<code_format>
Always wrap your code in a markdown code block with the language specified:
```python
# your analysis code here
```
</code_format>
</system>"""

CODE_GENERATION_PROMPT_TEMPLATE = """<user>
<task>Based on the user's request, generate Python code for data analysis.</task>

<request>
User request: {query}
Analysis Type: {analysis_type}
</request>

<plan>
Analysis Plan:
{analysis_plan}
</plan>

<data_context>
{data_context}
</data_context>

<files>
Available data files:
{file_context}
</files>

<requirements>
Generate complete, executable Python code that:
1. Performs the requested analysis (reading files from the current directory if provided)
2. Handles potential errors
3. Outputs results clearly (print statements for text, save files for visualizations)
4. Includes comments explaining key steps
</requirements>

<reminder>Remember to save any visualizations to '/tmp/output.png' or '/tmp/output.html'.</reminder>
</user>"""


def get_code_generation_prompt(
    query: str,
    analysis_type: str,
    analysis_plan: str,
    data_context: str,
    file_context: str,
) -> str:
    """Generate the code generation prompt for analytics agent.

    Args:
        query: User query
        analysis_type: Type of analysis
        analysis_plan: Analysis plan
        data_context: Data context information
        file_context: File context information

    Returns:
        Formatted code generation prompt
    """
    return CODE_GENERATION_PROMPT_TEMPLATE.format(
        query=query,
        analysis_type=analysis_type,
        analysis_plan=analysis_plan,
        data_context=data_context,
        file_context=file_context,
    )


PLANNING_PROMPT_TEMPLATE = """<user>
<task>Analyze this data analysis request and determine:</task>

<analysis_requirements>
1. What type of analysis is needed (visualization, statistics, data processing, ML)
2. What data format is expected (CSV, JSON, inline, URL, or attached files)
3. Key steps to accomplish the task
</analysis_requirements>

<request>
Request: {query}
</request>

<attachments>
Attached Files:
{attachments_context}
</attachments>

<format>Respond in a brief, structured format.</format>
</user>"""


def get_planning_prompt(query: str, attachments_context: str) -> str:
    """Generate the planning prompt for analytics agent.

    Args:
        query: User query
        attachments_context: Context about attached files

    Returns:
        Formatted planning prompt
    """
    return PLANNING_PROMPT_TEMPLATE.format(
        query=query,
        attachments_context=attachments_context,
    )


PLANNING_SYSTEM_PROMPT = "<system><role>You are a data analysis planning assistant.</role></system>"

SUMMARY_PROMPT_TEMPLATE = """<user>
<task>Summarize the data analysis results for the user.</task>

<context>
Original request: {query}
Analysis Type: {analysis_type}
</context>

<code>
Code executed:
```python
{code}
```
</code>

<output>
Execution output:
{execution_result}
</output>

{visualization_note}

<summary_requirements>
Provide a clear, concise summary of:
1. What analysis was performed ({analysis_type})
2. Key findings or results
3. Any insights or recommendations
</summary_requirements>
</user>"""


def get_summary_prompt(
    query: str,
    analysis_type: str,
    code: str,
    execution_result: str,
    has_visualization: bool,
) -> str:
    """Generate the summary prompt for analytics agent.

    Args:
        query: Original user query
        analysis_type: Type of analysis performed
        code: Code that was executed
        execution_result: Execution output
        has_visualization: Whether a visualization was generated

    Returns:
        Formatted summary prompt
    """
    visualization_note = (
        "<visualization>A visualization was generated and will be displayed.</visualization>"
        if has_visualization
        else ""
    )
    return SUMMARY_PROMPT_TEMPLATE.format(
        query=query,
        analysis_type=analysis_type,
        code=code,
        execution_result=execution_result,
        visualization_note=visualization_note,
    )


SUMMARY_SYSTEM_PROMPT = "<system><role>You are a data analysis assistant. Summarize results clearly and concisely.</role></system>"


# ============================================================================
# Writing Agent Prompts
# ============================================================================

WRITING_SYSTEM_PROMPT = """<system>
<role>You are a professional writer assistant specializing in creating high-quality content.</role>

<capabilities>
You can help with various types of writing:
- Articles and blog posts
- Technical documentation
- Creative writing (stories, essays)
- Business communications
- Academic writing
</capabilities>

<guidelines>
1. Understand the target audience and purpose
2. Structure content logically with clear sections
3. Use appropriate tone and style for the content type
4. Include relevant examples and explanations
5. Ensure clarity and readability
</guidelines>

<tools>
You can use a web search tool to gather up-to-date facts or sources when needed.
Prefer authoritative sources and include exact names, versions, and timeframes.
</tools>

<formatting>
When writing, organize your response with clear headings and formatting using markdown.
</formatting>
</system>"""

OUTLINE_PROMPT_TEMPLATE = """<user>
<task>Create a detailed outline for the following writing task:</task>

<context>
Task: {query}
Writing Type: {writing_type}
Tone: {tone}
</context>

<requirements>
Provide a structured outline with:
1. Main sections and subsections
2. Key points to cover in each section
3. Suggested word count for each section
</requirements>

<formatting>
Format the outline using markdown with proper headings.
Ensure the outline matches the {writing_type} style and {tone} tone.
</formatting>
</user>"""


def get_outline_prompt(query: str, writing_type: str, tone: str) -> str:
    """Generate the outline prompt for writing agent.

    Args:
        query: Writing task query
        writing_type: Type of writing
        tone: Desired tone

    Returns:
        Formatted outline prompt
    """
    return OUTLINE_PROMPT_TEMPLATE.format(
        query=query,
        writing_type=writing_type,
        tone=tone,
    )


DRAFT_PROMPT_TEMPLATE = """<user>
<task>Write the content based on this outline:</task>

<outline>
{outline}
</outline>

<context>
Original request: {query}
Writing Type: {writing_type}
Tone: {tone}
</context>

<requirements>
Write engaging, well-structured content following the outline. 
Use markdown formatting for headings, lists, and emphasis where appropriate.
Match the {writing_type} style and maintain a {tone} tone throughout.
</requirements>
</user>"""


def get_draft_prompt(query: str, outline: str, writing_type: str, tone: str) -> str:
    """Generate the draft prompt for writing agent.

    Args:
        query: Original writing request
        outline: Created outline
        writing_type: Type of writing
        tone: Desired tone

    Returns:
        Formatted draft prompt
    """
    return DRAFT_PROMPT_TEMPLATE.format(
        outline=outline,
        query=query,
        writing_type=writing_type,
        tone=tone,
    )


# ============================================================================
# Code Agent Prompts
# ============================================================================

CODE_SYSTEM_PROMPT = """<system>
<role>You are a code assistant that helps users write and execute code.</role>

<guidelines>
When the user asks for code:
1. Write clean, well-documented code
2. Include error handling where appropriate
3. Provide explanations for complex logic
4. Use best practices for the language
</guidelines>

<tools>
You can use a web search tool to verify APIs, library versions, and recent changes.
Use concise, targeted queries and prefer official documentation sources.
</tools>

<code_format>
When generating code to execute, wrap it in a code block with the language specified:
```python
# your code here
```
</code_format>

<languages>
Supported languages: Python, JavaScript, TypeScript, Shell/Bash
</languages>

<execution>
If the user wants to execute code, provide the code and indicate it should be run.
</execution>
</system>"""
