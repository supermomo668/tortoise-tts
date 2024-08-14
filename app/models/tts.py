import os
from typing import Optional
from pydantic import BaseModel
from enum import Enum

from tortoise.do_tts import pick_best_batch_size_for_gpu
from tortoise.api import MODELS_DIR
from tortoise.api import TextToSpeech

from .request import Presets

class TTSInitArgs(BaseModel):
    model_dir: str = os.getenv("TORTOISE_MODELS_DIR", MODELS_DIR)
    use_deepspeed: bool = False
    kv_cache: bool = True
    autoregressive_batch_size: int = pick_best_batch_size_for_gpu()
    half: bool = True

class TTSResponse(BaseModel):
    # Define the fields for the response model
    task_id: str
    status: str

class TTSWrapper:
    def __init__(self, tts: TextToSpeech):
        self.tts = tts