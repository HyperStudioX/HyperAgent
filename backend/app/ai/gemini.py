"""Shared Gemini client initialization."""

from google import genai

from app.config import get_settings


def get_gemini_client() -> genai.Client:
    """Get configured Gemini client (Vertex AI or API key)."""
    settings = get_settings()
    if settings.gemini_use_vertex_ai:
        return genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
    return genai.Client(api_key=settings.gemini_api_key)
