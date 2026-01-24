"""Pytest fixtures for agent evaluations."""

import json
from pathlib import Path
from typing import Any

import pytest

from evals.mocks.mock_llm import MockChatModel, MockLLMConfig, MockResponse, MockRouterLLM

# =============================================================================
# Data Fixtures
# =============================================================================


@pytest.fixture
def datasets_path() -> Path:
    """Return path to datasets directory."""
    return Path(__file__).parent / "datasets"


@pytest.fixture
def routing_cases(datasets_path: Path) -> list[dict[str, Any]]:
    """Load routing test cases from JSON."""
    path = datasets_path / "routing.json"
    data = json.loads(path.read_text())
    return data["test_cases"]


@pytest.fixture
def tool_selection_cases(datasets_path: Path) -> list[dict[str, Any]]:
    """Load tool selection test cases from JSON."""
    path = datasets_path / "tool_selection.json"
    data = json.loads(path.read_text())
    return data["test_cases"]


@pytest.fixture
def response_quality_cases(datasets_path: Path) -> list[dict[str, Any]]:
    """Load response quality test cases from JSON."""
    path = datasets_path / "response_quality.json"
    data = json.loads(path.read_text())
    return data["test_cases"]


# =============================================================================
# Mock LLM Fixtures
# =============================================================================


@pytest.fixture
def mock_router_llm() -> MockRouterLLM:
    """Create a mock LLM for router testing.

    Pre-configured with routing patterns that match expected behavior.
    Note: Patterns are matched in order, so more specific patterns should come first.
    """
    routing_map = {
        # Research patterns (more specific, check first)
        r"comprehensive.*research|comprehensive.*paper|comprehensive.*report": "research",
        r"comprehensive.*market.*analysis|comprehensive.*analysis": "research",
        r"detailed.*report.*synthesis|detailed.*analysis": "research",
        r"academic.*literature.*review|literature.*review.*citations": "research",
        r"research.*paper.*citations|20.*page|30\+.*citations": "research",
        r"peer.*reviewed|scholarly.*articles": "research",
        r"multi.*source.*analysis|multiple.*source.*synthesis": "research",
        # Data patterns (check before chat to catch data-specific queries)
        r"csv.*file|excel.*file|spreadsheet": "data",
        r"analyze.*csv|analyze.*excel|analyze.*data": "data",
        r"process.*excel|process.*csv": "data",
        r"statistical.*analysis|statistics.*on.*dataset": "data",
        r"data.*visualization|create.*dashboard|quarterly.*breakdown": "data",
        r"calculate.*correlations|find.*patterns.*data": "data",
        # Chat patterns (catch-all for remaining)
        r"hello|hi|how are you": "chat",
        r"what is|explain|tell me about": "chat",
        r"generate.*image|create.*picture|draw": "chat",
        r"write.*code|write.*function|write.*class": "chat",
        r"review.*code|check.*code": "chat",
        r"write.*email|write.*article|write.*blog": "chat",
        r"weather|news|search": "chat",
        r"go to|navigate|browse|click|fill.*form": "chat",
        r"translate|times|simple": "chat",
    }
    return MockRouterLLM(routing_map=routing_map)


