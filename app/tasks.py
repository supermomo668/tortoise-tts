from types import SimpleNamespace
from pathlib import Path
# from celery import shared_task
from app.logger import logger
from app.celery import celery_app

from app.models.tts import TTSInitArgs
from app.models.request import TranscriptionRequest

from tortoise.do_tts import infer_voice
from tortoise.do_tts import _initialized_tts


tts_instance = None

def get_tts():
    global tts_instance
    if tts_instance is None:
        logger.info("Initializing TTS object...")
        tts_instance = _initialized_tts(TTSInitArgs())  # Replace with actual initialization logic
    return tts_instance

@celery_app.task(bind=True)
def local_inference_tts(self, tts_args: dict):
    # Unpack the args and process the TTS task
    tts = get_tts()
    tts_args = TranscriptionRequest(**tts_args.get('args'))
    logger.info(f"TTS Inference input args: {tts_args}")
    Path(tts_args.output_path).mkdir(
        parents=True, exist_ok=True)
    output_path = infer_voice(
        tts, SimpleNamespace(**tts_args.model_dump())
    )
    return output_path