import os
# Environment-specific variable to skip initialization during testing
IS_TESTING = os.getenv("TESTING", "False").lower() in ("true", "1")
tts_instance = None
USE_CELERY = os.getenv("USE_CELERY", "False").lower() in ("true", "1")
TASK_RETRY_DELAY  = int(os.getenv("TASK_RETRY_DELAY", 2))
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", 60))