#!/bin/sh
set -e

python -c "from app.core.config import validate_database_url_or_exit; validate_database_url_or_exit()"

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
