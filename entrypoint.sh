#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
#exec uvicorn app.main:app --host 0.0.0.0 --port 8000

if [ $# -eq 0 ]; then
    #start API server
    echo "Starting API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
else
    # Run the celery worker/beat
    echo "Starting custom command: $@"
    exec "$@"
fi