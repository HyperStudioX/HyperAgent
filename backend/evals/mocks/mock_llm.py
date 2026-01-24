"""Mock LLM implementation for deterministic agent testing."""

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field


class MockResponse(BaseModel):
    """A mock response configuration for pattern-based matching."""

    pattern: str = Field(description="Regex pattern to match against input")
    response: str = Field(description="Response text to return")
    tool_calls: list[dict] | None = Field(
        default=None,
        description="Optional tool calls to include in the response",
    )

    def matches(self, text: str) -> bool:
        """Check if this response matches the input text."""
        return bool(re.search(self.pattern, text, re.IGNORECASE))


class MockLLMConfig(BaseModel):
    """Configuration for MockChatModel."""

    responses: list[MockResponse] = Field(
        default_factory=list,
        description="List of pattern-based responses",
    )
    default_response: str = Field(
        default="I can help with that.",
        description="Default response when no pattern matches",
    )
    default_tool_calls: list[dict] | None = Field(
        default=None,
        description="Default tool calls when no pattern matches",
    )


class MockChatModel(BaseChatModel):
    """Mock chat model for deterministic testing of agent behavior.

    This model returns pre-configured responses based on regex pattern matching
    against the input. It's useful for testing routing, tool selection, and
    other agent behaviors without making actual LLM API calls.

    Example:
        config = MockLLMConfig(
            responses=[
                MockResponse(
                    pattern="generate.*image",
                    response="I'll generate that image for you.",
                    tool_calls=[{
                        "name": "invoke_skill",
                        "args": {"skill_id": "image_generation", "params": {...}},
                        "id": "call_1"
                    }]
                )
            ]
        )
        mock_llm = MockChatModel(config=config)
    """

    config: MockLLMConfig = Field(default_factory=MockLLMConfig)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response based on pattern matching.

        Args:
            messages: Input messages (uses last message for matching)
            stop: Stop sequences (unused in mock)
            run_manager: Callback manager (unused in mock)
            **kwargs: Additional arguments (unused)

        Returns:
            ChatResult with matched or default response
        """
        # Extract text from last message
        user_input = ""
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                content = last_message.content
                if isinstance(content, str):
                    user_input = content
                elif isinstance(content, list):
                    # Handle multimodal content
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            user_input = item.get("text", "")
                            break
                        elif isinstance(item, str):
                            user_input = item
                            break

        # Find matching response
        for resp in self.config.responses:
            if resp.matches(user_input):
                return self._create_result(resp.response, resp.tool_calls)

        return self._create_result(
            self.config.default_response,
            self.config.default_tool_calls,
        )

    def _create_result(
        self,
        content: str,
        tool_calls: list[dict] | None,
    ) -> ChatResult:
        """Create a ChatResult from content and optional tool calls.

        Args:
            content: Response text
            tool_calls: Optional list of tool calls

        Returns:
            ChatResult with AIMessage
        """
        msg = AIMessage(content=content, tool_calls=tool_calls or [])
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return "mock"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        """Return identifying parameters for this model."""
        return {"config": self.config.model_dump()}


class MockRouterLLM(MockChatModel):
    """Specialized mock LLM for testing the router.

    Pre-configured with responses that match the router's expected
    JSON output format.
    """

    def __init__(self, routing_map: dict[str, str] | None = None, **kwargs):
        """Initialize with optional routing map.

        Args:
            routing_map: Dict mapping input patterns to agent names
            **kwargs: Additional arguments passed to parent
        """
        routing_map = routing_map or {}

        responses = []
        for pattern, agent in routing_map.items():
            responses.append(
                MockResponse(
                    pattern=pattern,
                    response=json.dumps(
                        {
                            "agent": agent,
                            "confidence": 0.95,
                            "reason": f"Pattern matched for {agent}",
                        }
                    ),
                )
            )

        config = MockLLMConfig(
            responses=responses,
            default_response=json.dumps(
                {
                    "agent": "chat",
                    "confidence": 0.8,
                    "reason": "Default routing to chat",
                }
            ),
        )

        super().__init__(config=config, **kwargs)
