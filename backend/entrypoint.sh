#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! python - <<'PY'
import os
import socket
import sys

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))

try:
    with socket.create_connection((host, port), timeout=3):
        sys.exit(0)
except OSError:
    sys.exit(1)
PY
do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 1
done

echo "PostgreSQL is up - running migrations"
python manage.py migrate --noinput

echo "Collecting static files"
python manage.py collectstatic --noinput 2>/dev/null || true

echo "Starting server"
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8003 \
    --workers 3 \
    --timeout 120
