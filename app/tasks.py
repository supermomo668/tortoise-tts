from types import SimpleNamespace
from pathlib import Path

from fastapi import HTTPException
from tenacity import retry, stop_after_delay, wait_fixed, RetryError
from celery.result import AsyncResult

from tortoise.do_tts import infer_voice
from tortoise.do_tts import _initialized_tts

from app.logger import logger
from app.celery import celery_app
from app.models.tts import TTSInitArgs
from app.models.tasks import Task
from app.models.request import TranscriptionRequest
from app.constants import IS_TESTING, USE_CELERY, TASK_RETRY_DELAY, TASK_TIMEOUT

tts_instance = None

def get_tts():
    global tts_instance
    if tts_instance is None:
        logger.info("Initializing TTS object...")
        tts_instance = _initialized_tts(TTSInitArgs())  # Replace with actual initialization logic
    return tts_instance

def _process_tts_inference(tts_args: dict):
    # Unpack the args and process the TTS task
    tts_args = TranscriptionRequest(**tts_args.get('args'))
    logger.info(f"TTS Inference input args: {tts_args}")
    return infer_voice(
        get_tts(), SimpleNamespace(**tts_args.model_dump())
    )

if USE_CELERY:
    @celery_app.task(bind=True)
    def local_inference_tts(self, tts_args: dict):
        audio_out = _process_tts_inference(tts_args)
        return audio_out.getvalue()
else:
    def local_inference_tts(tts_args: dict):
        return _process_tts_inference(tts_args)

@retry(stop=stop_after_delay(TASK_TIMEOUT), wait=wait_fixed(5), reraise=True)
async def check_task_status(task_id: str, tasks={}):
    if USE_CELERY:
        task = AsyncResult(task_id, app=celery_app)
    else:
        task = tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    # task status code
    if task.state == Task.FAILED:
        details = (task.info or 'Unknown error') if USE_CELERY else task.error
        raise HTTPException(status_code=500, detail=f"Task failed: {details}")
    if task.state != Task.COMPLETED:
        raise Exception("Task not completed yet")
    # return task
    return task 
    