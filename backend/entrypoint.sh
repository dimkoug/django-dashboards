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

# Hand off to the compose `command` (makemigrations + migrate + collectstatic
# + uvicorn) as PID 1.
exec "$@"
