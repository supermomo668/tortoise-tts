import io, os, uuid
from datetime import timedelta
import concurrent.futures, asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.logger import logger
from app.models.request import TranscriptionRequest
from app.models.tasks import Task
from app.services.auth import get_current_user, verify_user, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.services.task import check_task_status, local_inference_tts, get_tts
from app.constants import USE_CELERY

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)
            
@router.post("/login")
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

@router.get("/verify-token", dependencies=[Depends(get_current_user)])
async def verify_token(request: Request):
  return {"message": "true"}
