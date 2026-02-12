"""Tool scanner for validating tool arguments before execution."""

from urllib.parse import urlparse

from app.config import settings
from app.core.logging import get_logger
from app.guardrails.base import ScanResult, ViolationType

logger = get_logger(__name__)

# Blocked domains for URL validation
BLOCKED_DOMAINS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "internal",
    "local",
    "intranet",
    "corp",
    "private",
}

# Blocked URL schemes
BLOCKED_SCHEMES = {
    "file",
    "ftp",
    "ssh",
    "telnet",
    "sftp",
    "smb",
    "nfs",
    "data",  # data: URLs can be used for XSS
}

# Tools that involve URL navigation
URL_TOOLS = {
    "browser_navigate",
    "computer_tool",
    "web_search",
    "fetch_url",
}

# Tools that involve code execution
CODE_TOOLS = {
    "execute_code",
    "run_python",
    "run_shell",
    "code_sandbox",
}


class ToolScanner:
    """Scanner for validating tool arguments before execution."""

    def __init__(self):
        """Initialize the tool scanner."""
        self._enabled = settings.guardrails_enabled and settings.guardrails_tool_enabled

    async def scan(self, tool_name: str, args: dict) -> ScanResult:
        """Scan tool arguments for safety violations.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments

        Returns:
            ScanResult indicating whether tool execution is safe
        """
        if not self._enabled:
            return ScanResult.allow()

        # URL validation for browser/network tools
        if tool_name in URL_TOOLS:
            url = args.get("url", "") or args.get("query", "")
            if url:
                result = self._validate_url(url)
                if not result.passed:
                    return result

        # Code safety checks
        if tool_name in CODE_TOOLS:
            code = args.get("code", "") or args.get("command", "")
            if code:
                result = self._validate_code(code)
                if not result.passed:
                    return result

        return ScanResult.allow()

    def _validate_url(self, url: str) -> ScanResult:
        """Validate a URL for safety.

        Args:
            url: URL to validate

        Returns:
            ScanResult indicating whether URL is safe
        """
        try:
            parsed = urlparse(url)

            # Check scheme
            scheme = parsed.scheme.lower()
            if scheme in BLOCKED_SCHEMES:
                logger.warning(
                    "blocked_url_scheme",
                    url=url[:100],
                    scheme=scheme,
                )
                return ScanResult.block(
                    [ViolationType.INVALID_URL],
                    f"URL scheme '{scheme}' is not allowed for security reasons",
                )

            # Check for internal/localhost domains
            netloc = parsed.netloc.lower()

            # Check explicit blocked domains using exact matching
            # Extract hostname without port
            hostname = netloc.split(":")[0]
            for blocked in BLOCKED_DOMAINS:
                if hostname == blocked or hostname.endswith("." + blocked):
                    logger.warning(
                        "blocked_url_domain",
                        url=url[:100],
                        blocked_domain=blocked,
                    )
                    return ScanResult.block(
                        [ViolationType.INVALID_URL],
                        "Access to internal or local resources is not allowed",
                    )

            # Check for IP addresses in private ranges
            if self._is_private_ip(netloc):
                logger.warning(
                    "blocked_private_ip",
                    url=url[:100],
                    netloc=netloc,
                )
                return ScanResult.block(
                    [ViolationType.INVALID_URL],
                    "Access to private IP addresses is not allowed",
                )

            return ScanResult.allow()

        except Exception as e:
            logger.warning("url_validation_failed", url=url[:100], error=str(e))
            return ScanResult.block(
                [ViolationType.INVALID_URL],
                f"Invalid URL: {str(e)}",
            )

    def _is_private_ip(self, netloc: str) -> bool:
        """Check if the netloc contains a private IP address.

        Uses Python's ipaddress module for robust detection of private,
        loopback, reserved, and link-local addresses across IPv4 and IPv6,
        including octal and hex representations.

        Args:
            netloc: Network location string (host:port)

        Returns:
            True if private IP detected
        """
        import ipaddress

        # Extract just the host part (remove port if present)
        host = netloc.split(":")[0]
        # Handle IPv6 addresses in brackets
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return True
        except ValueError:
            pass  # Not an IP address, check domain patterns below

        # Also check for obfuscated IP formats (octal, hex, decimal)
        # e.g., 0x7f000001 = 127.0.0.1, 2130706433 = 127.0.0.1
        try:
            # Try interpreting as integer IP
            if host.startswith("0x") or host.startswith("0X"):
                ip_int = int(host, 16)
            elif host.isdigit():
                ip_int = int(host)
            else:
                return False
            ip = ipaddress.ip_address(ip_int)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return True
        except (ValueError, OverflowError):
            pass

        return False

    def _validate_code(self, code: str) -> ScanResult:
        """Validate code for safety.

        Args:
            code: Code to validate

        Returns:
            ScanResult indicating whether code is safe
        """
        import re

        code_lower = code.lower()

        # Dangerous commands/patterns (simple substring match)
        dangerous_patterns = [
            ("rm -rf /", "Destructive file system command"),
            ("rm -rf ~", "Destructive file system command"),
            (":(){:|:&};:", "Fork bomb detected"),
            ("mkfs.", "File system format command"),
            ("dd if=", "Low-level disk operation"),
            ("chmod 777 /", "Dangerous permission change"),
            ("> /dev/sda", "Direct disk write"),
        ]

        for pattern, reason in dangerous_patterns:
            if pattern in code_lower:
                logger.warning(
                    "dangerous_code_pattern",
                    pattern=pattern,
                    code_preview=code[:100],
                )
                return ScanResult.block(
                    [ViolationType.UNSAFE_CODE],
                    f"Potentially dangerous code detected: {reason}",
                )

        # Regex patterns for remote code execution (curl/wget piped to shell)
        rce_patterns = [
            (r"curl\s+.*\|\s*(ba)?sh", "Remote code execution pattern (curl | sh/bash)"),
            (r"wget\s+.*\|\s*(ba)?sh", "Remote code execution pattern (wget | sh/bash)"),
        ]

        for pattern, reason in rce_patterns:
            if re.search(pattern, code_lower):
                logger.warning(
                    "dangerous_code_pattern",
                    pattern=pattern,
                    code_preview=code[:100],
                )
                return ScanResult.block(
                    [ViolationType.UNSAFE_CODE],
                    f"Potentially dangerous code detected: {reason}",
                )

        return ScanResult.allow()


# Module-level singleton instance
tool_scanner = ToolScanner()
