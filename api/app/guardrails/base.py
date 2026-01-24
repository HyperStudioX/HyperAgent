"""Base types and abstractions for guardrails."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ViolationType(str, Enum):
    """Types of safety violations that can be detected."""

    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    PII = "pii"
    TOXICITY = "toxicity"
    HARMFUL_CONTENT = "harmful_content"
    INVALID_URL = "invalid_url"
    UNSAFE_CODE = "unsafe_code"


@dataclass
class ScanResult:
    """Result from a guardrails scan.

    Attributes:
        passed: Whether the content passed all checks
        blocked: Whether the content should be blocked entirely
        flagged: Whether the content was flagged but can continue
        violations: List of detected violation types
        reason: Human-readable explanation of the violation
        sanitized_content: Cleaned version of content if applicable
        confidence: Confidence score of the detection (0.0-1.0)
        metadata: Additional metadata from the scan
    """

    passed: bool
    blocked: bool = False
    flagged: bool = False
    violations: list[ViolationType] = field(default_factory=list)
    reason: str | None = None
    sanitized_content: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls) -> "ScanResult":
        """Create a passing result."""
        return cls(passed=True)

    @classmethod
    def block(
        cls,
        violations: list[ViolationType],
        reason: str,
        confidence: float = 1.0,
    ) -> "ScanResult":
        """Create a blocking result."""
        return cls(
            passed=False,
            blocked=True,
            violations=violations,
            reason=reason,
            confidence=confidence,
        )

    @classmethod
    def flag(
        cls,
        violations: list[ViolationType],
        reason: str | None = None,
        sanitized_content: str | None = None,
        confidence: float = 1.0,
    ) -> "ScanResult":
        """Create a flagged but non-blocking result."""
        return cls(
            passed=False,
            blocked=False,
            flagged=True,
            violations=violations,
            reason=reason,
            sanitized_content=sanitized_content,
            confidence=confidence,
        )
