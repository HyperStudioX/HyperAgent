"""Text-to-speech service using Gemini."""

import base64
from typing import Optional

from app.config import settings


class TextToSpeechService:
    """Text-to-speech using Gemini."""

    async def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
    ) -> bytes:
        """Generate speech using Gemini TTS.

        Args:
            text: Text to convert
            voice: Voice name (Puck, Charon, Kore, Fenrir, Aoede)
            model: Optional model override (defaults to configured TTS model)

        Returns:
            Audio data as bytes
        """
        import google.generativeai as genai

        # Use configured defaults
        if voice is None:
            voice = settings.audio_tts_voice
        if model is None:
            model = settings.audio_tts_model

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

        # Create model with speech configuration
        gemini_model = genai.GenerativeModel(model)

        # Generate speech
        response = await gemini_model.generate_content_async(
            text,
            generation_config={
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": voice}}
                },
            },
        )

        # Get audio data from response
        if hasattr(response, "candidates") and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    return base64.b64decode(part.inline_data.data)

        raise ValueError("No audio data returned from Gemini TTS")


# Global service instance
text_to_speech_service = TextToSpeechService()
