#!/bin/sh
# Container entrypoint for the API and Celery worker.
#  1. Waits until the database host:port (parsed from DATABASE_URL) accepts TCP connections.
#  2. Runs `alembic upgrade head` when RUN_MIGRATIONS=true (only the api service sets this).
#  3. Execs the given command (gunicorn / uvicorn / celery ...).
set -eu

DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"

if [ -n "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] waiting for database (timeout ${DB_WAIT_TIMEOUT}s)..."
    python - <<'PY'
import os
import socket
import sys
import time
from urllib.parse import urlsplit

url = urlsplit(os.environ["DATABASE_URL"])
host = url.hostname
if not host:
    # e.g. sqlite: nothing to wait for
    sys.exit(0)
port = url.port or 5432
deadline = time.monotonic() + int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        if time.monotonic() > deadline:
            sys.stderr.write(f"[entrypoint] database {host}:{port} not reachable\n")
            sys.exit(1)
        time.sleep(1)
sys.stdout.write(f"[entrypoint] database {host}:{port} is reachable\n")
PY
fi

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "[entrypoint] running alembic upgrade head"
    alembic upgrade head
fi

exec "$@"
