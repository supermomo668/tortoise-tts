# app/lifespan.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import HTTPException, FastAPI
from fastapi.responses import StreamingResponse
from app.models.request import TranscriptionRequest
from app.logger import logger

# Import the Celery task
from app.tasks import local_inference_tts, get_tts, infer_voice  # 
from app.constants import IS_TESTING, USE_CELERY

async def text_to_speech(request: TranscriptionRequest) -> StreamingResponse:
    try:
        if USE_CELERY:
            # Pass the tts object directly to the task using Celery
            task_id = local_inference_tts.s(
                tts_args={'args': request.model_dump()}).apply_async()
            return {"task_id": task_id.id, "status": "queued"}
        else:
            # Process the TTS task synchronously without Celery
            tts = get_tts()
            audio_buffer =  infer_voice(tts, request)
            return StreamingResponse(
                audio_buffer, media_type="audio/wav")
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
                voice="random", preset="ultra_fast", output_path="./data/results/init"
            )
            response = await text_to_speech(request)
            if not USE_CELERY:
                from app.routes import process_requests
                task = asyncio.create_task(process_requests(tts_instance))
            if response and response.status_code == 200:
                logger.info("Initialized TTS successfully.")
            else:
                logger.info(f"TTS initialization failed with response status: {response}")
        except Exception as e:
            logger.info(f"Error during initialization TTS: {str(e)}")
    else:
        print(f"Skipping initialization due to TESTING={IS_TESTING}")
        app.state.tts = None  # No need to initialize TTS if testing

    yield  # Yield control back to FastAPI