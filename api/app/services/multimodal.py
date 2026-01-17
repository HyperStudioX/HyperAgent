"""Multimodal services - backward compatibility layer.

This module re-exports services from their individual modules for backward compatibility.
New code should import directly from the specific service modules:
- vision.py: Image understanding
- image_generation.py: Image generation
- audio_transcription.py: Audio transcription
- text_to_speech.py: Text-to-speech
"""

from typing import Optional

from app.services.audio_transcription import (
    AudioTranscriptionService,
    audio_transcription_service,
)
from app.services.image_generation import (
    ImageGenerationService,
    image_generation_service,
)
from app.services.text_to_speech import TextToSpeechService, text_to_speech_service
from app.services.vision import VisionService, vision_service


class AudioService:
    """Unified audio service combining transcription and TTS for backward compatibility."""

    def __init__(self):
        self._transcription = audio_transcription_service
        self._tts = text_to_speech_service

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
        return await self._transcription.transcribe(audio_data, language, model)

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
        return await self._tts.text_to_speech(text, voice, model)


# Global service instances (backward compatibility)
audio_service = AudioService()

# Re-export individual service classes and instances
__all__ = [
    # Classes
    "VisionService",
    "ImageGenerationService",
    "AudioTranscriptionService",
    "TextToSpeechService",
    "AudioService",
    # Instances
    "vision_service",
    "image_generation_service",
    "audio_transcription_service",
    "text_to_speech_service",
    "audio_service",
]
