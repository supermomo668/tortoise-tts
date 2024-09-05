# run redis
docker run -p 6379:6379 -d redis

# Start Celery worker
echo "Starting Celery worker..."
celery -A app.celery.celery_app worker --loglevel=info &

# Start Uvicorn
echo "Starting Uvicorn server..."
uvicorn app.main:app --port 42110 --host 0.0.0.0 --reload &

# Wait for both processes to finish
wait