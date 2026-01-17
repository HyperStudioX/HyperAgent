"""Router for multimodal AI services (vision, image generation, audio)."""

import base64
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.models.schemas import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    TextToSpeechRequest,
    TranscriptionResponse,
    VisionAnalysisRequest,
    VisionAnalysisResponse,
)
from app.services.audio_transcription import audio_transcription_service
from app.services.image_generation import image_generation_service
from app.services.text_to_speech import text_to_speech_service
from app.services.vision import vision_service

logger = get_logger(__name__)

router = APIRouter(prefix="/multimodal")


@router.post("/vision/analyze", response_model=VisionAnalysisResponse)
async def analyze_image(
    request: VisionAnalysisRequest,
    image: UploadFile = File(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Analyze an image with Gemini vision model.

    Accepts either:
    - image_data in request body (base64)
    - image file as multipart upload
    """
    try:
        # Get image data from either source
        if image:
            image_data = await image.read()
        elif request.image_data:
            image_data = request.image_data
        else:
            raise HTTPException(
                status_code=400,
                detail="Either image file or image_data must be provided",
            )

        # Analyze image
        analysis = await vision_service.analyze_image(
            image_data=image_data,
            prompt=request.prompt,
            model=request.model,
        )

        return VisionAnalysisResponse(analysis=analysis)

    except Exception as e:
        logger.error(f"Vision analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/images/generate", response_model=ImageGenerationResponse)
async def generate_images(
    request: ImageGenerationRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Generate images from text prompt using Gemini Imagen."""
    try:
        images = await image_generation_service.generate_image(
            prompt=request.prompt,
            size=request.size,
            n=request.n,
            safety_filter=request.safety_filter,
            model=request.model,
        )

        return ImageGenerationResponse(images=images)

    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str | None = None,
    model: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Transcribe audio file using Gemini."""
    try:
        # Read audio data
        audio_data = await audio.read()

        # Transcribe
        result = await audio_transcription_service.transcribe(
            audio_data=audio_data,
            language=language,
            model=model,
        )

        return TranscriptionResponse(
            text=result["text"],
            language=result.get("language"),
            duration=result.get("duration"),
        )

    except Exception as e:
        logger.error(f"Audio transcription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio/tts")
async def text_to_speech(
    request: TextToSpeechRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Convert text to speech using Gemini TTS."""
    try:
        # Generate speech
        audio_data = await text_to_speech_service.text_to_speech(
            text=request.text,
            voice=request.voice,
            model=request.model,
        )

        # Return audio file
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="speech.mp3"',
            },
        )

    except Exception as e:
        logger.error(f"Text-to-speech failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
