#!/bin/sh
set -eu

# Les migrations sont idempotentes : elles appliquent uniquement les versions
# absentes et ne réinitialisent jamais la base Neon existante.
python backend/manage.py migrate --noinput
python -m alembic upgrade head
python backend/manage.py collectstatic --noinput --ignore="src/*"

exec gunicorn \
    --chdir backend \
    config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 \
    --threads 4 \
    --timeout 600
