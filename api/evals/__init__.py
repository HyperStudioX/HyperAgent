"""Agent evaluation framework for HyperAgent.

This module provides comprehensive evaluation capabilities for the multi-agent system:
- Routing accuracy evaluation
- Tool/skill selection evaluation
- Response quality evaluation

Usage:
    make eval           # Run all evaluations
    make eval-routing   # Run routing evaluations only
    make eval-tools     # Run tool selection evaluations only
    make eval-quality   # Run response quality evaluations only
"""

from .evaluators import (
    response_quality_evaluator,
    routing_accuracy_evaluator,
    tool_selection_evaluator,
)
from .mocks import MockChatModel, MockLLMConfig, MockResponse

__all__ = [
    "MockChatModel",
    "MockLLMConfig",
    "MockResponse",
    "routing_accuracy_evaluator",
    "tool_selection_evaluator",
    "response_quality_evaluator",
]
