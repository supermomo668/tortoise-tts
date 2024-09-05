from types import SimpleNamespace
import concurrent.futures, asyncio
import os, pathlib

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
from app.constants import USE_CELERY, TASK_RETRY_DELAY, TASK_TIMEOUT

tts_instance = None

# queue/task objects if not in Celery mode
if not USE_CELERY:
    logger.info("Running in non-Celery mode")
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=int(os.getenv("MAX_WORKERS", 10))
    )
    fifo_queue = asyncio.Queue()
    tasks: dict[str, Task] = {}
    async def process_requests():
        while True:
            task_id, future = await fifo_queue.get()
            task = tasks[task_id]
            try:
                task.set_in_progress()
                logger.info(f"Processing task {task_id}")
                audio_out = await asyncio.get_event_loop().run_in_executor(
                    executor, local_inference_tts, 
                    {"args": task.request.model_dump()}
                )
                future.set_result(audio_out)
                task.set_completed(audio_out)
            except Exception as e:
                task.set_failed(str(e))
                future.set_exception(e)
            finally:
                fifo_queue.task_done()
                
def get_tts():
    """
    Return the singleton instance of the TTS object.
    Subsequent calls will return the same instance.
    Returns:
        TextToSpeech: The singleton TTS object.
    """
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
        """
        Celery task to perform local TTS inference.
        Returns:
            bytes: The generated audio bytes.
        """
        audio_out = _process_tts_inference(tts_args)
        return audio_out.getvalue()
else:
    def local_inference_tts(tts_args: dict):
        return _process_tts_inference(tts_args)

@retry(stop=stop_after_delay(TASK_TIMEOUT), wait=wait_fixed(5), reraise=True)
async def check_task_status(task_id: str, tasks={}):
    """
    Check the status of a TTS task.
    Args:
        task_id: The task ID to check.
        tasks: The dictionary of tasks, if not using Celery.
    Returns:
        The task object if the task is completed.
        Raises an HTTPException if the task is not found or failed.
        Raises an Exception if the task is not completed yet.
    """
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
    