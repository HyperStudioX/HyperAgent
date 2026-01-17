"""Audio transcription service using Gemini."""

import io
from typing import Optional

from app.config import settings


class AudioTranscriptionService:
    """Audio transcription using Gemini."""

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        """Transcribe audio using Gemini.

        Args:
            audio_data: Audio file data
            language: Optional language hint (not used by Gemini, auto-detected)
            model: Optional model override (defaults to configured transcription model)

        Returns:
            Dict with text, language (None for Gemini), and duration (None for Gemini)
        """
        import google.generativeai as genai

        # Use configured model if not specified
        if model is None:
            model = settings.audio_transcription_model

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

        # Upload audio file
        audio_file = io.BytesIO(audio_data)
        uploaded_file = genai.upload_file(audio_file, mime_type="audio/mp3")

        # Create model and transcribe
        gemini_model = genai.GenerativeModel(model)
        response = await gemini_model.generate_content_async(
            [uploaded_file, "Transcribe this audio file."]
        )

        return {
            "text": response.text,
            "language": None,  # Gemini auto-detects, doesn't return language
            "duration": None,  # Gemini doesn't return duration
        }


# Global service instance
audio_transcription_service = AudioTranscriptionService()
