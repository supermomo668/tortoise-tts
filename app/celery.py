import os
from celery import Celery

import torch

# torch.multiprocessing.set_start_method('spawn')

# Define the Celery app
celery_app = Celery('app')

# Load configuration from environment variables
celery_app.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
celery_app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
celery_app.conf.task_serializer = os.getenv('CELERY_TASK_SERIALIZER', 'json')
celery_app.conf.result_serializer = os.getenv('CELERY_RESULT_SERIALIZER', 'json')
celery_app.conf.accept_content = os.getenv('CELERY_ACCEPT_CONTENT', 'json').split(',')
celery_app.conf.timezone = os.getenv('CELERY_TIMEZONE', 'UTC')
celery_app.conf.enable_utc = os.getenv('CELERY_ENABLE_UTC', 'True').lower() == 'true'
celery_app.conf.worker_concurrency = int(os.getenv('CELERY_WORKER_CONCURRENCY', '1'))
celery_app.conf.worker_prefetch_multiplier = int(os.getenv('CELERY_PREFETCH_MULTIPLIER', '1'))