#!/bin/sh
set -eu
if [ "${ENVIRONMENT:-development}" = production ]; then
    python -m app.release_guard
else
    alembic upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
