"""Input scanner for prompt injection and jailbreak detection."""

import threading

from app.config import settings
from app.core.logging import get_logger
from app.guardrails.base import ScanResult, ViolationType
from app.guardrails.utils import truncate_for_logging

logger = get_logger(__name__)

# Lazy initialization flag (thread-safe with double-check locking)
_scanners_initialized = False
_prompt_injection_scanner = None
_init_lock = threading.Lock()


def _initialize_scanners():
    """Lazily initialize llm-guard scanners (thread-safe)."""
    global _scanners_initialized, _prompt_injection_scanner

    if _scanners_initialized:
        return

    with _init_lock:
        if _scanners_initialized:
            return

        try:
            from llm_guard.input_scanners import PromptInjection

            _prompt_injection_scanner = PromptInjection(threshold=0.8)
            _scanners_initialized = True
            logger.info("input_scanners_initialized")
        except ImportError as e:
            logger.warning(
                "llm_guard_not_available",
                error=str(e),
                detail="llm-guard not available, falling back to pattern-only jailbreak detection",
            )
            _scanners_initialized = True  # Mark as initialized to avoid retrying
        except SystemExit as e:
            # llm-guard may call sys.exit when spacy models aren't available
            logger.warning("llm_guard_model_download_required", error=str(e))
            _scanners_initialized = True
        except Exception as e:
            # Known issue: llm-guard 0.3.x has compatibility issues with Pydantic v2
            # Fall back to pattern-based detection only
            error_msg = str(e)
            if "REGEX" in error_msg or "type" in error_msg:
                logger.warning(
                    "llm_guard_pydantic_incompatibility",
                    detail="llm-guard has Pydantic v2 compatibility issues, using pattern-based detection only"
                )
            else:
                logger.error("input_scanners_init_failed", error=error_msg)
            _scanners_initialized = True


class InputScanner:
    """Scanner for detecting prompt injection and jailbreak attempts in user input."""

    def __init__(self):
        """Initialize the input scanner."""
        self._enabled = settings.guardrails_enabled and settings.guardrails_input_enabled

    async def scan(self, content: str) -> ScanResult:
        """Scan user input for safety violations.

        Args:
            content: User input text to scan

        Returns:
            ScanResult indicating whether content is safe
        """
        if not self._enabled:
            return ScanResult.allow()

        if not content or not content.strip():
            return ScanResult.allow()

        # Lazy initialization
        _initialize_scanners()

        violations = []
        reasons = []

        # Run llm-guard prompt injection detection
        if _prompt_injection_scanner is not None:
            try:
                sanitized, is_valid, risk_score = _prompt_injection_scanner.scan(content)
                if not is_valid:
                    violations.append(ViolationType.PROMPT_INJECTION)
                    reasons.append(
                        f"Potential prompt injection detected (confidence: {risk_score:.2f})"
                    )
                    logger.warning(
                        "prompt_injection_detected",
                        risk_score=risk_score,
                        content_preview=truncate_for_logging(content),
                    )
            except Exception as e:
                logger.error("prompt_injection_scan_failed", error=str(e))

        # Additional pattern-based checks for jailbreak attempts
        jailbreak_result = self._check_jailbreak_patterns(content)
        if jailbreak_result:
            violations.append(ViolationType.JAILBREAK)
            reasons.append(jailbreak_result)

        if violations:
            reason = "; ".join(reasons)
            if settings.guardrails_violation_action == "block":
                return ScanResult.block(violations, reason)
            elif settings.guardrails_violation_action == "warn":
                logger.warning("input_guardrail_violation", violations=violations, reason=reason)
                return ScanResult.flag(violations, reason)
            else:  # log
                logger.info("input_guardrail_logged", violations=violations, reason=reason)
                return ScanResult.allow()

        return ScanResult.allow()

    def _check_jailbreak_patterns(self, content: str) -> str | None:
        """Check for common jailbreak patterns.

        Args:
            content: Text to check

        Returns:
            Reason string if jailbreak detected, None otherwise
        """
        content_lower = content.lower()

        # Common jailbreak patterns
        jailbreak_patterns = [
            ("ignore previous instructions", "Attempt to override instructions"),
            ("ignore all instructions", "Attempt to override instructions"),
            ("disregard your instructions", "Attempt to override instructions"),
            ("forget your rules", "Attempt to override rules"),
            ("pretend you are", "Role-play manipulation attempt"),
            ("act as if you have no restrictions", "Restriction bypass attempt"),
            ("jailbreak", "Explicit jailbreak attempt"),
            ("developer mode", "Developer mode manipulation"),
            ("dan mode", "DAN (Do Anything Now) manipulation"),
            ("bypass your filters", "Filter bypass attempt"),
            ("ignore your safety", "Safety bypass attempt"),
            ("reveal your system prompt", "System prompt extraction"),
            ("show me your instructions", "Instruction extraction"),
        ]

        for pattern, reason in jailbreak_patterns:
            if pattern in content_lower:
                logger.warning(
                    "jailbreak_pattern_detected",
                    pattern=pattern,
                    content_preview=truncate_for_logging(content),
                )
                return reason

        return None


# Module-level singleton instance
input_scanner = InputScanner()
