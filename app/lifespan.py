# app/lifespan.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise.api import TextToSpeech
from tortoise.do_tts import _initialized_tts
from app.models.request import TranscriptionRequest
from app.models.tts import TTSArgs
from app.logger import logger

from tortoise.api import TextToSpeech
from app.routes import text_to_speech  # Ensure this import is correct based on the actual location

# Environment-specific variable to skip initialization during testing
IS_TESTING = os.getenv("TESTING", "False").lower() in ("true", "1")

async def post_initialization_event(tts: TextToSpeech):
    try:
        request = TranscriptionRequest(
            text="Initialized! World", 
            voice="random", preset="ultra_fast"
        )
        response = await text_to_speech(request, tts)
        logger.info(f"Initialized TTS: {response}")
    except Exception as e:
        logger.info("Error during initialization TTS:", str(e))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not IS_TESTING:
        # Initialize the TTS object and store it in the app state
        args = TTSArgs(text="TEST")
        app.state.tts = _initialized_tts(args)
        
        # Pass the initialized TTS object to the post-initialization event
        await post_initialization_event(app.state.tts)
    else:
        print(f"Skipping initialization due to TESTING={IS_TESTING}")
        app.state.tts = None  # No need to initialize TTS if testing

    yield  # Yield control back to FastAPI