from celery import shared_task
from tortoise.do_tts import infer_voice

@shared_task(name="tts_inference_task")
def local_inference_tts(tts_args):
    # Unpack the args and process the TTS task
    output_path = infer_voice(tts_args['tts'], tts_args['args'])
    return output_path

