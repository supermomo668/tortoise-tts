# find process
ps aux | grep celery
ps aux | grep uvicorn

# manual kill
kill <PID_of_celery_worker>
kill <PID_of_uvicorn>
