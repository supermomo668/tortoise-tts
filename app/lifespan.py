# app/lifespan.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import HTTPException, FastAPI
from fastapi.responses import StreamingResponse
from app.models.request import TranscriptionRequest
from app.logger import logger

# Import the Celery task
from app.constants import IS_TESTING, USE_CELERY
from app.routes import text_to_speech

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None  # Ensure task is defined
    # Initialize the TTS object when the application starts
    if not IS_TESTING:
        # Initialize the TTS object and store it in the app state
        logger.info(f"Initializing TTS model dependencies with mock call")
        try:
            request = TranscriptionRequest(
                text="Initialized!", 
                voice="random", preset="ultra_fast", output_path="./data/results/init"
            )
            if not USE_CELERY:
                logger.info(f"Task added to the non-celery queue")
                from app.routes import process_requests, fifo_queue, executor
                task = asyncio.create_task(process_requests())
            response = await text_to_speech(request)
            if response:
                logger.info("Initialized TTS successfully.")
            else:
                logger.info(f"TTS initialization failed with response status: {response}")
        except Exception as e:
            logger.info(f"Error during initialization TTS: {str(e)}")
    else:
        print(f"Skipping initialization due to TESTING={IS_TESTING}")
        app.state.tts = None  # No need to initialize TTS if testing
    yield  # Yield control back to FastAPI
    # Graceful shutdown
    if task:
        await fifo_queue.join()  # Wait for the queue to empty
        task.cancel()  # Cancel the task to exit the loop
        try:
            await task
        except asyncio.CancelledError:
            pass
    if not USE_CELERY:
        # Shut down the executor
        executor.shutdown(wait=True)