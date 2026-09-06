#!/bin/sh
set -e

export FLASK_APP=run.py
# Default to docker-compose postgres service when DATABASE_URL is not provided.
if [ -z "${DATABASE_URL}" ]; then
  export DATABASE_URL="postgresql+psycopg2://postgres:postgres@db:5432/hris_postgres"
fi

python - <<'PY'
import os
import time
from urllib.parse import urlparse

import psycopg2

database_url = os.getenv("DATABASE_URL", "")
if not database_url.startswith("postgresql"):
    raise SystemExit("DATABASE_URL must point to PostgreSQL in Docker.")

parsed = urlparse(database_url)
dbname = parsed.path.lstrip("/") or "postgres"
host = parsed.hostname or "db"
port = parsed.port or 5432
user = parsed.username or "postgres"
password = parsed.password or ""

for attempt in range(30):
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        conn.close()
        break
    except psycopg2.OperationalError:
        if attempt == 29:
            raise
        time.sleep(2)
PY

python -m flask db upgrade
python -m flask seed
python -m flask seed-demo
python run.py
