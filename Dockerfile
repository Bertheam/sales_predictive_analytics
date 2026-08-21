# syntax=docker/dockerfile:1.7

FROM node:22-slim AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY backend/templates ./backend/templates
COPY backend/static/src ./backend/static/src
COPY backend/static/js ./backend/static/js
RUN npm run assets:build

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=10 \
    RUN_ALEMBIC=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt

RUN useradd --create-home --shell /bin/bash appuser

COPY --chown=appuser:appuser . .
COPY --from=frontend --chown=appuser:appuser /build/backend/static/css/tailwind.css /app/backend/static/css/tailwind.css
COPY --from=frontend --chown=appuser:appuser /build/backend/static/vendor/lucide/ /app/backend/static/vendor/lucide/
RUN DJANGO_USE_SQLITE=true DJANGO_DEBUG=false \
        python backend/manage.py collectstatic --noinput --ignore="src/*" \
    && chown -R appuser:appuser /app/staticfiles \
    && chmod +x /app/docker/entrypoint.sh /app/docker/render-start.sh

USER appuser

EXPOSE 8080 8501

HEALTHCHECK --interval=5s --timeout=3s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8080'); path=os.getenv('APP_HEALTHCHECK_PATH', '/health/'); path == 'disabled' or urllib.request.urlopen(f'http://localhost:{port}{path}', timeout=3)" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["./docker/render-start.sh"]
