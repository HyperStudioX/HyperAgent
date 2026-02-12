"""Sandbox App Reverse Proxy.

Routes browser requests for sandbox apps through the backend so that
iframe previews work without direct access to Docker-mapped ports.
"""

import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.sandbox.app_sandbox_manager import get_app_sandbox_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/sandbox/app", tags=["sandbox-proxy"])

# Shared async HTTP client (created lazily, reused across requests)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )
    return _http_client


# Headers that should not be forwarded to the sandbox
_HOP_BY_HOP_HEADERS = frozenset({
    "host",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "proxy-authenticate",
})

# Regex to find <head> or <head ...> tag for base-href injection
_HEAD_TAG_RE = re.compile(rb"(<head[^>]*>)", re.IGNORECASE)


def _inject_base_href(body: bytes, sandbox_id: str) -> bytes:
    """Inject a <base href> tag after <head> so relative URLs route through the proxy."""
    base_tag = f'<base href="/api/v1/sandbox/app/{sandbox_id}/">'.encode()
    match = _HEAD_TAG_RE.search(body)
    if match:
        insert_pos = match.end()
        return body[:insert_pos] + base_tag + body[insert_pos:]
    return body


@router.api_route(
    "/{sandbox_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"],
)
@router.api_route(
    "/{sandbox_id}",
    methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"],
)
async def proxy_sandbox_app(
    sandbox_id: str,
    request: Request,
    path: str = "",
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Reverse-proxy a request to the sandbox app's dev server.

    Looks up the sandbox session, forwards the request to its internal URL,
    and returns the response. For HTML responses, injects a <base href> tag
    so that relative resource URLs (JS, CSS, images) resolve through the proxy.
    """
    manager = get_app_sandbox_manager()
    session = await manager.get_session_by_sandbox_id(sandbox_id)

    if not session:
        raise HTTPException(status_code=404, detail="Sandbox session not found")

    if not session.internal_url:
        raise HTTPException(status_code=502, detail="Sandbox app not started")

    # Build target URL
    target_base = session.internal_url.rstrip("/")
    target_url = f"{target_base}/{path}" if path else f"{target_base}/"

    # Forward query string
    query_string = str(request.query_params)
    if query_string:
        target_url = f"{target_url}?{query_string}"

    # Build forwarded headers
    forward_headers = {}
    for key, value in request.headers.items():
        if key.lower() not in _HOP_BY_HOP_HEADERS:
            forward_headers[key] = value

    # Read request body for non-GET/HEAD
    body: bytes | None = None
    if request.method not in ("GET", "HEAD"):
        body = await request.body()

    client = _get_http_client()

    try:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail="Cannot connect to sandbox app — the dev server may not be running",
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Sandbox app request timed out")

    # Build response headers (filter hop-by-hop)
    response_headers: dict[str, str] = {}
    for key, value in resp.headers.items():
        if key.lower() not in _HOP_BY_HOP_HEADERS:
            response_headers[key] = value

    content_type = resp.headers.get("content-type", "")
    resp_body = resp.content

    # Inject <base href> into HTML responses so relative URLs work
    if "text/html" in content_type:
        resp_body = _inject_base_href(resp_body, sandbox_id)
        # Update content-length after injection
        response_headers["content-length"] = str(len(resp_body))

    return Response(
        content=resp_body,
        status_code=resp.status_code,
        headers=response_headers,
    )
