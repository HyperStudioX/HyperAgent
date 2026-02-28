"""HTTP API Client Tool.

Provides a generic HTTP client tool for making requests to external APIs.
Includes URL validation, response size limiting, and security checks.
"""

import ipaddress
import json
from urllib.parse import urlparse

import aiohttp
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum response body size (1 MB)
MAX_RESPONSE_SIZE = 1 * 1024 * 1024

# Allowed HTTP methods
ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/internal IP address."""
    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local
    except ValueError:
        # Not a raw IP address; hostname will be resolved by aiohttp.
        # Block common internal hostnames.
        lower = hostname.lower()
        blocked = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "metadata.google.internal",
            "169.254.169.254",
        ]
        return any(lower == b or lower.endswith("." + b) for b in blocked)


def _validate_request_url(url: str) -> tuple[bool, str | None]:
    """Validate a URL for HTTP requests.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    if not parsed.scheme:
        return False, "URL must include a scheme (e.g., https://)"
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme: {parsed.scheme}. Use http or https."
    if not parsed.netloc:
        return False, "URL must include a host"

    hostname = parsed.hostname or ""
    if _is_private_ip(hostname):
        return False, f"Requests to private/internal addresses are blocked: {hostname}"

    return True, None


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class HttpRequestInput(BaseModel):
    """Input schema for http_request tool."""

    url: str = Field(
        ...,
        description="The URL to request",
    )
    method: str = Field(
        default="GET",
        description="HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)",
    )
    headers: dict | None = Field(
        default=None,
        description="Optional HTTP headers as key-value pairs",
    )
    body: str | None = Field(
        default=None,
        description="Optional request body (JSON string for POST/PUT/PATCH)",
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Request timeout in seconds (1-120)",
    )


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool(args_schema=HttpRequestInput)
async def http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
    timeout: int = 30,
) -> str:
    """Make an HTTP request to an external API.

    Use this tool to call REST APIs, fetch data from web services, or send
    webhooks. Supports GET, POST, PUT, DELETE, PATCH, HEAD, and OPTIONS methods.

    For JSON APIs, pass a JSON string as the body and include
    'Content-Type: application/json' in headers.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
        headers: Optional HTTP headers as key-value pairs
        body: Optional request body (JSON string)
        timeout: Request timeout in seconds (1-120)

    Returns:
        Response status code, headers, and body
    """
    logger.info("http_request_invoked", url=url[:100], method=method)

    # Validate URL
    is_valid, error_msg = _validate_request_url(url)
    if not is_valid:
        logger.warning("http_request_invalid_url", url=url[:100], error=error_msg)
        return json.dumps({"success": False, "error": error_msg})

    # Validate method
    method_upper = method.upper()
    if method_upper not in ALLOWED_METHODS:
        return json.dumps({
            "success": False,
            "error": f"Unsupported HTTP method: {method}. Allowed: {', '.join(sorted(ALLOWED_METHODS))}",
        })

    request_headers = dict(headers) if headers else {}

    try:
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.request(
                method=method_upper,
                url=url,
                headers=request_headers,
                data=body.encode("utf-8") if body else None,
            ) as response:
                # Read response with size limit
                response_body = await response.content.read(MAX_RESPONSE_SIZE)
                truncated = not response.content.at_eof()

                # Decode response
                try:
                    body_text = response_body.decode("utf-8")
                except UnicodeDecodeError:
                    body_text = response_body.decode("latin-1")

                # Try to pretty-print JSON responses
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type or "javascript" in content_type:
                    try:
                        parsed_json = json.loads(body_text)
                        body_text = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass

                # Build response headers dict (limit to useful headers)
                resp_headers = {}
                for key in ["Content-Type", "Content-Length", "Location", "Set-Cookie", "X-Request-Id"]:
                    if key in response.headers:
                        resp_headers[key] = response.headers[key]

                result = {
                    "success": True,
                    "status_code": response.status,
                    "headers": resp_headers,
                    "body": body_text[:MAX_RESPONSE_SIZE],
                }

                if truncated:
                    result["truncated"] = True
                    result["message"] = f"Response truncated to {MAX_RESPONSE_SIZE} bytes"

                logger.info(
                    "http_request_completed",
                    url=url[:100],
                    status_code=response.status,
                    body_length=len(body_text),
                )

                return json.dumps(result)

    except aiohttp.ClientError as e:
        logger.error("http_request_client_error", url=url[:100], error=str(e))
        return json.dumps({"success": False, "error": f"HTTP request failed: {e}"})
    except TimeoutError:
        logger.error("http_request_timeout", url=url[:100], timeout=timeout)
        return json.dumps({"success": False, "error": f"Request timed out after {timeout} seconds"})
    except Exception as e:
        logger.error("http_request_failed", url=url[:100], error=str(e))
        return json.dumps({"success": False, "error": f"Request failed: {e}"})
