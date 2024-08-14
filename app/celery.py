from celery import Celery
import torch

torch.multiprocessing.set_start_method('spawn')

# Define the Celery app
celery_app = Celery(
    'app',
    broker='redis://localhost:6379/0',  # Redis URL for the broker
    backend='redis://localhost:6379/0'  # Redis URL for result backend
)
celery_app.config_from_object('app.celeryconfig')
# Load task modules
celery_app.autodiscover_tasks(['app.tasks'])
