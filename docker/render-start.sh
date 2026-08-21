#!/bin/sh
set -eu

# Sur Render Free, le conteneur redémarre après chaque mise en veille. Le garde
# de schéma n'exécute Django/Alembic que si les fichiers de migration ont changé.
python docker/render_migrations.py

exec gunicorn \
    --chdir backend \
    config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 \
    --threads 4 \
    --timeout 600
