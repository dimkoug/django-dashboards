#!/bin/sh
set -e

# Wait for the database (pgbouncer) to accept connections before starting.
python - <<'PY'
import os, socket, sys, time

host = os.environ.get("DB_HOST", "pgbouncer")
port = int(os.environ.get("DB_PORT", "5432"))
for _ in range(30):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"Database reachable at {host}:{port}")
            break
    except OSError:
        print(f"Waiting for database at {host}:{port}...")
        time.sleep(1)
else:
    sys.exit(f"Database {host}:{port} not reachable after 30s")
PY

# Generate migrations from current models, then apply them, before the server
# starts. No migration files are committed — they are regenerated every start,
# so log the generation explicitly (verbosity 2) on each boot.
echo "================ [entrypoint] makemigrations (auto, every start) ================"
python manage.py makemigrations --noinput --verbosity 2
echo "================ [entrypoint] migrate =========================================="
python manage.py migrate --noinput --verbosity 2
echo "================ [entrypoint] migrations done =================================="
python manage.py collectstatic --noinput

# Hand off to the CMD (uvicorn) as PID 1.
exec "$@"
