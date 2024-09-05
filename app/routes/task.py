import io, os

from fastapi import APIRouter, FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from celery.result import AsyncResult
from celery.app.control import Inspect
from tenacity import RetryError

from app.logger import logger
from app.models.tasks import Task
from app.services.auth import get_current_user
from app.celery import celery_app  # Import the Celery app
from app.services.task import check_task_status, local_inference_tts, get_tts
from app.constants import USE_CELERY

router = APIRouter(
    prefix="/task",
    tags=["task"]
)


if not USE_CELERY:
  from app.services.task import tasks, fifo_queue

@router.get("/queue-status", dependencies=[Depends(get_current_user)])
async def queue_status():
    if USE_CELERY:
        try:
            # Use Celery's inspect to get information about active tasks
            i = Inspect(app=celery_app)
            active_tasks = i.active()
            scheduled_tasks = i.scheduled()
            reserved_tasks = i.reserved()
            
            # Prepare the response
            return {
                "active_tasks": active_tasks,
                "scheduled_tasks": scheduled_tasks,
                "reserved_tasks": reserved_tasks
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"detail": "Error fetching Celery task information", "error": str(e)},
            )
    else:
        return {
            "queue_length": fifo_queue.qsize(), "tasks": tasks
        }

@router.get("/task-status/{task_id}", dependencies=[Depends(get_current_user)])
async def task_status(task_id: str):
    if USE_CELERY:
        task_result = AsyncResult(task_id, app=celery_app)
        if task_result.failed():
            error_msg = task_result.traceback or str(task_result.result)
            logger.error(f"Task {task_id} failed with error: {error_msg}")
            return {"task_id": task_id, "status": "failed", "error": error_msg}
        return {
          "task_id": task_id, "status": task_result.state}
    else:
        task = tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.state == "failed":
            logger.error(f"Task {task_id} failed with error: {task.error}")
            return {"task_id": task_id, "status": "failed", "error": task.error}
        return {
          "task_id": task_id, 
          "status": task.state, 
          "error": task.error
        }

@router.get("/task-result/{task_id}", dependencies=[Depends(get_current_user)])
async def task_result(task_id: str, request: Request):
    """
    Waits for the task to complete and returns the result file if successful.
    
    Args:
        task_id (str): The ID of the task to wait for.
        
    Returns:
        StreamingResponse: The response containing the result file.
    
    Raises:
        HTTPException: If the task is not found, fails, or times out.
    """
    assert await task_status(task_id), "Task not found"
    try:
        if USE_CELERY:
            task = await check_task_status(task_id)
        else:
            task = await check_task_status(task_id, tasks)
        audio_content = task.result
        if not isinstance(audio_content, (bytes , io.BytesIO)):
            raise HTTPException(status_code=500, detail=f"Invalid audio content received, got type: {str(type(audio_content))}")
            # If audio_content is bytes, wrap it in BytesIO
        if isinstance(audio_content, bytes):
            audio_content = io.BytesIO(audio_content)
        logger.info(f"Valid audio content received, size: {audio_content.getbuffer().nbytes} bytes")
        return StreamingResponse(audio_content, media_type="audio/wav")
    except RetryError as e:
        raise HTTPException(status_code=408, detail=f"Task timed out: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
