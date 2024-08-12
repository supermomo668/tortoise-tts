import os
import sys
import uuid
import asyncio
import dotenv
import logging
from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from celery.result import AsyncResult

from tortoise.api import TextToSpeech
from tortoise.utils.audio import BUILTIN_VOICES_DIR
from tortoise.do_tts import _initialized_tts, infer_voice

from app.models.request import TranscriptionRequest
from app.models.tts import TTSArgs
from app.services.auth import get_current_user, verify_user, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.celery import celery_app  # Import the Celery app
from app.tasks import local_inference_tts  # Import the Celery task


load_envar = dotenv.load_dotenv()
assert load_envar and os.getenv("DEFAULT_USERNAME"), "Missing environment variables at .env"

# Environment-specific variable to skip initialization during testing
IS_TESTING = os.getenv("TESTING", "False").lower() in ("true", "1")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
    handlers=[
        logging.FileHandler("app_debug.log"),  # Log to a file named `app_debug.log`
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)

async def post_initialization_event(tts: TextToSpeech):
    try:
        request = TranscriptionRequest(
            text="Initialized! World", 
            voice="random", preset="ultra_fast"
        )
        response = await text_to_speech(request, tts=tts)
        print("Initialization TTS Response:", response)
    except Exception as e:
        print("Error during initialization TTS:", str(e))

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
    
app = FastAPI(lifespan=lifespan)

async def get_tts(app: FastAPI = Depends()) -> TextToSpeech:
    tts = app.state.tts
    if tts is None:
        raise HTTPException(status_code=503, detail="TTS service not initialized.")
    return tts

@app.get("/")
async def home():
    return JSONResponse(content={
        "message": "Hello, FiCast-TTS! Check the docs at /docs."})

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if verify_user(form_data.username, form_data.password):
        try:
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": form_data.username}, expires_delta=access_token_expires
            )
            return {
                "access_token": access_token, 
                "token_type": "bearer", 
                "user": form_data.username
            }
        except:
            raise HTTPException(
                status_code=401, detail="Unable to create access token")
    raise HTTPException(
        status_code=401, detail="Incorrect username or password")

@app.get("/voices")
async def available_voices():
    return JSONResponse(content={"voices": os.listdir(BUILTIN_VOICES_DIR)})

@app.post("/tts", response_model=None, dependencies=[Depends(get_current_user)])
async def text_to_speech(request: TranscriptionRequest, tts=Depends(get_tts)):
    try:
        args = TTSArgs(
            text=request.text,
            voice=request.voice,
            preset=request.preset
        )
        # Pass the tts object directly to the task
        task_id = local_inference_tts.s(tts_args={'tts': tts, 'args': args}).apply_async()
        return {"task_id": task_id.id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue-status", dependencies=[Depends(get_current_user)])
async def queue_status():
    try:
        # There isn't a direct queue length in Celery, so we will just return an empty dict for compatibility
        return {
            "queue_length": "unknown (Celery doesn't expose this easily)",
            "tasks": {}  # Placeholder, Celery tasks can be checked individually
        }
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail, "headers": e.headers, "error": str(e)},
        )

@app.get("/task-status/{task_id}", dependencies=[Depends(get_current_user)])
async def task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.state == 'PENDING':
        return {"task_id": task_id, "status": "queued"}
    elif task_result.state == 'SUCCESS':
        return {"task_id": task_id, "status": "completed", "result": task_result.result}
    elif task_result.state == 'FAILURE':
        raise HTTPException(status_code=500, detail=str(task_result.info))
    else:
        return {"task_id": task_id, "status": task_result.state}

@app.get("/task-result/{task_id}", dependencies=[Depends(get_current_user)])
async def wait_for_result(task_id: str, request: Request):
    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.state == 'SUCCESS':
        output_path = task_result.result
        if not os.path.isfile(output_path):
            raise HTTPException(status_code=404, detail=f"File not found: {output_path}")
        return FileResponse(
            output_path, 
            filename=os.path.basename(output_path), 
            media_type="audio/wav"
        )
    elif task_result.state == 'FAILURE':
        raise HTTPException(status_code=500, detail=str(task_result.info))
    else:
        raise HTTPException(status_code=425, detail="Task not ready yet")
