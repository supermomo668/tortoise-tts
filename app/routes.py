# app/main.py
import os
from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse
from celery.result import AsyncResult

from tortoise.utils.audio import BUILTIN_VOICES_DIR

from app.models.request import TranscriptionRequest
from app.services.auth import get_current_user, verify_user, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.celery import celery_app  # Import the Celery app
from app.lifespan import text_to_speech

def register_routes(app: FastAPI):  
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
  async def tts(request: TranscriptionRequest):
      return await text_to_speech(request)

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
