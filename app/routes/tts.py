import io, os, uuid
import  asyncio

from fastapi import APIRouter, FastAPI, Depends, HTTPException, Request
from fastapi.responses import  JSONResponse
from app.logger import logger
from app.models.request import TranscriptionRequest

from app.services.tts import text_to_speech
from app.services.auth import get_current_user
from app.constants import USE_CELERY

from tortoise.utils.audio import BUILTIN_VOICES_DIR

# queue/task objects if not in Celery mode
if not USE_CELERY:
  from .task import tasks, fifo_queue

router = APIRouter(
    prefix="/tts",
    tags=["tts"]
)

@router.get("/voices")
async def available_voices():
    return JSONResponse(content={"voices": os.listdir(BUILTIN_VOICES_DIR)})
    
@router.post("", dependencies=[Depends(get_current_user)])
async def tts(request: TranscriptionRequest):
    return await text_to_speech(request)
