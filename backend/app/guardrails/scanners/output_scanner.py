"""Output scanner for toxicity, PII, and harmful content detection."""

import threading

from app.config import settings
from app.core.logging import get_logger
from app.guardrails.base import ScanResult, ViolationType
from app.guardrails.utils import truncate_for_logging

logger = get_logger(__name__)

# Lazy initialization flag (thread-safe with double-check locking)
_scanners_initialized = False
_toxicity_scanner = None
_sensitive_scanner = None
_init_lock = threading.Lock()


def _initialize_scanners():
    """Lazily initialize llm-guard output scanners (thread-safe)."""
    global _scanners_initialized, _toxicity_scanner, _sensitive_scanner

    if _scanners_initialized:
        return

    with _init_lock:
        if _scanners_initialized:
            return

        try:
            from llm_guard.output_scanners import Sensitive, Toxicity

            _toxicity_scanner = Toxicity(threshold=0.7)
            _sensitive_scanner = Sensitive(redact=True)
            _scanners_initialized = True
            logger.info("output_scanners_initialized")
        except ImportError as e:
            logger.warning("llm_guard_import_failed", error=str(e))
            _scanners_initialized = True
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
                logger.error("output_scanners_init_failed", error=error_msg)
            _scanners_initialized = True


class OutputScanner:
    """Scanner for detecting toxic content and PII in LLM outputs."""

    def __init__(self):
        """Initialize the output scanner."""
        self._enabled = settings.guardrails_enabled and settings.guardrails_output_enabled

    async def scan(self, content: str, prompt: str = "") -> ScanResult:
        """Scan LLM output for safety violations.

        Args:
            content: LLM output text to scan
            prompt: Original prompt (for context)

        Returns:
            ScanResult with sanitized content if needed
        """
        if not self._enabled:
            return ScanResult.allow()

        if not content or not content.strip():
            return ScanResult.allow()

        # Lazy initialization
        _initialize_scanners()

        violations = []
        reasons = []
        sanitized = content

        # Run toxicity detection
        if _toxicity_scanner is not None:
            try:
                scanned, is_valid, risk_score = _toxicity_scanner.scan(prompt, content)
                if not is_valid:
                    violations.append(ViolationType.TOXICITY)
                    reasons.append(f"Toxic content detected (confidence: {risk_score:.2f})")
                    logger.warning(
                        "toxicity_detected",
                        risk_score=risk_score,
                        content_preview=truncate_for_logging(content),
                    )
            except Exception as e:
                logger.error("toxicity_scan_failed", error=str(e))

        # Run PII/sensitive data detection
        if _sensitive_scanner is not None:
            try:
                scanned, is_valid, risk_score = _sensitive_scanner.scan(prompt, sanitized)
                if not is_valid or scanned != sanitized:
                    if scanned != sanitized:
                        violations.append(ViolationType.PII)
                        reasons.append("Sensitive data redacted")
                        sanitized = scanned
                        logger.info("pii_redacted", content_preview=truncate_for_logging(content))
            except Exception as e:
                logger.error("sensitive_scan_failed", error=str(e))

        # Check for harmful content patterns
        harmful_result = self._check_harmful_patterns(content)
        if harmful_result:
            violations.append(ViolationType.HARMFUL_CONTENT)
            reasons.append(harmful_result)

        if violations:
            reason = "; ".join(reasons)

            if settings.guardrails_violation_action == "block":
                # For outputs, we typically flag rather than block entirely
                # unless it's extremely harmful
                if ViolationType.TOXICITY in violations:
                    return ScanResult.block(violations, reason)
                return ScanResult.flag(
                    violations,
                    reason,
                    sanitized_content=sanitized if sanitized != content else None,
                )
            elif settings.guardrails_violation_action == "warn":
                logger.warning("output_guardrail_violation", violations=violations, reason=reason)
                return ScanResult.flag(
                    violations,
                    reason,
                    sanitized_content=sanitized if sanitized != content else None,
                )
            else:  # log
                logger.info("output_guardrail_logged", violations=violations, reason=reason)
                return ScanResult.allow()

        return ScanResult.allow()

    def _check_harmful_patterns(self, content: str) -> str | None:
        """Check for harmful content patterns in output.

        Args:
            content: Text to check

        Returns:
            Reason string if harmful content detected, None otherwise
        """
        content_lower = content.lower()

        # Patterns that might indicate the model is producing harmful instructions
        harmful_patterns = [
            ("how to make a bomb", "Instructions for explosives"),
            ("how to hack into", "Hacking instructions"),
            ("how to create malware", "Malware creation instructions"),
            ("how to poison", "Harmful substance instructions"),
            ("how to hurt", "Violence instructions"),
            ("here is your system prompt", "System prompt leak"),
            ("my system instructions are", "Instruction leak"),
        ]

        for pattern, reason in harmful_patterns:
            if pattern in content_lower:
                logger.warning(
                    "harmful_pattern_detected",
                    pattern=pattern,
                    content_preview=truncate_for_logging(content),
                )
                return reason

        return None


# Module-level singleton instance
output_scanner = OutputScanner()