@pytest.fixture
def mock_chat_llm() -> MockChatModel:
    """Create a mock LLM for chat agent testing.

    Configured to return appropriate tool calls based on input patterns.
    """
    responses = [
        # Image generation
        MockResponse(
            pattern=r"generate.*image|create.*picture|draw",
            response="I'll generate that image for you.",
            tool_calls=[
                {
                    "name": "invoke_skill",
                    "args": {"skill_id": "image_generation", "params": {"prompt": "image"}},
                    "id": "call_img_1",
                }
            ],
        ),
        # Code generation
        MockResponse(
            pattern=r"write.*code|write.*function|write.*class",
            response="I'll write that code for you.",
            tool_calls=[
                {
                    "name": "invoke_skill",
                    "args": {"skill_id": "code_generation", "params": {"task": "code"}},
                    "id": "call_code_1",
                }
            ],
        ),
        # Code review
        MockResponse(
            pattern=r"review.*code|check.*code.*bugs",
            response="I'll review that code.",
            tool_calls=[
                {
                    "name": "invoke_skill",
                    "args": {"skill_id": "code_review", "params": {"code": "code"}},
                    "id": "call_review_1",
                }
            ],
        ),
        # Writing
        MockResponse(
            pattern=r"write.*email|write.*article|write.*blog",
            response="I'll write that for you.",
            tool_calls=[
                {
                    "name": "invoke_skill",
                    "args": {"skill_id": "simple_writing", "params": {"task": "write"}},
                    "id": "call_write_1",
                }
            ],
        ),
        # Web research
        MockResponse(
            pattern=r"research.*trends|find.*news|search.*recent",
            response="I'll research that for you.",
            tool_calls=[
                {
                    "name": "invoke_skill",
                    "args": {"skill_id": "web_research", "params": {"query": "search"}},
                    "id": "call_research_1",
                }
            ],
        ),
        # Data visualization
        MockResponse(
            pattern=r"create.*chart|generate.*chart|bar chart|pie chart",
            response="I'll create that visualization.",
            tool_calls=[
                {
                    "name": "invoke_skill",
                    "args": {"skill_id": "data_visualization", "params": {"data": "data"}},
                    "id": "call_viz_1",
                }
            ],
        ),
        # Web search tool
        MockResponse(
            pattern=r"search for|look up|find information",
            response="I'll search for that.",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "search query"},
                    "id": "call_search_1",
                }
            ],
        ),
        # Code execution
        MockResponse(
            pattern=r"run.*code|execute.*code|run this",
            response="I'll run that code.",
            tool_calls=[
                {
                    "name": "execute_code",
                    "args": {"code": "print('hello')"},
                    "id": "call_exec_1",
                }
            ],
        ),
        # Browser navigation
        MockResponse(
            pattern=r"navigate to|go to.*\.com|browse",
            response="I'll navigate there.",
            tool_calls=[
                {
                    "name": "browser_navigate",
                    "args": {"url": "https://example.com"},
                    "id": "call_browser_1",
                }
            ],
        ),
    ]

    config = MockLLMConfig(
        responses=responses,
        default_response="I can help with that.",
        default_tool_calls=None,
    )
    return MockChatModel(config=config)


@pytest.fixture
def mock_judge_llm() -> MockChatModel:
    """Create a mock LLM for response quality judging."""
    config = MockLLMConfig(
        default_response=json.dumps(
            {
                "score": 0.8,
                "reasoning": "Good response that meets most criteria",
                "strengths": ["Clear", "Helpful"],
                "weaknesses": ["Could be more detailed"],
            }
        ),
    )
    return MockChatModel(config=config)


# =============================================================================
# Mock Supervisor and Agent Fixtures
# =============================================================================


@pytest.fixture
def mock_supervisor(mock_router_llm: MockRouterLLM):
    """Create a mock supervisor for routing tests."""

    class MockSupervisor:
        def __init__(self, llm):
            self.llm = llm

        async def route(self, query: str) -> dict[str, Any]:
            """Route a query and return the result."""
            from langchain_core.messages import HumanMessage, SystemMessage

            # Simulate the routing prompt
            messages = [
                SystemMessage(content="Route this query to an agent."),
                HumanMessage(content=f"Query: {query}"),
            ]

            result = self.llm._generate(messages)
            content = result.generations[0].message.content

            # Parse the JSON response
            try:
                parsed = json.loads(content)
                return {
                    "next_agent": parsed.get("agent", "chat"),
                    "confidence": parsed.get("confidence", 0.8),
                    "reason": parsed.get("reason", ""),
                }
            except json.JSONDecodeError:
                return {
                    "next_agent": "chat",
                    "confidence": 0.5,
                    "reason": "Parse error",
                }

    return MockSupervisor(mock_router_llm)


@pytest.fixture
def mock_chat_agent(mock_chat_llm: MockChatModel):
    """Create a mock chat agent for tool selection tests."""

    class MockChatAgent:
        def __init__(self, llm):
            self.llm = llm

        async def process(self, query: str) -> dict[str, Any]:
            """Process a query and return tool calls."""
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="You are a helpful assistant with tools."),
                HumanMessage(content=query),
            ]

            result = self.llm._generate(messages)
            ai_message = result.generations[0].message

            return {
                "response": ai_message.content,
                "tool_calls": ai_message.tool_calls or [],
            }

    return MockChatAgent(mock_chat_llm)


# =============================================================================
# LangSmith Fixtures (Optional)
# =============================================================================


@pytest.fixture
def langsmith_client():
    """Create a LangSmith client if available."""
    try:
        from langsmith import Client

        return Client()
    except ImportError:
        pytest.skip("LangSmith not installed")
    except Exception:
        pytest.skip("LangSmith not configured")
