# app/lifespan.py
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from app.models.request import TranscriptionRequest
from app.logger import logger

from app.tasks import local_inference_tts, get_tts  # Import the Celery task

# Environment-specific variable to skip initialization during testing
IS_TESTING = os.getenv("TESTING", "False").lower() in ("true", "1")
tts_instance = None

async def text_to_speech(
    request: TranscriptionRequest):
    try:
        # Pass the tts object directly to the task
        task_id = local_inference_tts.s(
            tts_args={'args': request.model_dump()}).apply_async()
        return {"task_id": task_id.id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the TTS object when the application starts
    tts_instance = get_tts()
    if not IS_TESTING:
        # Initialize the TTS object and store it in the app state
        logger.info(f"Initializing TTS model dependencies with mock call")
        try:
            request = TranscriptionRequest(
                text="Initialized!", 
                voice="random", preset="ultra_fast"
            )
            response = await text_to_speech(request)
            if response and response.get('status') == 'success':
                logger.info("Initialized TTS successfully.")
            else:
                logger.info(f"TTS initialization failed with response: {response}")
        except Exception as e:
            logger.info(f"Error during initialization TTS: {str(e)}")
    else:
        print(f"Skipping initialization due to TESTING={IS_TESTING}")
        app.state.tts = None  # No need to initialize TTS if testing

    yield  # Yield control back to FastAPI