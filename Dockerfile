FROM node:22-slim AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY backend/templates ./backend/templates
COPY backend/static/src ./backend/static/src
COPY backend/static/js ./backend/static/js
RUN npm run css:build

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RUN_ALEMBIC=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libgomp1 \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

RUN useradd --create-home --shell /bin/bash appuser

COPY --chown=appuser:appuser . .
COPY --from=frontend --chown=appuser:appuser /build/backend/static/css/tailwind.css /app/backend/static/css/tailwind.css
RUN mkdir -p /app/staticfiles \
    && chown appuser:appuser /app/staticfiles \
    && chmod +x /app/docker/entrypoint.sh

USER appuser

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8000'); path=os.getenv('APP_HEALTHCHECK_PATH', '/health/'); urllib.request.urlopen(f'http://localhost:{port}{path}', timeout=3)" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["sh", "-c", "python backend/manage.py migrate --noinput && python -m alembic upgrade head && python backend/manage.py collectstatic --noinput --ignore='src/*' && gunicorn --chdir backend config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
