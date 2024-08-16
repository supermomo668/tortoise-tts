import io, os, uuid
from datetime import timedelta
import concurrent.futures, asyncio

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from celery.result import AsyncResult
from celery.app.control import Inspect
from tenacity import RetryError

from app.logger import logger
from app.models.request import TranscriptionRequest
from app.models.tasks import Task
from app.services.auth import get_current_user, verify_user, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.celery import celery_app  # Import the Celery app
from app.tasks import check_task_status, local_inference_tts, get_tts
from app.constants import USE_CELERY

from tortoise.utils.audio import BUILTIN_VOICES_DIR

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
                task.set_completed(audio_out)
                future.set_result(audio_out)
            except Exception as e:
                task.set_failed(str(e))
                future.set_exception(e)
            finally:
                fifo_queue.task_done()
                
async def text_to_speech(request: TranscriptionRequest):
    if USE_CELERY:
        # Celery task processing as before
        task_id = local_inference_tts.s(
            tts_args={'args': request.model_dump()}).apply_async()
        return {"task_id": task_id.id, "status": "queued"}
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
            raise HTTPException(status_code=500, detail=str(e))
            
def register_routes(app: FastAPI):  
    @app.get("/", response_class=HTMLResponse)
    async def home():
        html_content = """
        <html>
            <head>
                <title>FiCast-TTS Home</title>
            </head>
            <body>
                <h1>Welcome to FiCast-TTS!</h1>
                <p>Check the API documentation at <a href="/docs">/docs</a>.</p>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)

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

    @app.get("/verify-token", dependencies=[Depends(get_current_user)])
    async def verify_token(request: Request):
      return {"message": "true"}
    
    @app.get("/voices")
    async def available_voices():
            return JSONResponse(content={"voices": os.listdir(BUILTIN_VOICES_DIR)})
        
    @app.post("/tts", dependencies=[Depends(get_current_user)])
    async def tts(request: TranscriptionRequest):
        return await text_to_speech(request)
        
    @app.get("/queue-status", dependencies=[Depends(get_current_user)])
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
    
    @app.get("/task-status/{task_id}", dependencies=[Depends(get_current_user)])
    async def task_status(task_id: str):
        if USE_CELERY:
            task_result = AsyncResult(task_id, app=celery_app)
            return {"task_id": task_id, "status": task_result.state}
        else:
            task = tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return {"task_id": task_id, "status": task.state, "error": task.error}

    @app.get("/task-result/{task_id}", dependencies=[Depends(get_current_user)])
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
