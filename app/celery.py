from celery import Celery

# Define the Celery app
celery_app = Celery(
    'app',
    broker='redis://localhost:6379/0',  # Redis URL for the broker
    backend='redis://localhost:6379/0'  # Redis URL for result backend
)

# Load task modules
celery_app.autodiscover_tasks(['app.tasks'])
