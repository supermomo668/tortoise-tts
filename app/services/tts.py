import io, os, uuid
import  asyncio

from fastapi import HTTPException

from app.logger import logger
from app.models.request import TranscriptionRequest
from app.models.tasks import Task
from app.services.task import local_inference_tts
from app.constants import USE_CELERY

# queue/task objects if not in Celery mode
if not USE_CELERY:
  from app.services.task import tasks, fifo_queue

async def text_to_speech(request: TranscriptionRequest):
    if USE_CELERY:
        # Celery task processing as before
        try:
            task_id = local_inference_tts.s(
                tts_args={'args': request.model_dump()}).apply_async()
            return {"task_id": task_id.id, "status": "queued"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Task submission failed: {str(e)}")
    else:
        # Task queuing and processing without Celery
        try:
            task_id = str(uuid.uuid4())
            task = Task(task_id=task_id, request=request)
            tasks[task_id] = task
            future = asyncio.get_event_loop().create_future()
            await fifo_queue.put((task_id, future))
            return {"task_id": task_id, "status": task.state}
        except Exception as e:
            task.error = str(e)
            raise HTTPException(status_code=500, detail=f"Task submission failed: {str(e)}")